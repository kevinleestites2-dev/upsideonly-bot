"""
UpsideOnly Bot — Cloud Executor v3
DOM-aware trade execution via Playwright on GitHub Actions.
"""

import json
import os
import time
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright
from signal_engine import analyze_snapshot

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8679655550:AAGUB1m5fmqHc8OHqqM24Vixz8FfwX-gqD4")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "7135054241")
COOKIES_FILE = "cookies.json"
MIN_CONVICTION = 30
MAX_TRADES = 3

SYMBOL_URLS = {
    "WTI/USD":  "https://upsideonly.com/trade/WTI",
    "XAG/USD":  "https://upsideonly.com/trade/XAGUSD",
    "XAU/USD":  "https://upsideonly.com/trade/XAUUSD",
    "NVDA":     "https://upsideonly.com/trade/NVDA",
    "TSLA":     "https://upsideonly.com/trade/TSLA",
    "AAPL":     "https://upsideonly.com/trade/AAPL",
    "AMZN":     "https://upsideonly.com/trade/AMZN",
    "META":     "https://upsideonly.com/trade/META",
    "SPY":      "https://upsideonly.com/trade/SPY",
    "QQQ":      "https://upsideonly.com/trade/QQQ",
    "BTC/USD":  "https://upsideonly.com/trade/BTCUSD",
    "ETH/USD":  "https://upsideonly.com/trade/ETHUSD",
    "SOL/USD":  "https://upsideonly.com/trade/SOLUSD",
    "EUR/USD":  "https://upsideonly.com/trade/EURUSD",
    "GBP/USD":  "https://upsideonly.com/trade/GBPUSD",
}


def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=5)
    except Exception as e:
        print(f"Telegram error: {e}")


def send_telegram_photo(img_path, caption=""):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    try:
        with open(img_path, "rb") as f:
            requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption},
                         files={"photo": f}, timeout=10)
    except Exception as e:
        print(f"Telegram photo error: {e}")


def load_cookies():
    try:
        with open(COOKIES_FILE) as f:
            return json.load(f)
    except Exception as e:
        print(f"Cookie load error: {e}")
        return []


def dump_page_info(page, label="page"):
    screenshot_path = f"screenshot_{label}.png"
    page.screenshot(path=screenshot_path, full_page=True)
    print(f"  [DEBUG] Screenshot: {screenshot_path}")
    buttons = page.query_selector_all("button")
    print(f"  [DEBUG] Buttons found ({len(buttons)}):")
    for b in buttons[:20]:
        txt = b.inner_text().strip()
        cls = b.get_attribute("class") or ""
        if txt:
            print(f"    btn: '{txt}' | class: {cls[:80]}")
    return screenshot_path


def try_click_trade_button(page, direction):
    btn_text = "Buy" if direction == "BUY" else "Sell"
    alt_text = "Long" if direction == "BUY" else "Short"

    selectors = [
        f"button:has-text('{btn_text}')",
        f"button:has-text('{alt_text}')",
        f"[data-testid='{btn_text.lower()}']",
        f"[data-testid='{alt_text.lower()}']",
        f"[class*='{btn_text.lower()}']",
        f"[class*='{alt_text.lower()}']",
    ]

    for sel in selectors:
        try:
            el = page.locator(sel).first
            if el.count() > 0 and el.is_visible():
                el.click()
                print(f"  Clicked: {sel}")
                return True
        except Exception:
            continue

    # Fallback — scan all buttons
    for b in page.query_selector_all("button"):
        txt = b.inner_text().strip().lower()
        if btn_text.lower() in txt or alt_text.lower() in txt:
            try:
                b.click()
                print(f"  Clicked button text: {txt}")
                return True
            except Exception:
                continue

    return False


def try_confirm(page):
    for txt in ["Confirm", "Place Order", "Submit", "Execute", "Place Trade"]:
        try:
            btn = page.locator(f"button:has-text('{txt}')").first
            if btn.count() > 0 and btn.is_visible():
                btn.click()
                print(f"  Confirmed: {txt}")
                return True
        except Exception:
            continue
    return False


def execute_trades(signals):
    if not signals:
        print("No signals.")
        return

    cookies = load_cookies()
    if not cookies:
        send_telegram("No cookies found — re-capture needed.")
        return

    tradeable = [s for s in signals if s["conviction"] >= MIN_CONVICTION][:MAX_TRADES]
    if not tradeable:
        print("No signals above threshold.")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        context.add_cookies(cookies)
        page = context.new_page()

        # Auth check
        page.goto("https://upsideonly.com/portfolio", wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(3000)
        current_url = page.url
        print(f"Auth URL: {current_url}")

        if "login" in current_url or "auth" in current_url or "signin" in current_url:
            sc = dump_page_info(page, "auth_fail")
            send_telegram_photo(sc, "Auth failed — cookies expired")
            browser.close()
            return

        print("Auth OK")

        # Scout: screenshot first trade page so we see real DOM
        first = tradeable[0]
        scout_url = SYMBOL_URLS.get(first["symbol"], f"https://upsideonly.com/trade/{first['symbol']}")
        page.goto(scout_url, wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(4000)
        sc = dump_page_info(page, f"scout")
        send_telegram_photo(sc, f"Scout: {first['symbol']} trade page")

        executed = []

        for signal in tradeable:
            sym = signal["symbol"]
            direction = signal["direction"]
            print(f"\n{direction} {sym} | {signal['conviction']}%")

            try:
                url = SYMBOL_URLS.get(sym, f"https://upsideonly.com/trade/{sym}")
                page.goto(url, wait_until="networkidle", timeout=20000)
                page.wait_for_timeout(3000)

                clicked = try_click_trade_button(page, direction)
                if clicked:
                    page.wait_for_timeout(1500)
                    try_confirm(page)
                    executed.append(signal)
                else:
                    sc = dump_page_info(page, f"fail_{sym.replace('/', '')}")
                    send_telegram_photo(sc, f"Button not found: {sym} {direction}")

            except Exception as e:
                print(f"Error {sym}: {e}")

        browser.close()

    if executed:
        lines = [f"<b>UpsideOnly Bot — {len(executed)} Trade(s) Fired</b>",
                 f"{datetime.now().strftime('%H:%M EDT')}\n"]
        for s in executed:
            arrow = "BUY" if s["direction"] == "BUY" else "SELL"
            lines.append(f"{arrow} {s['symbol']} | {s['change_pct']:+.2f}% | {s['conviction']}%")
        send_telegram("\n".join(lines))
    else:
        send_telegram("0 trades executed this cycle.")


if __name__ == "__main__":
    print(f"Cloud Executor v3 — {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    signals = analyze_snapshot()
    print(f"Signals: {len(signals)}")
    execute_trades(signals)
