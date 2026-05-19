"""
Configuration & constants for Meme Insider Tracker.
Free RPCs + API endpoints. No API keys required.
"""

# --- Dexscreener (free, no key) ---
DEXSCREENER_BASE = "https://api.dexscreener.com"
DEXSCREENER_NEW_PAIRS = f"{DEXSCREENER_BASE}/token-profiles/latest/v1"
DEXSCREENER_SEARCH = f"{DEXSCREENER_BASE}/latest/dex/search"
DEXSCREENER_PAIRS = f"{DEXSCREENER_BASE}/latest/dex/pairs"
DEXSCREENER_TOKENS = f"{DEXSCREENER_BASE}/latest/dex/tokens"

# --- Chain RPCs (free public endpoints) ---
CHAIN_RPCS = {
    "ethereum": "https://ethereum-rpc.publicnode.com",
    "bsc": "https://bsc-rpc.publicnode.com",
    "base": "https://mainnet.base.org",
    "arbitrum": "https://arb1.arbitrum.io/rpc",
    "polygon": "https://polygon-bor-rpc.publicnode.com",
    "avalanche": "https://avalanche-c-chain-rpc.publicnode.com",
}

# Solana RPCs (free)
SOLANA_RPC = "https://api.mainnet-beta.solana.com"

# --- Chain IDs for Dexscreener ---
SUPPORTED_CHAINS = [
    "ethereum", "bsc", "base", "arbitrum",
    "polygon", "avalanche", "solana",
]

# --- Insider detection thresholds ---
INSIDER_CONFIG = {
    "early_buyer_blocks": 10,        # first N blocks after liquidity add
    "whale_threshold_usd": 10_000,   # min USD to flag as whale buy
    "same_funder_min_wallets": 3,    # min wallets from same funder = cluster
    "dev_sell_alert_pct": 10,        # alert if dev sells >X% of supply
    "sniper_max_block_delay": 2,     # bought within N blocks = sniper
    "min_liquidity_usd": 1_000,      # skip dust pairs
    "max_token_age_hours": 6,        # only track tokens < 6 hours old
}

# --- Database ---
DB_PATH = "data/meme_tracker.db"

# --- Refresh intervals (seconds) ---
SCAN_INTERVAL = 30          # scan for new pairs
ANALYSIS_INTERVAL = 60      # re-analyze tokens
DASHBOARD_REFRESH = 10      # streamlit refresh
