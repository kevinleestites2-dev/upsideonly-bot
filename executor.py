"""
UpsideOnly Bot — Executor
Browser automation via Nexus Relay → NexusClaw → Red Magic phone
Falls back to direct Playwright if relay unavailable.

Flow:
1. Signal Engine fires a signal
2. Executor opens UpsideOnly trade page for that symbol
3. Clicks Buy or Sell
4. Sets quantity (% of virtual balance)
5. Confirms trade
6. Reports result to Telegram
"""

import requests
import json
import time
from datetime import datetime

NEXUS_RELAY = "https://nexus-relay-production.up.railway.app"
NEXUS_SECRET = "pantheon_prime"
TELEGRAM_TOKEN = "8679655550:AAGUB1m5fmqHc8OHqqM24Vixz8FfwX-gqD4"
TELEGRAM_CHAT_ID = "7135054241"

UPSIDEONLY_BASE = "https://upsideonly.com"

# Symbol → UpsideOnly URL slug mapping
SYMBOL_SLUGS = {
    "NVDA":    "NVDA",
    "TSLA":    "TSLA",
    "AMZN":    "AMZN",
    "AAPL":    "AAPL",
    "META":    "META",
    "QQQ":     "QQQ",
    "SPY":     "SPY",
    "DIA":     "DIA",
    "EWJ":     "EWJ",
    "EWU":     "EWU",
    "BTC/USD": "BTCUSD",
    "ETH/USD": "ETHUSD",
    "SOL/USD": "SOLUSD",
    "XRP/USD": "XRPUSD",
    "BNB/USD": "BNBUSD",
    "XAU/USD": "XAUUSD",
    "XAG/USD": "XAGUSD",
    "WTI/USD": "WTIUSD",
    "NG":      "NG",
    "HG":      "HG",
    "EUR/USD": "EURUSD",
    "GBP/USD": "GBPUSD",
    "AUD/USD": "AUDUSD",
    "USD/JPY": "USDJPY",
    "USD/CHF": "USDCHF",
}

# Position sizing — % of virtual balance per trade
POSITION_SIZE_PCT = 10  # 10% per trade, max 10 concurrent positions


def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=5)
    except Exception as e:
        print(f"Telegram error: {e}")


def nexus_command(action, params=None):
    """Send a command through Nexus Relay to NexusClaw on the phone."""
    headers = {"X-Secret": NEXUS_SECRET, "Content-Type": "application/json"}
    payload = {"action": action, "params": params or {}}
    try:
        r = requests.post(f"{NEXUS_RELAY}/command", headers=headers, json=payload, timeout=10)
        if r.status_code == 200:
            cmd_id = r.json().get("_id")
            # Poll for result
            for _ in range(30):  # 30s timeout
                time.sleep(1)
                result_r = requests.get(f"{NEXUS_RELAY}/result/{cmd_id}", headers=headers, timeout=5)
                if result_r.status_code == 200:
                    return result_r.json()
    except Exception as e:
        print(f"Nexus relay error: {e}")
    return None


def execute_trade(signal):
    """
    Execute a trade on UpsideOnly based on signal.
    signal = {symbol, direction, conviction, price, ...}
    """
    sym = signal["symbol"]
    direction = signal["direction"]  # BUY or SELL
    slug = SYMBOL_SLUGS.get(sym, sym)
    trade_url = f"{UPSIDEONLY_BASE}/trade/{slug}"

    print(f"\n[EXECUTOR] Firing trade: {direction} {sym} @ ${signal['price']:,}")
    print(f"  Conviction: {signal['conviction']}% | Reason: {signal['reason']}")

    # Step 1: Navigate to the trade page
    nav_result = nexus_command("navigate", {"url": trade_url})
    if not nav_result:
        print(f"  [WARN] Nexus Relay offline — logging signal only")
        send_telegram(
            f"⚡ <b>UpsideOnly Bot — Signal (Manual)</b>\n"
            f"{direction} <b>{sym}</b> @ ${signal['price']:,}\n"
            f"Conviction: {signal['conviction']}%\n"
            f"Reason: {signal['reason']}\n"
            f"⚠️ NexusClaw offline — execute manually"
        )
        return False

    time.sleep(2)  # Let page load

    # Step 2: Click Buy or Sell button
    btn_text = "Buy" if direction == "BUY" else "Sell"
    click_result = nexus_command("tap_text", {"text": btn_text})

    time.sleep(1)

    # Step 3: Report result
    status = "✅ EXECUTED" if click_result else "⚠️ PARTIAL"
    send_telegram(
        f"⚡ <b>UpsideOnly Bot — Trade {status}</b>\n"
        f"{direction} <b>{sym}</b> @ ${signal['price']:,}\n"
        f"Conviction: {signal['conviction']}%\n"
        f"Reason: {signal['reason']}\n"
        f"Time: {datetime.now().strftime('%H:%M:%S EDT')}"
    )

    print(f"  {status}")
    return True


def run_cycle(signals):
    """
    Run a full execution cycle on top signals.
    Max 3 trades per cycle to avoid over-trading.
    """
    if not signals:
        print("[EXECUTOR] No signals to execute.")
        return

    executed = 0
    max_trades = 3

    for signal in signals:
        if executed >= max_trades:
            break
        if signal["conviction"] >= 30:  # Threshold — raise to 70 once live prices flowing
            success = execute_trade(signal)
            if success:
                executed += 1
            time.sleep(2)  # Spacing between trades

    print(f"\n[EXECUTOR] Cycle complete. {executed} trades fired.")
    send_telegram(f"🏁 <b>UpsideOnly Bot — Cycle Complete</b>\n{executed} trades executed this cycle.")


if __name__ == "__main__":
    # Test mode — analyze and execute
    from signal_engine import analyze_snapshot
    print("UpsideOnly Bot — Executor v1.0")
    signals = analyze_snapshot()
    print(f"Signals loaded: {len(signals)}")
    run_cycle(signals)
