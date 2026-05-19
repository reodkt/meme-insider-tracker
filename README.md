# Meme Insider Tracker

> Deteksi real-time aktivitas insider & whale di meme coin — semua chain, 100% gratis.

Bosan kena rug pull? Tool ini otomatis memindai meme coin baru dan mendeteksi pola insider sebelum kamu jadi exit liquidity mereka.

**Live Demo:** [meme-insider-tracker.streamlit.app](https://meme-insider-tracker.streamlit.app) *(deploy sendiri via Streamlit Cloud)*

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

## Fitur Deteksi

| Deteksi | Chain | Penjelasan |
|---------|-------|------------|
| **Sniper Awal** | EVM | Wallet yang beli di block pertama — kemungkinan bot/insider |
| **Dev Pegang Banyak** | EVM | Developer masih hold % besar supply — risiko rug pull |
| **Grup Wallet** | EVM | Beberapa wallet didanai dari 1 sumber — koordinasi insider |
| **Pembelian Bundel** | Solana | Banyak wallet beli dalam 1 transaksi — taktik sniping |
| **Whale Dominan** | Semua | 1 wallet pegang >10% supply — bisa dump kapan saja |
| **Pembeli Awal** | Solana | Wallet pertama yang beli token baru |

## Dashboard Web

| Tab | Fungsi |
|-----|--------|
| **Aktivitas Insider** | Daftar semua event mencurigakan + chart distribusi |
| **Token Terpantau** | Semua meme coin yang ditemukan (harga, likuiditas, market cap) |
| **Grup Wallet** | Wallet cluster dari 1 pendana — indikasi koordinasi |
| **Scan & Analisis** | Scan manual + cek token spesifik dengan 1 klik |

## Quick Start

### 1. Install
```bash
git clone https://github.com/reodkt/meme-insider-tracker.git
cd meme-insider-tracker
pip install -r requirements.txt
```

### 2. Jalankan Dashboard
```bash
streamlit run dashboard/app.py
```
Buka http://localhost:8501

### 3. Atau Jalankan Scanner (Terminal mode)
```bash
python scanner.py
```

## Deploy Online (Gratis)

1. Fork / push repo ini ke GitHub kamu
2. Buka [share.streamlit.io](https://share.streamlit.io)
3. Pilih repo, branch `master`, main file `dashboard/app.py`
4. Klik Deploy — selesai!

## Project Structure
```
meme-insider-tracker/
├── scanner.py              # Scanner loop (terminal)
├── requirements.txt
├── .streamlit/config.toml  # Theme config
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
    └── app.py              # Streamlit web dashboard
```

## Konfigurasi

Edit `core/config.py`:

```python
INSIDER_CONFIG = {
    "early_buyer_blocks": 10,        # block pertama = sniper
    "whale_threshold_usd": 10_000,   # min USD untuk flag whale
    "same_funder_min_wallets": 3,    # min wallet dari funder sama
    "dev_sell_alert_pct": 10,        # alert jika dev hold >X%
    "sniper_max_block_delay": 2,     # delay block = sniper
    "min_liquidity_usd": 1_000,      # skip token kecil
    "max_token_age_hours": 72,       # hanya track token baru
}
```

## Cara Kerja

1. **Scan** — Dexscreener dicari dengan keyword meme (pepe, doge, bonk, dll)
2. **Filter** — Hanya token dengan likuiditas cukup & umur < 72 jam
3. **Analisis** — Cek on-chain: siapa beli pertama, siapa dev, ada cluster?
4. **Alert** — Semua temuan disimpan dengan level bahaya (Tinggi/Waspada/Info)
5. **Dashboard** — Visualisasi real-time di web

---

## ☕ Traktir Saya Kopi

Tool ini gratis & open-source. Kalau kamu merasa terbantu, bisa beliin saya kopi sebagai apresiasi:

| Network | Alamat |
|---------|--------|
| **Solana (SOL)** | `2vMBrEcTd85b1CUwcbU6f3PuKmdUCHkM8kq6mMVp82Ca` |
| **Ethereum / EVM** | `0x2D36d2658B46C509Ecc9BB68D7844bb3ef9D337a` |

Berapapun sangat berarti. Terima kasih, fren!

---

## Notes
- Semua API **gratis & tanpa key** (Dexscreener + public RPCs)
- Public RPC ada rate limit — scanner sudah include throttling
- Untuk production, pertimbangkan RPC berbayar (Alchemy, Helius)
- Ini tool **riset & analisis** — bukan saran finansial

## License
MIT
