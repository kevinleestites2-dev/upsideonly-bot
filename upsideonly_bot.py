#!/usr/bin/env python3
"""
UpsideOnly Strike Bot — Leaderboard Domination Engine
Target: Knock JimmieShortsWorld off #1
Loop: Open → Monitor → Close at target → Redeploy
Token expiry alert built in.
"""

import requests
import time
from datetime import datetime, timezone

# ─── CONFIG ───────────────────────────────────────────────────────────────────

SESSION_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6IkRjbUUyTkpCWFNyZ2U0RVJGcVcxYyJ9.eyJpc3MiOiJodHRwczovL2F1dGgudXBzaWRlb25seS5jb20vIiwic3ViIjoiZ29vZ2xlLW9hdXRoMnwxMTQ1MjgzNDcxMDA3NzE1NzQzOTgiLCJhdWQiOlsiaHR0cHM6Ly9hcGkudXBzaWRlb25seS5jb20iLCJodHRwczovL2Rldi03b2IyMWJzbHR3enp4am00LnVzLmF1dGgwLmNvbS91c2VyaW5mbyJdLCJpYXQiOjE3Nzk5MjY0MzEsImV4cCI6MTc4MDAxMjgzMSwic2NvcGUiOiJvcGVuaWQgcHJvZmlsZSBlbWFpbCBvZmZsaW5lX2FjY2VzcyIsImF6cCI6IkVIOGlLVDFadXJrNjJYcTNnWUxEM2ZrdlVtM0xSUkpIIn0.hPqZm-FyssR5S41Xk2efOm_MFbS_c8wfhdkHgEW1Usk97wJIV3Mx4KU11CXsC5rgxuk_9ei5OpB8weV8Ys20x_zfuE-7BcKHHes26sW54FHgYqx1Yvu_NHesmCPLvhMuV2j6sPNA3L0SY6ltQftonL25w1F_IU0LFtgPaFbdRIyJw3Yn_ct6Smr5j1CGs2m3cwtPhIrwBfrEmGA-y14Qbwkaz-Ii6UrllwnuAvwcIf1pKQG4-yJkZetTJFommTrWqo2d_h406eoJibSK1t0x4blzgexsLlN0Zxz-tgEy5F9JxRmhAFnQwCMOr084PbBNf88BZtjlgR-ahvFgMtePuA"

TOKEN_EXP_UTC   = 1780012831   # Unix timestamp — alert 2h before this

TELEGRAM_TOKEN  = "8776802338:AAENyG3ADwNRpk59CuBDnsh8fDGcEuUFVSg"
TELEGRAM_CHAT   = "7135054241"
BASE_URL        = "https://upsideonly.com"

TAKE_PROFIT_PCT = 0.5     # close position at +0.5% gain
STOP_LOSS_PCT   = -0.3    # cut at -0.3% loss
TRADE_AMOUNT    = 10000   # USD per position
MONITOR_SECS    = 30      # seconds between scan cycles
REPORT_EVERY    = 10      # cycles between Telegram status reports
TOKEN_WARN_SECS = 7200    # alert 2 hours before expiry

STRIKE_SYMBOLS = [
    "NVDA", "META", "TSLA", "SPY", "QQQ",
    "AMZN", "AAPL", "BTC/USD", "SOL/USD", "XRP/USD"
]

# ─── API ──────────────────────────────────────────────────────────────────────

def headers():
    return {
        "Authorization": f"Bearer {SESSION_TOKEN}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": BASE_URL,
        "Referer": BASE_URL + "/"
    }

