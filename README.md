# Meme Insider Tracker

> Real-time insider trade detection for meme coins across **all major chains** — 100% free.

Tired of getting rugged? This tool automatically scans new meme coins and detects insider patterns before you become their exit liquidity.

**Live App:** [memetracker.streamlit.app](https://memetracker.streamlit.app)

---

## Supported Chains

| Chain | Status |
|-------|--------|
| Ethereum | OK |
| BSC (BNB Chain) | OK |
| Base | OK |
| Arbitrum | OK |
| Polygon | OK |
| Avalanche | OK |
| Solana | OK |

## Detection Methods

| Detection | Chain | Description |
|-----------|-------|-------------|
| **Sniper (Early Buy)** | EVM | Wallets that bought in the very first block — likely bots or insiders |
| **Dev Large Holding** | EVM | Developer still holds a large % of supply — rug pull risk |
| **Wallet Cluster** | EVM | Multiple wallets funded by the same source — coordinated insiders |
| **Bundled Buy** | Solana | Many wallets bought in a single transaction — sniping tactic |
| **Whale Dominance** | All | One wallet holds >10% of supply — can dump anytime |
| **Early Buyer** | Solana | First wallets to buy a new token |

## Dashboard

| Tab | Function |
|-----|----------|
| **Tokens** | All discovered meme coins (price, liquidity, market cap, volume) |
| **Insider Activity** | Detected suspicious events with full details |
| **Wallet Clusters** | Groups of wallets linked to the same funder |
| **Scan & Analyze** | Manual keyword search + analyze any token by address |

## Quick Start

```bash
git clone https://github.com/reodkt/meme-insider-tracker.git
cd meme-insider-tracker
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Open http://localhost:8501

## Deploy Online (Free)

1. Fork this repo to your GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Select repo, branch `master`, main file `streamlit_app.py`
4. Click Deploy — done!

## Project Structure

```
meme-insider-tracker/
├── streamlit_app.py        # Main web app (Streamlit)
├── scanner.py              # CLI scanner (terminal mode)
├── requirements.txt
├── core/
│   ├── config.py           # RPC endpoints & thresholds
│   └── database.py         # SQLite storage
├── chains/
│   ├── dexscreener.py      # Dexscreener API (free, no key)
│   ├── evm.py              # EVM connector (web3.py)
│   └── solana_chain.py     # Solana connector
├── analyzers/
│   └── insider_detector.py # Insider detection engine
└── dashboard/
    └── app.py              # Dashboard (alternative entry)
```

## Configuration

Edit `core/config.py`:

```python
INSIDER_CONFIG = {
    "early_buyer_blocks": 10,        # first N blocks = sniper
    "whale_threshold_usd": 10_000,   # min USD to flag whale
    "same_funder_min_wallets": 3,    # min wallets from same funder
    "dev_sell_alert_pct": 10,        # alert if dev holds >X%
    "sniper_max_block_delay": 2,     # block delay = sniper
    "min_liquidity_usd": 1_000,      # skip dust tokens
    "max_token_age_hours": 72,       # only track new tokens
}
```

## How It Works

1. **Scan** — Dexscreener is searched with meme keywords (pepe, doge, bonk, etc.)
2. **Filter** — Only tokens with sufficient liquidity & age < 72h
3. **Analyze** — On-chain check: who bought first, who's the dev, any clusters?
4. **Alert** — Findings saved with severity levels (High / Medium / Low)
5. **Dashboard** — Real-time visualization in the web app

---

## ☕ Buy Me a Coffee

This tool is free & open-source. If it helped you, consider sending a small tip:

| Network | Address |
|---------|---------|
| **Solana (SOL)** | `2vMBrEcTd85b1CUwcbU6f3PuKmdUCHkM8kq6mMVp82Ca` |
| **ETH / BSC / Base / Arbitrum** | `0x2D36d2658B46C509Ecc9BB68D7844bb3ef9D337a` |

Any amount is appreciated. Thank you, fren!

---

## Notes

- All APIs are **free & keyless** (Dexscreener + public RPCs)
- Public RPCs have rate limits — scanner includes built-in throttling
- For production, consider paid RPCs (Alchemy, Helius)
- This is a **research & analytics tool** — not financial advice

## License

MIT
