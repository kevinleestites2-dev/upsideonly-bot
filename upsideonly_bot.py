#!/usr/bin/env python3
"""
UpsideOnly Strike Bot — Leaderboard Domination Engine
Target: Knock JimmieShortsWorld off #1
Loop: Open → Monitor → Close at target → Redeploy
"""

import requests
import time
from datetime import datetime

SESSION_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6IkRjbUUyTkpCWFNyZ2U0RVJGcVcxYyJ9.eyJpc3MiOiJodHRwczovL2F1dGgudXBzaWRlb25seS5jb20vIiwic3ViIjoiZ29vZ2xlLW9hdXRoMnwxMTQ1MjgzNDcxMDA3NzE1NzQzOTgiLCJhdWQiOlsiaHR0cHM6Ly9hcGkudXBzaWRlb25seS5jb20iLCJodHRwczovL2Rldi03b2IyMWJzbHR3enp4am00LnVzLmF1dGgwLmNvbS91c2VyaW5mbyJdLCJpYXQiOjE3Nzk5MjY0MzEsImV4cCI6MTc4MDAxMjgzMSwic2NvcGUiOiJvcGVuaWQgcHJvZmlsZSBlbWFpbCBvZmZsaW5lX2FjY2VzcyIsImF6cCI6IkVIOGlLVDFadXJrNjJYcTNnWUxEM2ZrdlVtM0xSUkpIIn0.hPqZm-FyssR5S41Xk2efOm_MFbS_c8wfhdkHgEW1Usk97wJIV3Mx4KU11CXsC5rgxuk_9ei5OpB8weV8Ys20x_zfuE-7BcKHHes26sW54FHgYqx1Yvu_NHesmCPLvhMuV2j6sPNA3L0SY6ltQftonL25w1F_IU0LFtgPaFbdRIyJw3Yn_ct6Smr5j1CGs2m3cwtPhIrwBfrEmGA-y14Qbwkaz-Ii6UrllwnuAvwcIf1pKQG4-yJkZetTJFommTrWqo2d_h406eoJibSK1t0x4blzgexsLlN0Zxz-tgEy5F9JxRmhAFnQwCMOr084PbBNf88BZtjlgR-ahvFgMtePuA"

TELEGRAM_TOKEN = "8776802338:AAENyG3ADwNRpk59CuBDnsh8fDGcEuUFVSg"
TELEGRAM_CHAT_ID = "7135054241"
BASE_URL = "https://upsideonly.com"

HEADERS = {
    "Authorization": f"Bearer {SESSION_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Origin": "https://upsideonly.com",
    "Referer": "https://upsideonly.com/"
}

# Strategy config
TAKE_PROFIT_PCT  = 0.5    # close at +0.5% gain
STOP_LOSS_PCT    = -0.3   # cut at -0.3% loss
TRADE_AMOUNT     = 10000  # per position
MONITOR_INTERVAL = 30     # seconds between checks
REPORT_INTERVAL  = 10     # cycles between Telegram reports

# Strike universe — momentum assets
STRIKE_SYMBOLS = [
    "NVDA", "META", "TSLA", "SPY", "QQQ",
    "AMZN", "AAPL", "BTC/USD", "SOL/USD", "XRP/USD"
]

