"""
UpsideOnly Bot — Cloud Executor
Runs inside GitHub Actions. No tunnel, no phone, no wifi dependency.
Uses saved session cookies to authenticate, then executes trades via Playwright.
"""

import json
import os
import time
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright
from signal_engine import analyze_snapshot, format_signal_report

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8679655550:AAGUB1m5fmqHc8OHqqM24Vixz8FfwX-gqD4")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "7135054241")
COOKIES_FILE = "cookies.json"
UPSIDEONLY_TRADE = "https://upsideonly.com/trade"
MIN_CONVICTION = 30
MAX_TRADES = 3


def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=5)
    except Exception as e:
        print(f"Telegram error: {e}")


def load_cookies():
    try:
        with open(COOKIES_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Cookie load error: {e}")
        return []


def execute_trades(signals):
    if not signals:
        print("No signals to execute.")
        return

    cookies = load_cookies()
    if not cookies:
        send_telegram("⚠️ <b>UpsideOnly Bot</b> — No session cookies found. Re-capture needed.")
        return

    tradeable = [s for s in signals if s["conviction"] >= MIN_CONVICTION][:MAX_TRADES]

    if not tradeable:
        print("No signals above conviction threshold.")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()

        # Inject saved session cookies
        context.add_cookies(cookies)

        page = context.new_page()

        executed = []

        for signal in tradeable:
            sym = signal["symbol"]
            direction = signal["direction"]

            print(f"Executing: {direction} {sym} @ conviction {signal['conviction']}%")

            try:
                # Navigate to trade page
                page.goto(UPSIDEONLY_TRADE, wait_until="networkidle", timeout=15000)
                time.sleep(2)

                # Search for the market
                search = page.query_selector("input[placeholder*='Search']") or \
                         page.query_selector("input[placeholder*='search']") or \
                         page.query_selector("[data-testid='search-input']")

                if search:
                    search.click()
                    search.fill(sym)
                    time.sleep(1)
                    # Click first result
                    result = page.query_selector(".market-result, [data-testid='market-item']")
                    if result:
                        result.click()
                        time.sleep(1)

                # Click Buy or Sell
                btn_text = "Buy" if direction == "BUY" else "Sell"
                btn = page.get_by_role("button", name=btn_text).first
                if btn:
                    btn.click()
                    time.sleep(1)
                    executed.append(signal)
                    print(f"  ✅ {direction} {sym} executed")
                else:
                    print(f"  ⚠️ Button not found for {sym}")

            except Exception as e:
                print(f"  ❌ Error on {sym}: {e}")

        browser.close()

        # Report results
        if executed:
            lines = [f"⚡ <b>UpsideOnly Bot — {len(executed)} Trade(s) Executed</b>"]
            lines.append(f"🕐 {datetime.now().strftime('%H:%M EDT')}\n")
            for s in executed:
                arrow = "🟢" if s["direction"] == "BUY" else "🔴"
                lines.append(f"{arrow} {s['direction']} <b>{s['symbol']}</b> @ ${s['price']:,} | {s['change_pct']:+.2f}% | {s['conviction']}% conviction")
            send_telegram("\n".join(lines))
        else:
            print("No trades executed this cycle.")


if __name__ == "__main__":
    print(f"Cloud Executor — {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    signals = analyze_snapshot()
    print(f"Signals: {len(signals)}")
    execute_trades(signals)
