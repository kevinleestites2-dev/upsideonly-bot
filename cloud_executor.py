"""
UpsideOnly Bot — Cloud Executor v4
IMPORTANT: UpsideOnly uses a DRAWING-BASED prediction system.
Flow: Login → Navigate to asset → Draw on chart → Pick direction (Up/Down) → Submit

Without a valid session cookie, all trade execution is blocked.
This executor handles:
1. Session validation
2. API-based trade submission (if endpoint found)
3. Graceful fallback with diagnostics when session is missing
"""

import json
import os
import time
import requests
from datetime import datetime
from signal_engine import analyze_snapshot

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8776802338:AAENyG3ADwNRpk59CuBDnsh8fDGcEuUFVSg")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "7135054241")
COOKIES_FILE = "cookies.json"
MIN_CONVICTION = 30
MAX_TRADES = 3
BASE_URL = "https://upsideonly.com"

# Asset → market ID mapping (from /api/v1/markets)
# SOL/USD first — that's Jimmie's arena
ASSET_MARKET_IDS = {
    "SOL/USD":  "da25c9b1-6ad6-4d8c-8f6b-8bca8eed3f89",  # primary SOL market
    "BTC/USD":  "f8306ea5-05ac-45e6-8241-8414f4acc5bb",
    "ETH/USD":  "b5dd9349-c945-49ae-92ec-aff5d0cbe3b6",
    "QQQ":      "5bbb4472-8512-4cae-9f20-a02b11d70475",
    "NVDA":     "a9e20906-3fde-4191-91fb-7216246e8f42",
    "TSLA":     "77171ec9-0eee-45c2-8bc7-d325c7769f4f",
    "AAPL":     "00a37d38-e3fa-4281-aaa6-19eb5938b313",
    "META":     "2d85f9e0-31f3-4364-b04d-4d2283adcc53",
    "XAU/USD":  "fe582cbd-7b8d-450d-bdff-55b06eb5b15e",
    "XAG/USD":  "d78964a1-74cf-4553-9338-e75c02d4b6cb",
    "WTI/USD":  "9b3e004d-dc0e-40f6-83a7-40f2241ce577",
    "EUR/USD":  "e3af4b59-616c-48a4-a3d5-e56d78a9489d",
    "GBP/USD":  "1e971306-028e-4298-8521-129ecdaa662e",
    "BNB/USD":  "03051e83-a320-401c-a2d7-4e3bcae98328",
}

# Asset → trade URL (asset slug as used in UI)
ASSET_URLS = {
    "SOL/USD":  f"{BASE_URL}/trade/SOLUSD",
    "BTC/USD":  f"{BASE_URL}/trade/BTCUSD",
    "ETH/USD":  f"{BASE_URL}/trade/ETHUSD",
    "QQQ":      f"{BASE_URL}/trade/QQQ",
    "NVDA":     f"{BASE_URL}/trade/NVDA",
    "TSLA":     f"{BASE_URL}/trade/TSLA",
    "AAPL":     f"{BASE_URL}/trade/AAPL",
    "META":     f"{BASE_URL}/trade/META",
    "XAU/USD":  f"{BASE_URL}/trade/XAUUSD",
    "XAG/USD":  f"{BASE_URL}/trade/XAGUSD",
    "WTI/USD":  f"{BASE_URL}/trade/WTIUSD",
    "EUR/USD":  f"{BASE_URL}/trade/EURUSD",
    "GBP/USD":  f"{BASE_URL}/trade/GBPUSD",
    "BNB/USD":  f"{BASE_URL}/trade/BNBUSD",
}


def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=5)
    except Exception as e:
        print(f"Telegram error: {e}")


def load_cookies():
    try:
        with open(COOKIES_FILE) as f:
            return json.load(f)
    except Exception:
        return []


def cookies_to_header(cookies):
    """Convert cookie list to Cookie header string."""
    return "; ".join(f"{c['name']}={c['value']}" for c in cookies if "name" in c and "value" in c)


