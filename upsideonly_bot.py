#!/usr/bin/env python3
"""
UpsideOnly Strike Bot v2.0 — Leaderboard Domination Engine
Fixes:
- Live prices via Finnhub + CoinGecko (no more stale snapshot)
- Cooldown per symbol after a cut (15 min)
- Focus only on high-volatility assets (crypto + vol_tier 1 stocks/commodities)
- Improved TP/SL ratio: +0.5% TP / -0.25% SL (2:1 R/R)
- Skip flat assets (<0.15% move) — no dead positions
- Redeploy freed capital immediately after a win or cut
"""

import requests
import time
from datetime import datetime, timezone

# ─── CONFIG ───────────────────────────────────────────────────────────────────

SESSION_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6IkRjbUUyTkpCWFNyZ2U0RVJGcVcxYyJ9.eyJpc3MiOiJodHRwczovL2F1dGgudXBzaWRlb25seS5jb20vIiwic3ViIjoiZ29vZ2xlLW9hdXRoMnwxMTQ1MjgzNDcxMDA3NzE1NzQzOTgiLCJhdWQiOlsiaHR0cHM6Ly9hcGkudXBzaWRlb25seS5jb20iLCJodHRwczovL2Rldi03b2IyMWJzbHR3enp4am00LnVzLmF1dGgwLmNvbS91c2VyaW5mbyJdLCJpYXQiOjE3Nzk5MjY0MzEsImV4cCI6MTc4MDAxMjgzMSwic2NvcGUiOiJvcGVuaWQgcHJvZmlsZSBlbWFpbCBvZmZsaW5lX2FjY2VzcyIsImF6cCI6IkVIOGlLVDFadXJrNjJYcTNnWUxEM2ZrdlVtM0xSUkpIIn0.hPqZm-FyssR5S41Xk2efOm_MFbS_c8wfhdkHgEW1Usk97wJIV3Mx4KU11CXsC5rgxuk_9ei5OpB8weV8Ys20x_zfuE-7BcKHHes26sW54FHgYqx1Yvu_NHesmCPLvhMuV2j6sPNA3L0SY6ltQftonL25w1F_IU0LFtgPaFbdRIyJw3Yn_ct6Smr5j1CGs2m3cwtPhIrwBfrEmGA-y14Qbwkaz-Ii6UrllwnuAvwcIf1pKQG4-yJkZetTJFommTrWqo2d_h406eoJibSK1t0x4blzgexsLlN0Zxz-tgEy5F9JxRmhAFnQwCMOr084PbBNf88BZtjlgR-ahvFgMtePuA"

TOKEN_EXP_UTC   = 1780012831

TELEGRAM_TOKEN  = "8776802338:AAENyG3ADwNRpk59CuBDnsh8fDGcEuUFVSg"
TELEGRAM_CHAT   = "7135054241"
BASE_URL        = "https://upsideonly.com"
FINNHUB_KEY     = "d86chq1r01qgiu44rds0d86chq1r01qgiu44rdsg"

# ─── STRATEGY PARAMS ──────────────────────────────────────────────────────────
TAKE_PROFIT_PCT  = 0.5    # +0.5% TP
STOP_LOSS_PCT    = -0.25  # -0.25% SL  -> 2:1 R/R
TRADE_AMOUNT     = 10000  # USD per position
MONITOR_SECS     = 30
REPORT_EVERY     = 10
TOKEN_WARN_SECS  = 7200
COOLDOWN_SECS    = 900    # 15 min cooldown after a cut
MIN_MOVE_PCT     = 0.15   # skip asset if 24h change is below this

# Only trade these — high volatility, actually move
STRIKE_SYMBOLS = [
    "BTC/USD", "ETH/USD", "SOL/USD", "XRP/USD", "BNB/USD",
    "NVDA", "TSLA",
    "XAU/USD", "XAG/USD", "WTI/USD",
]

# CoinGecko IDs for crypto
COINGECKO_MAP = {
    "BTC/USD": "bitcoin",
    "ETH/USD": "ethereum",
    "SOL/USD": "solana",
    "XRP/USD": "ripple",
    "BNB/USD": "binancecoin",
}

# Finnhub tickers for stocks
FINNHUB_STOCKS = {
    "NVDA": "NVDA",
    "TSLA": "TSLA",
}

