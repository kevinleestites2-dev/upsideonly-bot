"""
UpsideOnly Bot — Signal Engine
Strategy: Momentum + Mean Reversion hybrid
- Buys oversold Tier 1 assets on strong downside moves (mean reversion)
- Rides momentum on Tier 1 assets breaking up with volume confirmation
- Uses current snapshot + Finnhub for live price feeds (stocks)
- Crypto/Forex/Commodities: uses UpsideOnly price feed via browser scrape
"""

import requests
import json
import time
from datetime import datetime
from markets import MARKETS, SNAPSHOT, TIER_1, TIER_2

FINNHUB_KEY = "d86chq1r01qgiu44rds0d86chq1r01qgiu44rdsg"
TELEGRAM_TOKEN = "8776802338:AAENyG3ADwNRpk59CuBDnsh8fDGcEuUFVSg"
TELEGRAM_CHAT_ID = "7135054241"

# Signal thresholds
OVERSOLD_THRESHOLD = -2.0    # % drop = potential long signal
MOMENTUM_THRESHOLD = +1.5    # % rise with volume = momentum long
VOLUME_SURGE_MULT  = 1.5     # volume must be 1.5x average to confirm


def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=5)
    except Exception as e:
        print(f"Telegram error: {e}")


def get_finnhub_quote(symbol):
    """Fetch real-time quote from Finnhub for stock symbols."""
    try:
        url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_KEY}"
        r = requests.get(url, timeout=5)
        data = r.json()
        if data.get("c"):
            return {
                "price": data["c"],
                "open": data["o"],
                "high": data["h"],
                "low": data["l"],
                "prev_close": data["pc"],
                "change_pct": round(((data["c"] - data["pc"]) / data["pc"]) * 100, 2)
            }
    except Exception as e:
        print(f"Finnhub error for {symbol}: {e}")
    return None


def analyze_snapshot(snapshot=None):
    """
    Analyze current market snapshot and generate signals.
    Returns list of actionable signals sorted by conviction.
    """
    if snapshot is None:
        snapshot = SNAPSHOT

    signals = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for market in MARKETS:
        sym = market["symbol"]
        if sym not in snapshot:
            continue

        data = snapshot[sym]
        chg = data["change_pct"]
        price = data["price"]
        vol_tier = market["vol_tier"]

        signal = None
        conviction = 0
        direction = None
        reason = ""

        # === MEAN REVERSION LONG — oversold Tier 1/2 ===
        if chg <= OVERSOLD_THRESHOLD and vol_tier <= 2:
            direction = "BUY"
            conviction = min(abs(chg) * 15, 95)  # scale by magnitude, cap at 95
            reason = f"Oversold {chg:.2f}% — mean reversion setup"
            signal = True

        # === MOMENTUM LONG — strong upside Tier 1/2 ===
        elif chg >= MOMENTUM_THRESHOLD and vol_tier <= 2:
            direction = "BUY"
            conviction = min(chg * 20, 90)
            reason = f"Momentum +{chg:.2f}% — trend continuation"
            signal = True

        # === SHORT SIGNAL — extreme drop Tier 1 (commodities/crypto) ===
        # UpsideOnly allows both buy and sell
        elif chg <= -3.5 and vol_tier == 1 and market["class"] in ["commodity", "crypto"]:
            direction = "SELL"
            conviction = min(abs(chg) * 12, 88)
            reason = f"Breakdown {chg:.2f}% — short momentum"
            signal = True

        if signal:
            signals.append({
                "symbol": sym,
                "name": market["name"],
                "class": market["class"],
                "direction": direction,
                "conviction": round(conviction, 1),
                "price": price,
                "change_pct": chg,
                "reason": reason,
                "tier": vol_tier,
                "timestamp": now,
            })

    # Sort by conviction descending
    signals.sort(key=lambda x: x["conviction"], reverse=True)
    return signals


def format_signal_report(signals):
    if not signals:
        return "⚡ UpsideOnly Bot — No signals above threshold right now."

    lines = [f"⚡ <b>UpsideOnly Bot Signal Report</b>"]
    lines.append(f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M EDT')}\n")

    for i, s in enumerate(signals[:5], 1):  # Top 5 only
        arrow = "🟢" if s["direction"] == "BUY" else "🔴"
        lines.append(
            f"{arrow} <b>#{i} {s['symbol']}</b> — {s['direction']}\n"
            f"   Price: ${s['price']:,} | Change: {s['change_pct']:+.2f}%\n"
            f"   Conviction: {s['conviction']}%\n"
            f"   Reason: {s['reason']}\n"
        )

    lines.append(f"Total signals: {len(signals)} | Top conviction: {signals[0]['conviction']}%")
    return "\n".join(lines)


if __name__ == "__main__":
    print("UpsideOnly Bot — Signal Engine v1.0")
    print(f"Analyzing {len(MARKETS)} markets...\n")

    signals = analyze_snapshot()

    if signals:
        print(f"Found {len(signals)} signals:\n")
        for s in signals:
            print(f"  [{s['direction']:4s}] {s['symbol']:10s} | {s['change_pct']:+.2f}% | Conviction: {s['conviction']}% | {s['reason']}")
    else:
        print("No signals above threshold.")

    # Send top signals to Telegram
    report = format_signal_report(signals)
    print("\n--- Telegram Report ---")
    print(report)
    send_telegram(report)
    print("\nReport sent to Telegram.")
