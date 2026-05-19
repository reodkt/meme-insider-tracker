"""
Meme Insider Tracker — Streamlit Web Dashboard
Deteksi aktivitas insider pada meme coin di semua chain.
"""

import streamlit as st
import pandas as pd
import json
import time
import threading
from datetime import datetime, timedelta

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import (
    init_db, get_recent_events, get_tracked_tokens, get_clusters,
    upsert_token, get_db
)
from core.config import SUPPORTED_CHAINS, INSIDER_CONFIG
from chains.dexscreener import scan_new_memes, search_meme_tokens
from analyzers.insider_detector import analyze_token

# ─────────────────────────── PAGE CONFIG ───────────────────────────
st.set_page_config(
    page_title="Meme Insider Tracker",
    page_icon="https://em-content.zobj.net/source/twitter/408/detective_1f575-fe0f.png",
    layout="wide",
    initial_sidebar_state="expanded",
)
init_db()

# ─────────────────────────── CUSTOM CSS ────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* Header gradient */
.main-header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 2rem 2.5rem; border-radius: 16px; margin-bottom: 1.5rem;
    color: white;
}
.main-header h1 { font-size: 2rem; font-weight: 800; margin: 0; }
.main-header p { opacity: 0.9; margin: 0.3rem 0 0 0; font-size: 1rem; }

