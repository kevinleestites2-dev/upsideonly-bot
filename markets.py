# UpsideOnly Bot — Market Registry
# All 25 available markets mapped with asset class and volatility tier

MARKETS = [
    # === HIGH VOLATILITY — Primary targets ===
    {"symbol": "NVDA",    "name": "NVIDIA Corp.",              "class": "stock",     "vol_tier": 1},
    {"symbol": "WTI/USD", "name": "Crude Oil",                 "class": "commodity", "vol_tier": 1},
    {"symbol": "XAG/USD", "name": "Silver / US Dollar",        "class": "commodity", "vol_tier": 1},
    {"symbol": "BTC/USD", "name": "Bitcoin / US Dollar",       "class": "crypto",    "vol_tier": 1},
    {"symbol": "XAU/USD", "name": "Gold / US Dollar",          "class": "commodity", "vol_tier": 1},
    {"symbol": "NG",      "name": "Natural Gas",               "class": "commodity", "vol_tier": 1},
    {"symbol": "TSLA",    "name": "Tesla Inc.",                 "class": "stock",     "vol_tier": 1},

    # === MEDIUM VOLATILITY — Secondary targets ===
    {"symbol": "ETH/USD", "name": "Ethereum / US Dollar",      "class": "crypto",    "vol_tier": 2},
    {"symbol": "BNB/USD", "name": "Binance Coin / US Dollar",  "class": "crypto",    "vol_tier": 2},
    {"symbol": "SOL/USD", "name": "Solana / US Dollar",        "class": "crypto",    "vol_tier": 2},
    {"symbol": "XRP/USD", "name": "XRP / US Dollar",           "class": "crypto",    "vol_tier": 2},
    {"symbol": "AMZN",    "name": "Amazon.com Inc.",            "class": "stock",     "vol_tier": 2},
    {"symbol": "META",    "name": "Meta Platforms Inc.",        "class": "stock",     "vol_tier": 2},
    {"symbol": "AAPL",    "name": "Apple Inc.",                 "class": "stock",     "vol_tier": 2},
    {"symbol": "QQQ",     "name": "Nasdaq 100 ETF",             "class": "etf",       "vol_tier": 2},
    {"symbol": "HG",      "name": "Copper",                    "class": "commodity", "vol_tier": 2},

    # === LOWER VOLATILITY — Confirmation/hedge ===
    {"symbol": "SPY",     "name": "S&P 500 ETF",               "class": "etf",       "vol_tier": 3},
    {"symbol": "DIA",     "name": "Dow Jones ETF",             "class": "etf",       "vol_tier": 3},
    {"symbol": "EWJ",     "name": "Japan Equity ETF",          "class": "etf",       "vol_tier": 3},
    {"symbol": "EWU",     "name": "UK Equity ETF",             "class": "etf",       "vol_tier": 3},
    {"symbol": "USD/JPY", "name": "US Dollar / Japanese Yen",  "class": "forex",     "vol_tier": 3},
    {"symbol": "GBP/USD", "name": "British Pound / US Dollar", "class": "forex",     "vol_tier": 3},
    {"symbol": "EUR/USD", "name": "Euro / US Dollar",          "class": "forex",     "vol_tier": 3},
    {"symbol": "AUD/USD", "name": "Australian Dollar / US Dollar", "class": "forex", "vol_tier": 3},
    {"symbol": "USD/CHF", "name": "US Dollar / Swiss Franc",   "class": "forex",     "vol_tier": 3},
]

# Primary hit list — bot focuses here first
TIER_1 = [m for m in MARKETS if m["vol_tier"] == 1]
TIER_2 = [m for m in MARKETS if m["vol_tier"] == 2]
TIER_3 = [m for m in MARKETS if m["vol_tier"] == 3]

# Current market snapshot from user (2026-05-27 10:30 EDT)
SNAPSHOT = {
    "NVDA":    {"price": 209.77, "change_pct": -2.37, "volume": "2.5M"},
    "WTI/USD": {"price": 89.80,  "change_pct": -4.06, "volume": "-"},
    "XAG/USD": {"price": 74.63,  "change_pct": -3.03, "volume": "-"},
    "BTC/USD": {"price": 74787,  "change_pct": -1.45, "volume": "-"},
    "XAU/USD": {"price": 4441.68,"change_pct": -1.46, "volume": "-"},
    "NG":      {"price": 8.12,   "change_pct": -2.23, "volume": "48.5K"},
    "TSLA":    {"price": 436.17, "change_pct": +0.59, "volume": "496.8K"},
    "ETH/USD": {"price": 2055.03,"change_pct": -0.89, "volume": "-"},
    "SOL/USD": {"price": 83.28,  "change_pct": -0.37, "volume": "-"},
    "XRP/USD": {"price": 1.32,   "change_pct": -0.75, "volume": "-"},
    "AMZN":    {"price": 269.68, "change_pct": +1.65, "volume": "950.8K"},
    "AAPL":    {"price": 310.97, "change_pct": +0.86, "volume": "975.1K"},
    "META":    {"price": 615.61, "change_pct": +0.53, "volume": "127.8K"},
    "QQQ":     {"price": 726.01, "change_pct": -0.58, "volume": "770.8K"},
    "SPY":     {"price": 749.65, "change_pct": -0.12, "volume": "695.8K"},
    "DIA":     {"price": 508.00, "change_pct": +0.54, "volume": "91.7K"},
    "HG":      {"price": 31.34,  "change_pct": -1.00, "volume": "4.2K"},
    "EWJ":     {"price": 92.12,  "change_pct": -0.84, "volume": "178.3K"},
    "EWU":     {"price": 47.24,  "change_pct": -0.38, "volume": "13.9K"},
    "USD/JPY": {"price": 159.41, "change_pct": +0.06, "volume": "-"},
    "GBP/USD": {"price": 1.34,   "change_pct": +0.01, "volume": "-"},
    "EUR/USD": {"price": 1.16,   "change_pct": +0.13, "volume": "-"},
    "AUD/USD": {"price": 0.7136, "change_pct": -0.43, "volume": "-"},
    "USD/CHF": {"price": 0.7851, "change_pct": -0.08, "volume": "-"},
    "BNB/USD": {"price": 651.42, "change_pct": -0.72, "volume": "-"},
}