def tg(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception as e:
        print(f"[TG ERROR] {e}")

def get_portfolio():
    r = requests.get(f"{BASE_URL}/api/v1/portfolio/summary", headers=HEADERS, timeout=10)
    return r.json()

def get_positions():
    r = requests.get(f"{BASE_URL}/api/v1/trades", headers=HEADERS, timeout=10)
    data = r.json()
    return [p for p in data.get("positions", []) if p.get("status") == "open"]

def place_trade(symbol, side="buy"):
    payload = {"symbol": symbol, "side": side, "amount": TRADE_AMOUNT}
    r = requests.post(f"{BASE_URL}/api/v1/trades", headers=HEADERS, json=payload, timeout=10)
    return r.json()

def close_trade(trade_id):
    r = requests.post(f"{BASE_URL}/api/v1/trades/{trade_id}/close", headers=HEADERS, timeout=10)
    return r.json()

def fill_positions():
    """Open positions on all symbols that aren't already held."""
    positions = get_positions()
    open_symbols = {p["symbol"] for p in positions}
    filled = []
    for sym in STRIKE_SYMBOLS:
        if sym not in open_symbols:
            result = place_trade(sym, "buy")
            if result.get("success") or result.get("trade_id"):
                filled.append(sym)
                print(f"  [OPEN] {sym} ${TRADE_AMOUNT:,}")
            else:
                err = result.get("error", "unknown")
                print(f"  [SKIP] {sym} — {err}")
            time.sleep(0.3)
    return filled

def monitor_and_cycle():
    """Check all open positions. Close winners/losers. Redeploy."""
    positions = get_positions()
    closed_win, closed_loss = [], []

    for pos in positions:
        pnl_pct = pos.get("unrealized_pnl_percent", 0)
        sym = pos["symbol"]
        pid = pos["id"]

        if pnl_pct >= TAKE_PROFIT_PCT:
            result = close_trade(pid)
            if result.get("success"):
                closed_win.append((sym, pnl_pct))
                print(f"  [WIN] Closed {sym} at {pnl_pct:.2f}%")
        elif pnl_pct <= STOP_LOSS_PCT:
            result = close_trade(pid)
            if result.get("success"):
                closed_loss.append((sym, pnl_pct))
                print(f"  [CUT] Closed {sym} at {pnl_pct:.2f}%")

    return closed_win, closed_loss

def run():
    print(f"\n{'='*55}")
    print(f"  UPSIDEONLY STRIKE BOT — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  TP: +{TAKE_PROFIT_PCT}%  |  SL: {STOP_LOSS_PCT}%  |  ${TRADE_AMOUNT:,}/pos")
    print(f"{'='*55}\n")

    portfolio = get_portfolio()
    balance = portfolio.get("currentBalance", {}).get("value", 0)
    perf = portfolio.get("performancePercent", 0)

    tg(
        f"<b>Strike Bot LIVE</b>\n"
        f"Balance: ${balance:,.2f}\n"
        f"Performance: {perf:.2f}%\n"
        f"TP: +{TAKE_PROFIT_PCT}% | SL: {STOP_LOSS_PCT}%\n"
        f"Filling positions..."
    )

    # Initial fill
    print("[PHASE 1] Filling positions...")
    filled = fill_positions()
    if filled:
        tg(f"Opened {len(filled)} positions: {', '.join(filled)}")

    cycle = 0
    total_wins = 0
    total_losses = 0

    print(f"\n[PHASE 2] Monitor loop active — checking every {MONITOR_INTERVAL}s\n")

    while True:
        cycle += 1
        now = datetime.now().strftime("%H:%M:%S")
        print(f"[{now}] Cycle {cycle} — scanning positions...")

        # Monitor and close
        wins, losses = monitor_and_cycle()
        total_wins += len(wins)
        total_losses += len(losses)

        # Redeploy freed capital
        if wins or losses:
            time.sleep(1)
            print(f"  Redeploying freed capital...")
            fill_positions()

        # Periodic Telegram report
        if cycle % REPORT_INTERVAL == 0:
            try:
                portfolio = get_portfolio()
                balance = portfolio.get("currentBalance", {}).get("value", 0)
                perf = portfolio.get("performancePercent", 0)
                positions = get_positions()
                pos_summary = "\n".join(
                    f"  {p['symbol']}: {p.get('unrealized_pnl_percent', 0):+.2f}%"
                    for p in positions
                ) or "  (none)"

                tg(
                    f"<b>Bot Report — Cycle {cycle}</b>\n"
                    f"Balance: ${balance:,.2f}\n"
                    f"Performance: {perf:.2f}%\n"
                    f"Total Wins: {total_wins} | Losses: {total_losses}\n"
                    f"Open Positions:\n{pos_summary}"
                )
            except Exception as e:
                print(f"  [REPORT ERROR] {e}")

        time.sleep(MONITOR_INTERVAL)

if __name__ == "__main__":
    run()