/* Metric cards */
.metric-card {
    background: linear-gradient(135deg, #1e1e2f 0%, #2d2d44 100%);
    border: 1px solid #3d3d5c; border-radius: 14px;
    padding: 1.2rem 1.5rem; text-align: center;
}
.metric-card .number { font-size: 2rem; font-weight: 800; color: #a78bfa; }
.metric-card .label { font-size: 0.85rem; color: #9ca3af; margin-top: 0.2rem; }

/* Severity badges */
.badge-high {
    background: #dc2626; color: white; padding: 3px 10px;
    border-radius: 20px; font-size: 0.75rem; font-weight: 700;
}
.badge-medium {
    background: #f59e0b; color: #1a1a2e; padding: 3px 10px;
    border-radius: 20px; font-size: 0.75rem; font-weight: 700;
}
.badge-low {
    background: #10b981; color: white; padding: 3px 10px;
    border-radius: 20px; font-size: 0.75rem; font-weight: 700;
}

/* Chain badges */
.chain-badge {
    display: inline-block; padding: 2px 8px; border-radius: 6px;
    font-size: 0.72rem; font-weight: 700; text-transform: uppercase;
}
.chain-ethereum { background: #627eea22; color: #627eea; border: 1px solid #627eea44; }
.chain-bsc { background: #f3ba2f22; color: #f3ba2f; border: 1px solid #f3ba2f44; }
.chain-solana { background: #9945ff22; color: #9945ff; border: 1px solid #9945ff44; }
.chain-base { background: #0052ff22; color: #0052ff; border: 1px solid #0052ff44; }
.chain-arbitrum { background: #28a0f022; color: #28a0f0; border: 1px solid #28a0f044; }
.chain-polygon { background: #8247e522; color: #8247e5; border: 1px solid #8247e544; }
.chain-avalanche { background: #e8414222; color: #e84142; border: 1px solid #e8414244; }

/* Event cards */
.event-card {
    background: #1a1a2e; border: 1px solid #2d2d5c;
    border-radius: 12px; padding: 1rem 1.2rem; margin-bottom: 0.8rem;
    border-left: 4px solid #a78bfa;
}
.event-card.high { border-left-color: #dc2626; }
.event-card.medium { border-left-color: #f59e0b; }
.event-card.low { border-left-color: #10b981; }

/* Token row */
.token-row {
    background: #12121f; border: 1px solid #1e1e35;
    border-radius: 10px; padding: 0.8rem 1rem; margin-bottom: 0.5rem;
    display: flex; align-items: center; gap: 1rem;
}

/* Coffee / Donate section */
.donate-box {
    background: linear-gradient(135deg, #1a1a2e 0%, #0f172a 50%, #1e1b4b 100%);
    border: 1px solid #a78bfa44;
    border-radius: 20px; padding: 2.5rem 2rem; margin: 2rem 0;
    text-align: center; position: relative; overflow: hidden;
}
.donate-box::before {
    content: ''; position: absolute; top: -50%; left: -50%;
    width: 200%; height: 200%;
    background: radial-gradient(circle at 30% 50%, #a78bfa11 0%, transparent 50%),
                radial-gradient(circle at 70% 50%, #667eea11 0%, transparent 50%);
    animation: pulse-bg 6s ease-in-out infinite;
}
@keyframes pulse-bg {
    0%, 100% { opacity: 0.5; }
    50% { opacity: 1; }
}
.donate-box * { position: relative; z-index: 1; }
.donate-box h2 {
    font-size: 1.6rem; font-weight: 800;
    background: linear-gradient(135deg, #a78bfa, #f472b6, #fbbf24);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text; margin: 0 0 0.3rem 0;
}
.donate-box .subtitle {
    color: #9ca3af; font-size: 0.95rem; margin-bottom: 1.5rem;
    max-width: 520px; margin-left: auto; margin-right: auto;
}
.wallet-card {
    background: #0f0f1f; border: 1px solid #2d2d5c;
    border-radius: 14px; padding: 1.2rem; margin: 0.8rem auto;
    max-width: 520px; text-align: left;
    transition: border-color 0.3s;
}
.wallet-card:hover { border-color: #a78bfa; }
.wallet-card .chain-label {
    display: inline-flex; align-items: center; gap: 6px;
    font-size: 0.8rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.5px; margin-bottom: 0.5rem;
}
.wallet-card .chain-label.sol { color: #9945ff; }
.wallet-card .chain-label.eth { color: #627eea; }
.wallet-card .chain-label .dot {
    width: 8px; height: 8px; border-radius: 50%;
    display: inline-block;
}
.wallet-card .chain-label.sol .dot { background: #9945ff; }
.wallet-card .chain-label.eth .dot { background: #627eea; }
.wallet-card .addr {
    font-family: 'Courier New', monospace;
    font-size: 0.82rem; color: #e5e7eb;
    background: #1a1a2e; padding: 8px 12px;
    border-radius: 8px; word-break: break-all;
    border: 1px solid #2d2d5c;
    user-select: all; cursor: pointer;
}
.donate-footer {
    color: #6b7280; font-size: 0.8rem; margin-top: 1.5rem;
    font-style: italic;
}

/* Hide streamlit branding */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

/* Tab styling */
.stTabs [data-baseweb="tab-list"] { gap: 8px; }
.stTabs [data-baseweb="tab"] {
    padding: 10px 20px; border-radius: 10px 10px 0 0;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)


# ─────────────── HELPER FUNCTIONS ────────────────

CHAIN_DISPLAY = {
    "ethereum": "Ethereum", "bsc": "BSC", "base": "Base",
    "arbitrum": "Arbitrum", "polygon": "Polygon",
    "avalanche": "Avalanche", "solana": "Solana",
}

EVENT_DISPLAY = {
    "early_sniper": "Sniper Awal",
    "dev_large_holding": "Dev Pegang Banyak",
    "wallet_cluster": "Grup Wallet Mencurigakan",
    "whale_holding": "Whale Dominan",
    "early_buyer": "Pembeli Awal",
    "bundled_buy": "Pembelian Bundel",
}

SEVERITY_DISPLAY = {
    "high": "BAHAYA",
    "medium": "WASPADA",
    "low": "INFO",
}

SEVERITY_EMOJI = {
    "high": "🔴",
    "medium": "🟡",
    "low": "🟢",
}


def fmt_usd(val):
    if val is None or val == 0:
        return "-"
    if val >= 1_000_000:
        return f"${val/1_000_000:,.1f}M"
    if val >= 1_000:
        return f"${val/1_000:,.1f}K"
    return f"${val:,.2f}"


def fmt_addr(addr):
    if not addr or len(addr) < 12:
        return addr or "-"
    return f"{addr[:6]}...{addr[-4:]}"


def chain_badge_html(chain):
    name = CHAIN_DISPLAY.get(chain, chain)
    return f'<span class="chain-badge chain-{chain}">{name}</span>'


def severity_badge_html(sev):
    label = SEVERITY_DISPLAY.get(sev, sev)
    return f'<span class="badge-{sev}">{label}</span>'


def run_background_scan():
    """Run a scan and store results — called from web UI."""
    tokens = scan_new_memes(queries=[
        "meme", "pepe", "doge", "bonk", "moon", "shib",
        "floki", "trump", "ai", "cat", "wojak",
    ])
    for t in tokens:
        try:
            upsert_token(
                chain=t["chain"], address=t["token_address"],
                symbol=t.get("symbol", ""), name=t.get("name", ""),
                pair_address=t.get("pair_address", ""),
                dex=t.get("dex", ""),
                liquidity_usd=t.get("liquidity_usd", 0),
                market_cap=t.get("market_cap", 0),
                price_usd=t.get("price_usd", 0),
                volume_24h=t.get("volume_24h", 0),
                created_at=str(t.get("created_at", "")),
            )
        except Exception:
            pass
    return tokens


# ─────────────── SIDEBAR ────────────────

with st.sidebar:
    st.markdown("## Pengaturan")

    st.markdown("### Filter Chain")
    selected_chain = st.selectbox(
        "Pilih Blockchain",
        ["Semua"] + SUPPORTED_CHAINS,
        format_func=lambda x: "Semua Chain" if x == "Semua" else CHAIN_DISPLAY.get(x, x),
        label_visibility="collapsed",
    )

    st.markdown("### Tingkat Bahaya")
    selected_severity = st.selectbox(
        "Pilih Tingkat",
        ["Semua", "high", "medium", "low"],
        format_func=lambda x: {
            "Semua": "Semua Level",
            "high": "🔴 Bahaya Tinggi",
            "medium": "🟡 Waspada",
            "low": "🟢 Info",
        }.get(x, x),
        label_visibility="collapsed",
    )

    st.markdown("### Jumlah Data")
    event_limit = st.slider("Maks event ditampilkan", 10, 500, 100, label_visibility="collapsed")

    st.divider()

    st.markdown("### Scan Otomatis")
    auto_refresh = st.toggle("Refresh otomatis tiap 15 detik", value=False)

    if st.button("🔄 Scan Sekarang", use_container_width=True, type="primary"):
        with st.spinner("Memindai meme coin baru..."):
            tokens_found = run_background_scan()
            st.success(f"Ditemukan {len(tokens_found)} token!")
            time.sleep(1)
            st.rerun()

    st.divider()
    st.markdown(
        '<p style="font-size:0.75rem;color:#6b7280;text-align:center;">'
        'Meme Insider Tracker v1.0<br>'
        'Data dari Dexscreener + On-chain RPC<br>'
        'Gratis &bull; Tanpa API Key'
        '</p>', unsafe_allow_html=True
    )

if auto_refresh:
    time.sleep(15)
    st.rerun()


# ─────────────── LOAD DATA ────────────────

chain_filter = selected_chain if selected_chain != "Semua" else None
severity_filter = selected_severity if selected_severity != "Semua" else None

events = get_recent_events(limit=event_limit, chain=chain_filter, severity=severity_filter)
tokens = get_tracked_tokens(limit=200, chain=chain_filter)
clusters = get_clusters(limit=50, chain=chain_filter)


# ─────────────── HEADER ────────────────

st.markdown("""
<div class="main-header">
    <h1>Meme Insider Tracker</h1>
    <p>Deteksi otomatis aktivitas insider & whale di meme coin — semua chain, real-time</p>
</div>
""", unsafe_allow_html=True)


# ─────────────── METRIC CARDS ────────────────

c1, c2, c3, c4 = st.columns(4)

high_count = len([e for e in events if e.get("severity") == "high"])

with c1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="number">{len(tokens)}</div>
        <div class="label">Token Terpantau</div>
    </div>""", unsafe_allow_html=True)

with c2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="number">{len(events)}</div>
        <div class="label">Event Insider</div>
    </div>""", unsafe_allow_html=True)

with c3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="number" style="color:#dc2626">{high_count}</div>
        <div class="label">Alert Bahaya Tinggi</div>
    </div>""", unsafe_allow_html=True)

with c4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="number">{len(clusters)}</div>
        <div class="label">Grup Wallet Terdeteksi</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)


# ─────────────── TABS ────────────────

tab1, tab2, tab3, tab4 = st.tabs([
    "🔍 Aktivitas Insider",
    "📊 Token Terpantau",
    "🕸️ Grup Wallet",
    "⚡ Scan & Analisis",
])


# ─────────────── TAB 1: INSIDER EVENTS ────────────────

with tab1:
    st.markdown("### Aktivitas Insider Terbaru")
    st.caption("Daftar transaksi & pola mencurigakan yang terdeteksi oleh scanner")

    if events:
        for ev in events:
            sev = ev.get("severity", "low")
            emoji = SEVERITY_EMOJI.get(sev, "")
            ev_type = EVENT_DISPLAY.get(ev.get("event_type", ""), ev.get("event_type", ""))
            chain = ev.get("chain", "")
            chain_name = CHAIN_DISPLAY.get(chain, chain)
            token = fmt_addr(ev.get("token_address", ""))
            wallet = fmt_addr(ev.get("wallet_address", ""))
            amount = fmt_usd(ev.get("amount_usd", 0))
            waktu = ev.get("detected_at", "")

            details = {}
            try:
                details = json.loads(ev.get("details", "{}"))
            except Exception:
                pass

            detail_text = ""
            if details.get("balance_pct"):
                detail_text = f" &bull; Memegang **{details['balance_pct']:.1f}%** supply"
            elif details.get("bundle_size"):
                detail_text = f" &bull; **{details['bundle_size']}** wallet dalam 1 transaksi"
            elif details.get("amount"):
                detail_text = f" &bull; Jumlah: **{details['amount']:,.0f}** token"

            st.markdown(f"""
            <div class="event-card {sev}">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem;">
                    <div>
                        {severity_badge_html(sev)} &nbsp;
                        {chain_badge_html(chain)}
                        &nbsp; <b>{ev_type}</b>
                    </div>
                    <span style="color:#6b7280;font-size:0.8rem;">{waktu}</span>
                </div>
                <div style="font-size:0.85rem;color:#d1d5db;">
                    <b>Token:</b> <code>{ev.get("token_address","")}</code><br>
                    <b>Wallet:</b> <code>{ev.get("wallet_address","")}</code>
                    {detail_text}
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Charts
        st.markdown("### Distribusi Event")
        col_a, col_b = st.columns(2)
        df_ev = pd.DataFrame(events)

        with col_a:
            if "event_type" in df_ev.columns:
                st.markdown("**Berdasarkan Jenis**")
                type_counts = df_ev["event_type"].map(
                    lambda x: EVENT_DISPLAY.get(x, x)
                ).value_counts()
                st.bar_chart(type_counts)

        with col_b:
            if "chain" in df_ev.columns:
                st.markdown("**Berdasarkan Chain**")
                chain_counts = df_ev["chain"].map(
                    lambda x: CHAIN_DISPLAY.get(x, x)
                ).value_counts()
                st.bar_chart(chain_counts)
    else:
        st.info(
            "Belum ada aktivitas insider terdeteksi. "
            "Klik **Scan Sekarang** di sidebar atau gunakan tab **Scan & Analisis**."
        )


# ─────────────── TAB 2: TRACKED TOKENS ────────────────

with tab2:
    st.markdown("### Daftar Meme Coin Terpantau")
    st.caption("Token yang ditemukan scanner dari Dexscreener, diurutkan terbaru")

    if tokens:
        df = pd.DataFrame(tokens)

        # Rename columns to friendly names
        col_map = {
            "chain": "Chain",
            "symbol": "Simbol",
            "name": "Nama Token",
            "price_usd": "Harga (USD)",
            "market_cap": "Market Cap",
            "liquidity_usd": "Likuiditas",
            "volume_24h": "Volume 24j",
            "dex": "DEX",
            "last_updated": "Update Terakhir",
        }

        available = [c for c in col_map.keys() if c in df.columns]
        df_show = df[available].copy()

        # Format columns
        if "chain" in df_show.columns:
            df_show["chain"] = df_show["chain"].map(lambda x: CHAIN_DISPLAY.get(x, x))
        for col in ["price_usd"]:
            if col in df_show.columns:
                df_show[col] = df_show[col].map(lambda x: f"${x:,.6f}" if x and x < 1 else f"${x:,.2f}" if x else "-")
        for col in ["market_cap", "liquidity_usd", "volume_24h"]:
            if col in df_show.columns:
                df_show[col] = df_show[col].map(lambda x: fmt_usd(x) if x else "-")

        df_show = df_show.rename(columns=col_map)

        st.dataframe(
            df_show,
            use_container_width=True,
            height=500,
            hide_index=True,
        )
    else:
        st.info("Belum ada token terpantau. Jalankan scan untuk menemukan meme coin baru!")


# ─────────────── TAB 3: WALLET CLUSTERS ────────────────

with tab3:
    st.markdown("### Grup Wallet Terdeteksi")
    st.caption(
        "Kumpulan wallet yang didanai dari sumber yang sama — "
        "indikasi kuat adanya insider yang terkoordinasi"
    )

    if clusters:
        for cl in clusters:
            chain = cl.get("chain", "")
            funder = cl.get("funder_address", "")
            size = cl.get("cluster_size", 0)
            total = cl.get("total_bought_usd", 0)
            waktu = cl.get("detected_at", "")

            with st.expander(
                f"{SEVERITY_EMOJI['high']} [{CHAIN_DISPLAY.get(chain, chain)}] "
                f"Pendana: {fmt_addr(funder)} — {size} wallet terhubung"
            ):
                col_x, col_y = st.columns(2)
                with col_x:
                    st.markdown(f"**Chain:** {CHAIN_DISPLAY.get(chain, chain)}")
                    st.markdown(f"**Alamat Pendana:**")
                    st.code(funder)
                    st.markdown(f"**Jumlah Wallet:** {size}")
                with col_y:
                    st.markdown(f"**Total Pembelian:** {fmt_usd(total)}")
                    st.markdown(f"**Terdeteksi:** {waktu}")

                wallets = []
                try:
                    wallets = json.loads(cl.get("wallet_addresses", "[]"))
                except Exception:
                    pass

                if wallets:
                    st.markdown("**Daftar Wallet dalam Grup:**")
                    for i, w in enumerate(wallets, 1):
                        st.markdown(f"`{i}.` `{w}`")
    else:
        st.info("Belum ada grup wallet terdeteksi.")


# ─────────────── TAB 4: LIVE SCANNER ────────────────

with tab4:
    st.markdown("### Scan & Analisis Token")

    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.markdown("#### Scan Meme Coin Baru")
        st.caption("Cari meme coin yang baru launch di semua chain sekaligus")

        keyword = st.text_input(
            "Kata kunci pencarian (opsional)",
            placeholder="Contoh: pepe, doge, trump, ai...",
            key="scan_keyword",
        )

        min_liq = st.number_input(
            "Minimum Likuiditas (USD)",
            min_value=0, value=500, step=100,
            help="Hanya tampilkan token dengan likuiditas di atas nilai ini",
        )

        if st.button("🚀 Mulai Scan", use_container_width=True, type="primary"):
            with st.spinner("Memindai Dexscreener untuk meme coin baru..."):
                queries = [k.strip() for k in keyword.split(",") if k.strip()] if keyword else None
                found = scan_new_memes(queries=queries) if not queries else []
                if queries:
                    for q in queries:
                        found.extend(search_meme_tokens(query=q, min_liquidity=min_liq))

                if not queries:
                    found = [t for t in found if t.get("liquidity_usd", 0) >= min_liq]

                for t in found:
                    try:
                        upsert_token(
                            chain=t["chain"], address=t["token_address"],
                            symbol=t.get("symbol", ""), name=t.get("name", ""),
                            pair_address=t.get("pair_address", ""),
                            dex=t.get("dex", ""),
                            liquidity_usd=t.get("liquidity_usd", 0),
                            market_cap=t.get("market_cap", 0),
                            price_usd=t.get("price_usd", 0),
                            volume_24h=t.get("volume_24h", 0),
                        )
                    except Exception:
                        pass

                st.success(f"Ditemukan **{len(found)}** token!")

                if found:
                    for t in found[:20]:
                        chain = t.get("chain", "")
                        st.markdown(
                            f"{chain_badge_html(chain)} "
                            f"**{t.get('symbol', '?')}** — {t.get('name', '')} &nbsp; | &nbsp; "
                            f"Likuiditas: **{fmt_usd(t.get('liquidity_usd', 0))}** &nbsp; | &nbsp; "
                            f"Market Cap: **{fmt_usd(t.get('market_cap', 0))}**",
                            unsafe_allow_html=True
                        )

    with col_right:
        st.markdown("#### Analisis Token Spesifik")
        st.caption("Masukkan alamat token untuk cek apakah ada insider")

        analysis_chain = st.selectbox(
            "Pilih Chain",
            SUPPORTED_CHAINS,
            format_func=lambda x: CHAIN_DISPLAY.get(x, x),
            key="analysis_chain",
        )

        analysis_addr = st.text_input(
            "Alamat Token (Contract Address)",
            placeholder="0x... atau alamat Solana",
            key="analysis_addr",
        )

        if st.button("🔍 Analisis Insider", use_container_width=True):
            if not analysis_addr:
                st.warning("Masukkan alamat token terlebih dahulu!")
            else:
                with st.spinner(f"Menganalisis token di {CHAIN_DISPLAY.get(analysis_chain, analysis_chain)}..."):
                    results = analyze_token(analysis_chain, analysis_addr)

                if not results:
                    st.success("✅ Tidak ada aktivitas mencurigakan terdeteksi!")
                else:
                    for r in results:
                        sev = r.get("severity", "low")
                        msg = r.get("msg", str(r))
                        rtype = r.get("type", "")

                        if rtype == "error":
                            st.error(f"Error: {msg}")
                        elif sev == "high":
                            st.error(f"🔴 **BAHAYA** — {msg}")
                        elif sev == "medium":
                            st.warning(f"🟡 **WASPADA** — {msg}")
                        else:
                            st.info(f"🟢 {msg}")

                        # Show extra detail
                        if r.get("wallets"):
                            with st.expander(f"Lihat {len(r['wallets'])} wallet terkait"):
                                for w in r["wallets"]:
                                    st.code(w)

        st.divider()
        st.markdown("#### Cara Baca Hasil Analisis")
        st.markdown("""
        | Istilah | Artinya |
        |---------|---------|
        | **Sniper Awal** | Wallet yang beli di block pertama setelah token launch — kemungkinan bot/insider |
        | **Dev Pegang Banyak** | Developer masih memegang % besar supply — risiko rug pull |
        | **Grup Wallet** | Beberapa wallet didanai dari 1 sumber — koordinasi insider |
        | **Pembelian Bundel** | Banyak wallet beli dalam 1 transaksi (Solana) — taktik insider |
        | **Whale Dominan** | 1 wallet pegang >10% supply — bisa dump kapan saja |
        """)


# ─────────────── COFFEE / DONATE ────────────────

st.markdown("""
<div class="donate-box">
    <div style="font-size:2.5rem;margin-bottom:0.5rem;">☕</div>
    <h2>Traktir Saya Kopi</h2>
    <p class="subtitle">
        Tool ini 100% gratis &amp; open-source. Kalau kamu merasa terbantu
        menghindari rug pull atau menemukan insider lebih awal,
        beliin saya kopi sebagai apresiasi ya! Setiap donasi bikin saya
        makin semangat ngembangin fitur baru.
    </p>

    <div class="wallet-card">
        <div class="chain-label sol"><span class="dot"></span> Solana (SOL)</div>
        <div class="addr">2vMBrEcTd85b1CUwcbU6f3PuKmdUCHkM8kq6mMVp82Ca</div>
    </div>

    <div class="wallet-card">
        <div class="chain-label eth"><span class="dot"></span> Ethereum / EVM (ETH, BSC, Base, Arbitrum)</div>
        <div class="addr">0x2D36d2658B46C509Ecc9BB68D7844bb3ef9D337a</div>
    </div>

    <p class="donate-footer">
        Klik alamat di atas untuk copy &bull; Berapapun sangat berarti &bull; Terima kasih, fren! 🤝
    </p>
</div>
""", unsafe_allow_html=True)


# ─────────────── FOOTER ────────────────

st.divider()
cols_f = st.columns(3)
with cols_f[0]:
    st.caption(f"Terakhir diperbarui: {datetime.now().strftime('%d %b %Y, %H:%M:%S')}")
with cols_f[1]:
    st.caption(f"Memantau {len(SUPPORTED_CHAINS)} blockchain")
with cols_f[2]:
    st.caption("Data: Dexscreener + On-chain RPC (gratis)")
