"""
UpsideOnly Bot — Main Loop
Runs continuously, scanning for signals every 5 minutes.
Reports to Telegram. Executes via Nexus Relay → NexusClaw.
"""

import time
import sys
from datetime import datetime
from signal_engine import analyze_snapshot, send_telegram, format_signal_report
from executor import run_cycle

SCAN_INTERVAL = 300  # 5 minutes between scans
CYCLE_COUNT = 0

def main():
    global CYCLE_COUNT
    send_telegram(
        "🚀 <b>UpsideOnly Bot ONLINE</b>\n"
        f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M EDT')}\n"
        f"Markets: 25 | Scan interval: 5min\n"
        f"Strategy: Momentum + Mean Reversion\n"
        f"Min conviction threshold: 70%"
    )

    print("UpsideOnly Bot v1.0 — LIVE")
    print(f"Scanning 25 markets every {SCAN_INTERVAL}s\n")

    while True:
        try:
            CYCLE_COUNT += 1
            now = datetime.now().strftime("%H:%M:%S")
            print(f"\n[{now}] Cycle #{CYCLE_COUNT} — Scanning...")

            signals = analyze_snapshot()

            if signals:
                print(f"  {len(signals)} signals found. Top: {signals[0]['symbol']} {signals[0]['direction']} @ {signals[0]['conviction']}%")
                run_cycle(signals)
            else:
                print("  No signals above threshold.")

            # Every 6 cycles (30 min) send a status heartbeat
            if CYCLE_COUNT % 6 == 0:
                send_telegram(
                    f"💓 <b>UpsideOnly Bot Heartbeat</b>\n"
                    f"Cycle #{CYCLE_COUNT} | {datetime.now().strftime('%H:%M EDT')}\n"
                    f"Status: Running ✅"
                )

            time.sleep(SCAN_INTERVAL)

        except KeyboardInterrupt:
            print("\nBot stopped by user.")
            send_telegram("🛑 <b>UpsideOnly Bot STOPPED</b> — manual shutdown.")
            sys.exit(0)
        except Exception as e:
            print(f"  [ERROR] {e}")
            send_telegram(f"⚠️ <b>UpsideOnly Bot Error</b>\n{str(e)}")
            time.sleep(60)  # Wait 1 min before retry


if __name__ == "__main__":
    main()
