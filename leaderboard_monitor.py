"""
UpsideOnly Leaderboard Monitor — No Auth Required
Scrapes public leaderboard, tracks JimmieShortsWorld, Telegrams changes.
"""

import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
TARGET_USER = "JimmieShortsWorld"
STATE_FILE = "leaderboard_state.json"
LEADERBOARD_URL = "https://upsideonly.com"


def send_telegram(msg: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"})


def scrape_leaderboard() -> list[dict]:
    """Scrape the public leaderboard from the homepage."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    resp = requests.get(LEADERBOARD_URL, headers=headers, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    traders = []

    # Parse leaderboard entries — each has rank, name, trades, %, $value
    # Structure based on observed HTML
    for item in soup.find_all(attrs={"cursor": "pointer"}):
        texts = [t.strip() for t in item.stripped_strings]
        if not texts:
            continue
        # Look for entries that have a rank number + trader name pattern
        try:
            rank = int(texts[0])
            name = texts[1]
            trades_str = texts[2] if len(texts) > 2 else ""
            pct = texts[3] if len(texts) > 3 else ""
            value = texts[4] if len(texts) > 4 else ""
            traders.append({
                "rank": rank,
                "name": name,
                "trades": trades_str,
                "pct": pct,
                "value": value
            })
        except (ValueError, IndexError):
            continue

    return traders


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}


def save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def run():
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    print(f"[{now}] Scraping leaderboard...")

    try:
        traders = scrape_leaderboard()
    except Exception as e:
        send_telegram(f"⚠️ <b>Leaderboard scrape failed</b>\n{e}")
        print(f"Scrape error: {e}")
        return

    if not traders:
        print("No traders found — page structure may have changed.")
        send_telegram("⚠️ <b>No leaderboard data found.</b> Page may have changed.")
        return

    print(f"Found {len(traders)} traders.")

    # Find target
    target = next((t for t in traders if TARGET_USER.lower() in t["name"].lower()), None)
    top3 = traders[:3]

    prev_state = load_state()
    prev_target = prev_state.get("target", {})
    prev_top3 = prev_state.get("top3", [])

    # Detect changes
    target_changed = target != prev_target
    top3_changed = top3 != prev_top3
    first_run = not prev_state

    if first_run:
        # Always report on first run
        msg = f"🔱 <b>UpsideOnly Monitor — LIVE</b>\n\n"
        msg += f"📅 {now}\n\n"
        msg += f"<b>Current Top 3:</b>\n"
        for t in top3:
            msg += f"  #{t['rank']} {t['name']} — {t['pct']} ({t['value']}) | {t['trades']}\n"
        if target:
            msg += f"\n🎯 <b>{TARGET_USER}:</b> #{target['rank']} | {target['pct']} | {target['value']} | {target['trades']}"
        else:
            msg += f"\n🎯 <b>{TARGET_USER}:</b> Not in top 3 (dropped or not visible)"
        send_telegram(msg)

    else:
        # Report only on changes
        if target_changed and target:
            prev_rank = prev_target.get("rank", "?")
            curr_rank = target["rank"]
            direction = "📈" if curr_rank < prev_rank else "📉" if curr_rank > prev_rank else "➡️"
            msg = (
                f"{direction} <b>{TARGET_USER} UPDATE</b>\n\n"
                f"Rank: #{prev_rank} → #{curr_rank}\n"
                f"Return: {prev_target.get('pct','?')} → {target['pct']}\n"
                f"Value: {prev_target.get('value','?')} → {target['value']}\n"
                f"Trades: {prev_target.get('trades','?')} → {target['trades']}\n"
                f"📅 {now}"
            )
            send_telegram(msg)

        if top3_changed:
            msg = f"🏆 <b>Top 3 Changed</b>\n\n"
            for t in top3:
                msg += f"  #{t['rank']} {t['name']} — {t['pct']} ({t['value']})\n"
            msg += f"\n📅 {now}"
            send_telegram(msg)

        if not target_changed and not top3_changed:
            print("No changes detected. Silent run.")
            # Hourly heartbeat (every 2 runs = ~1 hour)
            run_count = prev_state.get("run_count", 0) + 1
            if run_count % 2 == 0:
                msg = f"💓 <b>Heartbeat</b> — No changes\n"
                if target:
                    msg += f"🎯 {TARGET_USER} still #{target['rank']} | {target['pct']}\n"
                msg += f"📅 {now}"
                send_telegram(msg)
            prev_state["run_count"] = run_count
            save_state({**prev_state, "target": target, "top3": top3})
            return

    # Save new state
    run_count = prev_state.get("run_count", 0) + 1
    save_state({"target": target, "top3": top3, "run_count": run_count, "last_run": now})
    print("Done.")


if __name__ == "__main__":
    run()