def validate_session(cookies):
    """Check if session is valid by hitting /api/v1/account."""
    if not cookies:
        return None
    headers = {
        "Accept": "application/json",
        "Cookie": cookies_to_header(cookies),
        "User-Agent": "Mozilla/5.0",
    }
    try:
        r = requests.get(f"{BASE_URL}/api/v1/account", headers=headers, timeout=10)
        if r.status_code == 200:
            d = r.json()
            print(f"  Session valid — user: {d.get('username', 'unknown')} | balance: ${d.get('balance', 0):,.2f}")
            return d
    except Exception as e:
        print(f"  Session check error: {e}")
    return None


def submit_prediction_api(cookies, market_id, direction, amount=10):
    """
    Attempt to submit a prediction via the API directly.
    direction: 'up' or 'down'
    amount: USD amount (minimum $10)
    """
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Cookie": cookies_to_header(cookies),
        "User-Agent": "Mozilla/5.0",
        "Referer": BASE_URL,
        "Origin": BASE_URL,
    }

    # Try /api/v1/predictions endpoint
    payload = {
        "market_id": market_id,
        "direction": direction,  # 'up' or 'down'
        "amount": amount,
    }

    try:
        r = requests.post(f"{BASE_URL}/api/v1/predictions", headers=headers,
                         json=payload, timeout=10)
        print(f"  predictions POST: {r.status_code} | {r.text[:200]}")
        if r.status_code in (200, 201):
            return r.json()
    except Exception as e:
        print(f"  predictions POST error: {e}")

    # Also try /api/v1/trades
    try:
        r2 = requests.post(f"{BASE_URL}/api/v1/trades", headers=headers,
                          json=payload, timeout=10)
        print(f"  trades POST: {r2.status_code} | {r2.text[:200]}")
        if r2.status_code in (200, 201):
            return r2.json()
    except Exception as e:
        print(f"  trades POST error: {e}")

    return None


def run_cycle(signals=None):
    """
    Main execution cycle.
    1. Validate session
    2. For each signal, attempt API trade submission
    3. Report results
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M EDT")
    print(f"\n[{now}] Starting execution cycle...")

    cookies = load_cookies()
    account = validate_session(cookies)

    if not account:
        msg = (f"🔐 <b>UpsideOnly Bot — No Active Session</b>\n"
               f"📅 {now}\n\n"
               f"Trade execution requires a logged-in session.\n"
               f"<b>Action needed:</b> Log into UpsideOnly on your phone, export cookies to <code>cookies.json</code>, "
               f"and push to the repo as a GitHub Secret <code>COOKIES_JSON</code>.\n\n"
               f"Monitoring continues ✅ — execution paused 🔐")
        send_telegram(msg)
        print("  No valid session. Execution paused.")
        return 0

    if signals is None:
        signals = analyze_snapshot()

    if not signals:
        print("  No signals above threshold.")
        return 0

    executed = 0
    results = []

    for signal in signals[:MAX_TRADES]:
        sym = signal["symbol"]
        direction = signal["direction"].lower()  # 'buy' → 'up', 'sell' → 'down'
        api_direction = "up" if direction == "buy" else "down"
        market_id = ASSET_MARKET_IDS.get(sym)
        conviction = signal["conviction"]

        if conviction < MIN_CONVICTION:
            continue

        if not market_id:
            print(f"  {sym}: No market ID mapped — skipping")
            continue

        print(f"  Executing: {api_direction.upper()} {sym} | conviction={conviction}%")

        result = submit_prediction_api(cookies, market_id, api_direction, amount=10)

        if result and result.get("success") is not False:
            executed += 1
            results.append(f"✅ {api_direction.upper()} {sym} @ {signal['price']} | {conviction}%")
        else:
            results.append(f"⚠️ FAILED {api_direction.upper()} {sym} — {str(result)[:60] if result else 'no response'}")

        time.sleep(1.5)

    summary = "\n".join(results) if results else "No trades attempted"
    send_telegram(
        f"⚡ <b>UpsideOnly Bot — Cycle Complete</b>\n"
        f"📅 {now}\n"
        f"{executed} trades executed\n\n"
        f"{summary}"
    )

    print(f"\n[EXECUTOR] {executed} trades executed.")
    return executed


if __name__ == "__main__":
    from signal_engine import analyze_snapshot
    signals = analyze_snapshot()
    print(f"Signals: {len(signals)}")
    for s in signals[:5]:
        print(f"  {s['direction']} {s['symbol']} | conviction={s['conviction']}% | {s['reason']}")
    run_cycle(signals)
