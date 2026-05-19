# Meme Insider Tracker

Real-time insider trade detection for meme coins across **all major chains**.

## Supported Chains
- **EVM**: Ethereum, BSC, Base, Arbitrum, Polygon, Avalanche
- **Non-EVM**: Solana

## Features

### Detection Methods
| Method | Chain | Description |
|--------|-------|-------------|
| Early Sniper | EVM | Wallets that bought in the first N blocks after launch |
| Dev Wallet | EVM | Developer holds large % of total supply |
| Wallet Cluster | EVM | Multiple wallets funded by the same source |
| Bundled Buys | Solana | Multiple buys packed in the same transaction/slot |
| Whale Tracking | All | Large holders with >10% of supply |
| Early Buyers | Solana | First wallets to buy a new token |

### Data Sources
- **Dexscreener API** (free, no key) — new pair discovery, price/volume data
- **Public RPCs** (free) — on-chain transaction analysis
- **SQLite** — local storage, no external DB needed

## Quick Start

### 1. Install
```bash
cd meme-insider-tracker
pip install -r requirements.txt
```

### 2. Run Scanner (Terminal)
```bash
python scanner.py
```
The scanner will:
- Scan Dexscreener for new meme tokens every 30s
- Analyze each token for insider patterns
- Store results in SQLite

### 3. Run Dashboard (Web UI)
```bash
streamlit run dashboard/app.py
```
Open http://localhost:8501 in your browser.

## Project Structure
```
meme-insider-tracker/
├── scanner.py              # Main scanner loop
├── requirements.txt
├── core/
│   ├── config.py           # Configuration & thresholds
│   └── database.py         # SQLite storage layer
├── chains/
│   ├── dexscreener.py      # Dexscreener API client
│   ├── evm.py              # EVM chain connector (web3.py)
│   └── solana_chain.py     # Solana chain connector
├── analyzers/
│   └── insider_detector.py # Insider detection engine
├── dashboard/
│   └── app.py              # Streamlit dashboard
└── data/
    └── meme_tracker.db     # SQLite database (auto-created)
```

## Configuration

Edit `core/config.py` to adjust:

```python
INSIDER_CONFIG = {
    "early_buyer_blocks": 10,        # first N blocks = sniper
    "whale_threshold_usd": 10_000,   # min USD to flag whale
    "same_funder_min_wallets": 3,    # min wallets from same funder
    "dev_sell_alert_pct": 10,        # alert if dev holds >X%
    "sniper_max_block_delay": 2,     # blocks delay = sniper
    "min_liquidity_usd": 1_000,      # skip dust pairs
    "max_token_age_hours": 72,       # only track fresh tokens
}
```

## Dashboard Features
- **Insider Events** — table + charts of all detected insider activity
- **Tracked Tokens** — all discovered meme tokens with price/volume
- **Wallet Clusters** — detected coordinated wallet groups
- **Live Scanner** — manual token lookup + scanner status

## How It Works

1. **Discovery**: Scanner queries Dexscreener with meme-related keywords (pepe, doge, bonk, etc.)
2. **Filtering**: Only tokens with sufficient liquidity and age < 72h are tracked
3. **Analysis**:
   - EVM: Fetches early Transfer events, identifies snipers, checks dev holdings, detects wallet clusters
   - Solana: Scans transaction history for early buyers, detects bundled buys in same slot
4. **Alerting**: All findings stored in DB with severity levels (high/medium/low)
5. **Visualization**: Streamlit dashboard shows real-time results

## Notes
- All APIs used are **free and keyless** (Dexscreener + public RPCs)
- Public RPCs have rate limits — the scanner includes built-in throttling
- For production use, consider paid RPC providers (Alchemy, Helius) for better reliability
- This is an **analytics/research tool** — not financial advice
