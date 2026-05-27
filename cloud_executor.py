"""
UpsideOnly Bot — Cloud Executor v5
Auth: Bearer token from UPSIDEONLY_TOKEN env var (Auth0 access_token)
Flow: signal → validate token → POST /api/v1/predictions → report
"""

import json
import os
import time
import requests
from datetime import datetime
from signal_engine import analyze_snapshot

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8776802338:AAENyG3ADwNRpk59CuBDnsh8fDGcEuUFVSg")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "7135054241")
UPSIDEONLY_TOKEN = os.environ.get("UPSIDEONLY_TOKEN", "")
MIN_CONVICTION = 30
MAX_TRADES = 3
BASE_URL = "https://upsideonly.com"
API_BASE = "https://api.upsideonly.com"

# Asset → market UUID (from /api/v1/markets — confirmed live)
ASSET_MARKET_IDS = {
    "SOL/USD":  "da25c9b1-6ad6-4d8c-8f6b-8bca8eed3f89",
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


def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=5)
    except Exception as e:
        print(f"Telegram error: {e}")


def get_auth_headers():
    if not UPSIDEONLY_TOKEN:
        return None
    return {
        "Authorization": f"Bearer {UPSIDEONLY_TOKEN}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": BASE_URL,
        "Referer": BASE_URL,
        "User-Agent": "Mozilla/5.0",
    }


def validate_token():
    headers = get_auth_headers()
    if not headers:
        return None
    # Try both API bases — frontend uses upsideonly.com, backend may be api.upsideonly.com
    for base in [BASE_URL, API_BASE]:
        try:
            r = requests.get(f"{base}/api/v1/account", headers=headers, timeout=10)
            if r.status_code == 200:
                d = r.json()
                username = d.get("username") or d.get("display_name", "unknown")
                balance = d.get("balance") or d.get("portfolio_balance", 0)
                print(f"  Token valid [{base}] — user: {username} | balance: ${balance:,.2f}")
                return d
            elif r.status_code == 401:
                print(f"  Token expired/invalid [{base}]: {r.text[:100]}")
        except Exception as e:
            print(f"  Validate error [{base}]: {e}")
    return None


def submit_prediction(market_id, direction, amount=10):
    """Submit via API. direction = 'up' or 'down'."""
    headers = get_auth_headers()
    if not headers:
        return None

    payload = {
        "market_id": market_id,
        "direction": direction,
        "amount": amount,
    }

    for base in [BASE_URL, API_BASE]:
        for endpoint in ["/api/v1/predictions", "/api/v1/trades", "/api/v1/order-fills"]:
            try:
                r = requests.post(f"{base}{endpoint}", headers=headers, json=payload, timeout=10)
                print(f"  POST {base}{endpoint}: {r.status_code} | {r.text[:150]}")
                if r.status_code in (200, 201):
                    return r.json()
                elif r.status_code == 422:
                    # Unprocessable — log payload mismatch info
                    print(f"  422 detail: {r.text[:300]}")
            except Exception as e:
                print(f"  POST error {endpoint}: {e}")

    return None


def refresh_token():
    """
    Attempt to refresh using Auth0 refresh_token if stored.
    Returns new access_token or None.
    """
    refresh = os.environ.get("UPSIDEONLY_REFRESH_TOKEN", "")
    if not refresh:
        return None

    r = requests.post(
        "https://auth.upsideonly.com/oauth/token",
        json={
            "grant_type": "refresh_token",
            "client_id": "EH8iKT1Zurk62Xq3gYLD3fkvUm3LRRJH",
            "refresh_token": refresh,
        },
        headers={"Content-Type": "application/json"},
        timeout=10
    )
    if r.status_code == 200:
        new_token = r.json().get("access_token")
        print(f"  Token refreshed successfully")
        return new_token
    else:
        print(f"  Token refresh failed: {r.status_code} | {r.text[:100]}")
        return None


def run_cycle(signals=None):
    now = datetime.now().strftime("%Y-%m-%d %H:%M EDT")
    print(f"\n[{now}] Starting execution cycle...")

    # Check token
    global UPSIDEONLY_TOKEN
    account = validate_token()

    if not account:
        # Try refresh
        new_token = refresh_token()
        if new_token:
            UPSIDEONLY_TOKEN = new_token
            account = validate_token()

    if not account:
        send_telegram(
            f"<b>UpsideOnly Bot — Session Required</b>\n"
            f"<b>How to get your token (30 seconds):</b>\n\n"
            f"1. Open Chrome on phone\n"
            f"2. Go to upsideonly.com — log in with Google\n"
            f"3. Open DevTools (or use HTTP Toolkit)\n"
            f"4. Any API request will show: <code>Authorization: Bearer eyJ...</code>\n"
            f"5. Copy that token\n"
            f"6. Go to: github.com/kevinleestites2-dev/upsideonly-bot/settings/secrets/actions\n"
            f"7. Add secret: <code>UPSIDEONLY_TOKEN</code> = the token\n\n"
            f"Token lasts ~4 hours. Refresh token setup = auto-renewal.\n"
            f"Monitoring still running. Execution paused."
        )
        print("  No valid token. Execution paused.")
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
        direction = "up" if signal["direction"].upper() == "BUY" else "down"
        market_id = ASSET_MARKET_IDS.get(sym)
        conviction = signal["conviction"]

        if conviction < MIN_CONVICTION:
            continue
        if not market_id:
            print(f"  {sym}: no market ID — skip")
            continue

        print(f"  {direction.upper()} {sym} | conviction={conviction}% | market={market_id[:8]}...")
        result = submit_prediction(market_id, direction, amount=10)

        if result and result.get("success") is not False:
            executed += 1
            results.append(f"<b>{direction.upper()} {sym}</b> @ ${signal['price']:,} — {conviction}% conviction")
        else:
            err = str(result)[:80] if result else "no response"
            results.append(f"FAILED {direction.upper()} {sym} — {err}")

        time.sleep(1.5)

    summary = "\n".join(results) if results else "No trades attempted"
    send_telegram(
        f"<b>UpsideOnly — Cycle {now}</b>\n"
        f"{executed}/{len(signals[:MAX_TRADES])} trades executed\n\n"
        f"{summary}"
    )

    print(f"\n[EXECUTOR] {executed} trades fired.")
    return executed


if __name__ == "__main__":
    from signal_engine import analyze_snapshot
    signals = analyze_snapshot()
    print(f"Signals: {len(signals)}")
    for s in signals[:5]:
        print(f"  {s['direction']} {s['symbol']} | {s['conviction']}% | {s['reason']}")
    run_cycle(signals)