# ─── STATE ────────────────────────────────────────────────────────────────────
cooldown_until = {}
price_cache    = {}
CACHE_TTL      = 60


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def tg(msg):
    try:
        requests.post(
            "https://api.telegram.org/bot{}/sendMessage".format(TELEGRAM_TOKEN),
            json={"chat_id": TELEGRAM_CHAT, "text": msg, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception as e:
        print("[TG] {}".format(e))


def api_headers():
    return {
        "Authorization": "Bearer {}".format(SESSION_TOKEN),
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": BASE_URL,
        "Referer": BASE_URL + "/",
    }


# ─── LIVE PRICE FEED ──────────────────────────────────────────────────────────

def get_crypto_price(symbol):
    cg_id = COINGECKO_MAP.get(symbol)
    if not cg_id:
        return None
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price"
            "?ids={}&vs_currencies=usd&include_24hr_change=true".format(cg_id),
            timeout=8
        )
        data = r.json().get(cg_id, {})
        price = data.get("usd")
        chg   = data.get("usd_24h_change", 0)
        if price:
            return {"price": price, "change_pct": round(chg, 2)}
    except Exception as e:
        print("[CG] {}: {}".format(symbol, e))
    return None


def get_stock_price(symbol):
    ticker = FINNHUB_STOCKS.get(symbol)
    if not ticker:
        return None
    try:
        r = requests.get(
            "https://finnhub.io/api/v1/quote?symbol={}&token={}".format(ticker, FINNHUB_KEY),
            timeout=8
        )
        d = r.json()
        if d.get("c") and d.get("pc"):
            chg = round(((d["c"] - d["pc"]) / d["pc"]) * 100, 2)
            return {"price": d["c"], "change_pct": chg}
    except Exception as e:
        print("[FH] {}: {}".format(symbol, e))
    return None


def get_live_price(symbol):
    now = time.time()
    cached = price_cache.get(symbol)
    if cached and (now - cached.get("fetched_at", 0)) < CACHE_TTL:
        return cached
    data = None
    if symbol in COINGECKO_MAP:
        data = get_crypto_price(symbol)
    elif symbol in FINNHUB_STOCKS:
        data = get_stock_price(symbol)
    if data:
        data["fetched_at"] = now
        price_cache[symbol] = data
    return data


def is_moving(symbol):
    data = get_live_price(symbol)
    if not data:
        return False
    return abs(data.get("change_pct", 0)) >= MIN_MOVE_PCT


# ─── COOLDOWN ─────────────────────────────────────────────────────────────────

def in_cooldown(symbol):
    return time.time() < cooldown_until.get(symbol, 0)


def set_cooldown(symbol):
    cooldown_until[symbol] = time.time() + COOLDOWN_SECS
    print("  [COOL] {} on cooldown for {} min".format(symbol, COOLDOWN_SECS // 60))


# ─── API CALLS ────────────────────────────────────────────────────────────────

def get_portfolio():
    r = requests.get("{}/api/v1/portfolio/summary".format(BASE_URL),
                     headers=api_headers(), timeout=10)
    return r.json()


def get_positions():
    r = requests.get("{}/api/v1/trades".format(BASE_URL),
                     headers=api_headers(), timeout=10)
    return [p for p in r.json().get("positions", []) if p.get("status") == "open"]


def place_trade(symbol, side="buy"):
    r = requests.post(
        "{}/api/v1/trades".format(BASE_URL),
        headers=api_headers(),
        json={"symbol": symbol, "side": side, "amount": TRADE_AMOUNT},
        timeout=10
    )
    return r.json()


def close_trade(trade_id):
    r = requests.post(
        "{}/api/v1/trades/{}/close".format(BASE_URL, trade_id),
        headers=api_headers(),
        timeout=10
    )
    return r.json()


# ─── POSITION MANAGEMENT ──────────────────────────────────────────────────────

def fill_positions():
    try:
        positions = get_positions()
    except Exception as e:
        print("  [ERR] get_positions: {}".format(e))
        return []

    open_syms = {p["symbol"] for p in positions}
    filled = []

    for sym in STRIKE_SYMBOLS:
        if sym in open_syms:
            continue
        if in_cooldown(sym):
            mins_left = int((cooldown_until[sym] - time.time()) / 60)
            print("  [SKIP] {} cooldown {}m".format(sym, mins_left))
            continue
        if not is_moving(sym):
            print("  [SKIP] {} flat/no data".format(sym))
            continue

        data = get_live_price(sym)
        chg_str = "{:+.2f}%".format(data["change_pct"]) if data else "?"

        try:
            result = place_trade(sym, "buy")
        except Exception as e:
            print("  [ERR] place {} : {}".format(sym, e))
            continue

        if result.get("success") or result.get("trade_id") or result.get("id"):
            filled.append(sym)
            print("  [OPEN] {} {} ${:,}".format(sym, chg_str, TRADE_AMOUNT))
        else:
            err = result.get("error", result.get("message", "api err"))
            print("  [SKIP] {} - {}".format(sym, err))
        time.sleep(0.5)

    return filled


def monitor_positions():
    wins, cuts = [], []
    try:
        positions = get_positions()
    except Exception as e:
        print("  [ERR] monitor: {}".format(e))
        return wins, cuts

    for pos in positions:
        pnl = pos.get("unrealized_pnl_percent", 0)
        sym = pos["symbol"]
        pid = pos["id"]

        if pnl >= TAKE_PROFIT_PCT:
            try:
                result = close_trade(pid)
                if result.get("success") or result.get("id"):
                    wins.append((sym, pnl))
                    print("  [WIN ] {} +{:.2f}% TP hit".format(sym, pnl))
            except Exception as e:
                print("  [ERR] close win {}: {}".format(sym, e))

        elif pnl <= STOP_LOSS_PCT:
            try:
                result = close_trade(pid)
                if result.get("success") or result.get("id"):
                    cuts.append((sym, pnl))
                    set_cooldown(sym)
                    print("  [CUT ] {} {:.2f}% SL hit -> cooldown".format(sym, pnl))
            except Exception as e:
                print("  [ERR] close cut {}: {}".format(sym, e))

    return wins, cuts


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def check_token():
    now = int(datetime.now(timezone.utc).timestamp())
    remaining = TOKEN_EXP_UTC - now
    if remaining <= 0:
        tg("TOKEN EXPIRED - Bot halted. Export cookies from upsideonly.com -> send to ZapiaPrime.")
        raise SystemExit(1)
    return remaining


def run():
    print("=" * 55)
    print("  UPSIDEONLY STRIKE BOT v2.0")
    print("  {}".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    print("  TP: +{}%  SL: {}%  R/R: 2:1".format(TAKE_PROFIT_PCT, STOP_LOSS_PCT))
    print("  Cooldown: {}m after cut".format(COOLDOWN_SECS // 60))
    print("  Symbols: {}".format(", ".join(STRIKE_SYMBOLS)))
    print("=" * 55)

    remaining = check_token()
    mins_left = remaining // 60

    port    = get_portfolio()
    balance = port.get("currentBalance", {}).get("value", 0)
    perf    = port.get("performancePercent", 0)
    exp_dt  = datetime.fromtimestamp(TOKEN_EXP_UTC).strftime("%Y-%m-%d %H:%M")

    tg(
        "<b>Strike Bot v2.0 LIVE</b>\n"
        "Balance: ${:,.2f} | Perf: {:.2f}%\n"
        "TP: +{}% | SL: {}% | R/R: 2:1\n"
        "Cooldown: {}m on cuts | Skip flat less than {}%\n"
        "Token: {} min left ({} ET)\n"
        "Filling positions with live prices...".format(
            balance, perf,
            TAKE_PROFIT_PCT, STOP_LOSS_PCT,
            COOLDOWN_SECS // 60, MIN_MOVE_PCT,
            mins_left, exp_dt
        )
    )

    print("\n[PHASE 1] Filling positions...")
    filled = fill_positions()
    if filled:
        tg("Opened: {}".format(", ".join(filled)))
        print("  Opened: {}".format(filled))
    else:
        print("  No positions opened yet.")

    cycle      = 0
    total_wins = 0
    total_cuts = 0
    warned     = False

    print("\n[PHASE 2] Monitor loop every {}s\n".format(MONITOR_SECS))

    while True:
        cycle += 1
        now_str = datetime.now().strftime("%H:%M:%S")
        print("[{}] Cycle {}".format(now_str, cycle))

        remaining = TOKEN_EXP_UTC - int(datetime.now(timezone.utc).timestamp())
        if remaining <= 0:
            tg("TOKEN EXPIRED - Bot stopping.")
            break
        if remaining <= TOKEN_WARN_SECS and not warned:
            tg("Token expiring in {} min! Export cookies -> send to ZapiaPrime.".format(remaining // 60))
            warned = True

        wins, cuts = monitor_positions()
        total_wins += len(wins)
        total_cuts += len(cuts)

        if wins or cuts:
            time.sleep(1)
            new = fill_positions()
            if new:
                print("  Redeployed: {}".format(new))

        if cycle % REPORT_EVERY == 0:
            try:
                port    = get_portfolio()
                balance = port.get("currentBalance", {}).get("value", 0)
                perf    = port.get("performancePercent", 0)
                pos     = get_positions()
                lines   = "\n".join(
                    "  {:10} {:+.2f}%".format(p["symbol"], p.get("unrealized_pnl_percent", 0))
                    for p in pos
                ) or "  (none)"
                cds = [s for s in cooldown_until if in_cooldown(s)]
                cd_str = "\nCooldowns: {}".format(", ".join(cds)) if cds else ""

                tg(
                    "<b>Report - Cycle {}</b>\n"
                    "Balance: ${:,.2f} | Perf: {:+.2f}%\n"
                    "Wins: {} | Cuts: {}\n"
                    "Token: {} min left\n"
                    "Positions:\n{}{}".format(
                        cycle, balance, perf,
                        total_wins, total_cuts,
                        remaining // 60, lines, cd_str
                    )
                )
            except Exception as e:
                print("  [REPORT ERR] {}".format(e))

        time.sleep(MONITOR_SECS)


if __name__ == "__main__":
    run()