def tg(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT, "text": msg, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception as e:
        print(f"[TG] {e}")

def get_portfolio():
    r = requests.get(f"{BASE_URL}/api/v1/portfolio/summary", headers=headers(), timeout=10)
    return r.json()

def get_positions():
    r = requests.get(f"{BASE_URL}/api/v1/trades", headers=headers(), timeout=10)
    return [p for p in r.json().get("positions", []) if p.get("status") == "open"]

def place_trade(symbol, side="buy"):
    r = requests.post(
        f"{BASE_URL}/api/v1/trades",
        headers=headers(),
        json={"symbol": symbol, "side": side, "amount": TRADE_AMOUNT},
        timeout=10
    )
    return r.json()

def close_trade(trade_id):
    r = requests.post(f"{BASE_URL}/api/v1/trades/{trade_id}/close", headers=headers(), timeout=10)
    return r.json()

# ─── LOGIC ────────────────────────────────────────────────────────────────────

def check_token_expiry():
    """Warn on Telegram if token expires within TOKEN_WARN_SECS."""
    now = int(datetime.now(timezone.utc).timestamp())
    remaining = TOKEN_EXP_UTC - now
    if remaining <= 0:
        tg(
            "🔴 <b>TOKEN EXPIRED — Bot halted</b>\n"
            "Go to upsideonly.com → Cookie-Editor → export JSON → send to ZapiaPrime to redeploy."
        )
        print("[FATAL] Token expired. Exiting.")
        raise SystemExit(1)
    if remaining <= TOKEN_WARN_SECS:
        mins = remaining // 60
        tg(
            f"⚠️ <b>Token expiring in {mins} min!</b>\n"
            f"Go to upsideonly.com → Cookie-Editor → export JSON → send to ZapiaPrime.\n"
            f"Bot keeps running until expiry."
        )
        print(f"[WARN] Token expires in {mins} min.")

def fill_positions():
    """Open positions on any symbol not already held."""
    positions  = get_positions()
    open_syms  = {p["symbol"] for p in positions}
    filled     = []
    for sym in STRIKE_SYMBOLS:
        if sym not in open_syms:
            result = place_trade(sym, "buy")
            if result.get("success") or result.get("trade_id"):
                filled.append(sym)
                print(f"  [OPEN] {sym} ${TRADE_AMOUNT:,}")
            else:
                print(f"  [SKIP] {sym} — {result.get('error','?')}")
            time.sleep(0.3)
    return filled

def monitor_and_cycle():
    """Scan open positions; close winners and losers."""
    wins, losses = [], []
    for pos in get_positions():
        pnl  = pos.get("unrealized_pnl_percent", 0)
        sym  = pos["symbol"]
        pid  = pos["id"]
        if pnl >= TAKE_PROFIT_PCT:
            if close_trade(pid).get("success"):
                wins.append((sym, pnl))
                print(f"  [WIN ] {sym} closed at {pnl:+.2f}%")
        elif pnl <= STOP_LOSS_PCT:
            if close_trade(pid).get("success"):
                losses.append((sym, pnl))
                print(f"  [CUT ] {sym} closed at {pnl:+.2f}%")
    return wins, losses

# ─── MAIN ─────────────────────────────────────────────────────────────────────

def run():
    print(f"\n{'='*55}")
    print(f"  UPSIDEONLY STRIKE BOT — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  TP: +{TAKE_PROFIT_PCT}%  |  SL: {STOP_LOSS_PCT}%  |  ${TRADE_AMOUNT:,}/pos")
    print(f"{'='*55}\n")

    check_token_expiry()

    port    = get_portfolio()
    balance = port.get("currentBalance", {}).get("value", 0)
    perf    = port.get("performancePercent", 0)

    exp_dt  = datetime.fromtimestamp(TOKEN_EXP_UTC).strftime("%Y-%m-%d %H:%M")
    tg(
        f"<b>Strike Bot LIVE</b>\n"
        f"Balance: ${balance:,.2f} | Perf: {perf:.2f}%\n"
        f"TP: +{TAKE_PROFIT_PCT}% | SL: {STOP_LOSS_PCT}%\n"
        f"Token expires: {exp_dt} ET\n"
        f"Filling positions..."
    )

    print("[PHASE 1] Filling positions...")
    filled = fill_positions()
    if filled:
        tg(f"Opened: {', '.join(filled)}")

    cycle       = 0
    total_wins  = 0
    total_cuts  = 0
    warned      = False

    print(f"\n[PHASE 2] Monitor loop — every {MONITOR_SECS}s\n")

    while True:
        cycle += 1
        now = datetime.now().strftime("%H:%M:%S")
        print(f"[{now}] Cycle {cycle}")

        # Token expiry check — warn once, then every 10 cycles in danger zone
        remaining = TOKEN_EXP_UTC - int(datetime.now(timezone.utc).timestamp())
        if remaining <= 0:
            tg("🔴 <b>Token EXPIRED — bot stopping.</b> Refresh token to resume.")
            print("[FATAL] Token expired.")
            break
        if remaining <= TOKEN_WARN_SECS and (not warned or cycle % 10 == 0):
            mins = remaining // 60
            tg(f"⚠️ <b>Token expiring in {mins} min!</b> Export cookies from upsideonly.com and send to ZapiaPrime.")
            warned = True

        # Monitor positions
        wins, cuts = monitor_and_cycle()
        total_wins += len(wins)
        total_cuts += len(cuts)

        # Redeploy freed capital
        if wins or cuts:
            time.sleep(1)
            print("  Redeploying...")
            fill_positions()

        # Periodic report
        if cycle % REPORT_EVERY == 0:
            try:
                port    = get_portfolio()
                balance = port.get("currentBalance", {}).get("value", 0)
                perf    = port.get("performancePercent", 0)
                pos     = get_positions()
                lines   = "\n".join(
                    f"  {p['symbol']:10} {p.get('unrealized_pnl_percent',0):+.2f}%"
                    for p in pos
                ) or "  (none)"
                mins_left = remaining // 60
                tg(
                    f"<b>Report — Cycle {cycle}</b>\n"
                    f"Balance: ${balance:,.2f} | Perf: {perf:.2f}%\n"
                    f"Wins: {total_wins} | Cuts: {total_cuts}\n"
                    f"Token: {mins_left} min left\n"
                    f"Positions:\n{lines}"
                )
            except Exception as e:
                print(f"  [REPORT ERR] {e}")

        time.sleep(MONITOR_SECS)

if __name__ == "__main__":
    run()
