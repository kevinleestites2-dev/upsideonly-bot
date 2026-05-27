"""
UpsideOnly Leaderboard Monitor — Direct API, No Auth Required
Hits /api/v1/leaderboard directly, tracks JimmieShortsWorld, Telegrams on changes.
"""

import os
import json
import requests
from datetime import datetime

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
TARGET_USER = "JimmieShortsWorld"
STATE_FILE = "leaderboard_state.json"
API_BASE = "https://upsideonly.com/api/v1"
PERIODS = ["", "weekly", "monthly"]  # all-time, weekly, monthly


def send_telegram(msg: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"})
    if not r.ok:
        print(f"Telegram error: {r.text}")


def fetch_leaderboard(period: str = "") -> list:
    params = {"period": period} if period else {}
    r = requests.get(f"{API_BASE}/leaderboard", params=params,
                     headers={"Accept": "application/json"}, timeout=15)
    r.raise_for_status()
    return r.json()


def find_target(data: list) -> dict | None:
    for t in data:
        if t.get("username", "").lower() == TARGET_USER.lower():
            return t
    return None


def fmt_trader(t: dict) -> str:
    pct = f"{t['percentGain']:.2f}%"
    bal = f"${t['portfolioBalance']:,.0f}"
    wr = f"{t['winRate']*100:.1f}% WR"
    trades = t['totalPredictions']
    rank = t['rank']
    title = t.get('rewardHighlight', '')
    return f"#{rank} {t['username']} [{title}] — {pct} | {bal} | {wr} | {trades} trades"


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
    print(f"[{now}] Fetching leaderboard...")

    # Fetch all-time + weekly
    try:
        alltime = fetch_leaderboard("")
        weekly = fetch_leaderboard("weekly")
    except Exception as e:
        send_telegram(f"⚠️ <b>Leaderboard fetch failed</b>\n{e}")
        print(f"Fetch error: {e}")
        return

    target_alltime = find_target(alltime)
    target_weekly = find_target(weekly)
    top3_alltime = alltime[:3]
    top3_weekly = weekly[:3]

    prev = load_state()
    first_run = not prev

    # Detect changes
    prev_at = prev.get("target_alltime", {})
    prev_wk = prev.get("target_weekly", {})
    prev_top3_at = prev.get("top3_alltime", [])

    at_rank_changed = target_alltime and target_alltime.get("rank") != prev_at.get("rank")
    at_pct_changed = target_alltime and abs(target_alltime.get("percentGain", 0) - prev_at.get("percentGain", 0)) > 0.5
    at_trades_changed = target_alltime and target_alltime.get("totalPredictions", 0) != prev_at.get("totalPredictions", 0)
    wk_rank_changed = target_weekly and target_weekly.get("rank") != prev_wk.get("rank")
    top3_changed = top3_alltime != prev_top3_at

    something_changed = at_rank_changed or at_pct_changed or at_trades_changed or wk_rank_changed or top3_changed

    if first_run:
        msg = f"🔱 <b>UpsideOnly Monitor — ONLINE</b>\n📅 {now}\n\n"
        msg += f"<b>🏆 All-Time Top 3:</b>\n"
        for t in top3_alltime:
            msg += f"  {fmt_trader(t)}\n"
        msg += f"\n<b>📅 Weekly Top 3:</b>\n"
        for t in top3_weekly[:3]:
            msg += f"  {fmt_trader(t)}\n"
        if target_alltime:
            at = target_alltime
            msg += f"\n🎯 <b>{TARGET_USER} (All-Time):</b>\n"
            msg += f"  Rank #{at['rank']} | {at['percentGain']:.2f}% | ${at['portfolioBalance']:,.0f}\n"
            msg += f"  Win Rate: {at['winRate']*100:.1f}% | Trades: {at['totalPredictions']}\n"
            msg += f"  Title: {at.get('rewardHighlight','—')}"
        send_telegram(msg)

    elif something_changed:
        msg = f"⚡ <b>{TARGET_USER} — CHANGE DETECTED</b>\n📅 {now}\n\n"

        if at_rank_changed or at_pct_changed or at_trades_changed:
            at = target_alltime
            prev_rank = prev_at.get('rank', '?')
            curr_rank = at['rank']
            direction = "📈" if isinstance(prev_rank, int) and curr_rank < prev_rank else "📉" if isinstance(prev_rank, int) and curr_rank > prev_rank else "➡️"
            msg += f"<b>All-Time {direction}</b>\n"
            msg += f"  Rank: #{prev_rank} → #{curr_rank}\n"
            msg += f"  Return: {prev_at.get('percentGain',0):.2f}% → {at['percentGain']:.2f}%\n"
            msg += f"  Balance: ${prev_at.get('portfolioBalance',0):,.0f} → ${at['portfolioBalance']:,.0f}\n"
            msg += f"  Trades: {prev_at.get('totalPredictions','?')} → {at['totalPredictions']}\n"
            msg += f"  Win Rate: {at['winRate']*100:.1f}%\n\n"

        if wk_rank_changed and target_weekly:
            wk = target_weekly
            msg += f"<b>Weekly 📅</b>\n"
            msg += f"  Rank: #{prev_wk.get('rank','?')} → #{wk['rank']}\n"
            msg += f"  Return: {wk['percentGain']:.2f}% | Trades: {wk['totalPredictions']}\n\n"

        if top3_changed:
            msg += f"<b>New Top 3 (All-Time):</b>\n"
            for t in top3_alltime:
                msg += f"  {fmt_trader(t)}\n"

        send_telegram(msg)

    else:
        # Heartbeat every 2nd silent run (~1 hour)
        run_count = prev.get("run_count", 0) + 1
        if run_count % 2 == 0 and target_alltime:
            at = target_alltime
            msg = (f"💓 <b>Heartbeat</b> — No changes\n"
                   f"🎯 {TARGET_USER}: #{at['rank']} | {at['percentGain']:.2f}% | "
                   f"{at['totalPredictions']} trades\n📅 {now}")
            send_telegram(msg)
        print(f"No changes. Run #{prev.get('run_count',0)+1}")

    # Save state
    save_state({
        "target_alltime": target_alltime or prev.get("target_alltime", {}),
        "target_weekly": target_weekly or prev.get("target_weekly", {}),
        "top3_alltime": top3_alltime,
        "top3_weekly": top3_weekly[:3],
        "run_count": prev.get("run_count", 0) + 1,
        "last_run": now
    })
    print("Done.")


if __name__ == "__main__":
    run()
