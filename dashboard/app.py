"""
Meme Insider Tracker — Streamlit Web Dashboard
Deteksi aktivitas insider pada meme coin di semua chain.
"""

import streamlit as st
import pandas as pd
import json
import time
from datetime import datetime, timedelta

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from core.database import init_db, get_recent_events, get_tracked_tokens, get_clusters, upsert_token, add_insider_event
from core.config import SUPPORTED_CHAINS, INSIDER_CONFIG
from chains.dexscreener import scan_new_memes, search_meme_tokens
from analyzers.insider_detector import analyze_token

# ━━━━━━━━━━━━━━━━━━━ PAGE CONFIG ━━━━━━━━━━━━━━━━━━━
st.set_page_config(page_title="Meme Insider Tracker", page_icon="🔍", layout="wide")
init_db()

# ━━━━━━━━━━━━━━━━━━━ CONSTANTS ━━━━━━━━━━━━━━━━━━━
CHAIN_NAME = {
    "ethereum": "Ethereum", "bsc": "BSC", "base": "Base",
    "arbitrum": "Arbitrum", "polygon": "Polygon",
    "avalanche": "Avalanche", "solana": "Solana",
}
EVENT_NAME = {
    "early_sniper": "🎯 Sniper Awal",
    "dev_large_holding": "👨‍💻 Dev Pegang Banyak",
    "wallet_cluster": "🕸️ Grup Wallet Mencurigakan",
    "whale_holding": "🐋 Whale Dominan",
    "early_buyer": "⚡ Pembeli Awal",
    "bundled_buy": "📦 Pembelian Bundel",
}
SEVERITY_LABEL = {"high": "🔴 BAHAYA", "medium": "🟡 WASPADA", "low": "🟢 INFO"}


def fmt_usd(val):
    if not val:
        return "-"
    if val >= 1_000_000:
        return f"${val/1_000_000:,.1f}M"
    if val >= 1_000:
        return f"${val/1_000:,.1f}K"
    return f"${val:,.2f}"


def fmt_addr(addr):
    if not addr or len(addr) < 14:
        return addr or "-"
    return f"{addr[:6]}...{addr[-4:]}"


# ━━━━━━━━━━━━━━━━━━━ AUTO-SCAN ON FIRST LOAD ━━━━━━━━━━━━━━━━━━━
# Otomatis scan saat pertama kali web dibuka supaya ada data

if "first_scan_done" not in st.session_state:
    st.session_state.first_scan_done = False
    st.session_state.scan_results = []
    st.session_state.analysis_results = []

if not st.session_state.first_scan_done:
    with st.spinner("⏳ Memuat data meme coin terbaru dari semua chain... (hanya sekali saat pertama buka)"):
        try:
            tokens_found = scan_new_memes(queries=[
                "meme", "pepe", "doge", "bonk", "moon",
                "shib", "floki", "trump", "ai", "cat",
            ])
            for t in tokens_found:
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

            # Analyze top EVM tokens for insider activity (skip Solana on auto to avoid rate limit)
            analysis_results = []
            evm_chains = {"ethereum", "bsc", "base", "arbitrum", "polygon", "avalanche"}
            evm_tokens = [t for t in tokens_found if t.get("chain") in evm_chains]
            sorted_tokens = sorted(evm_tokens, key=lambda x: x.get("liquidity_usd", 0), reverse=True)
            for t in sorted_tokens[:5]:
                try:
                    findings = analyze_token(t["chain"], t["token_address"], pair_data=t)
                    if findings:
                        for f in findings:
                            f["token_symbol"] = t.get("symbol", "?")
                            f["token_chain"] = t.get("chain", "")
                        analysis_results.extend(findings)
                except Exception:
                    pass
                time.sleep(0.5)

            st.session_state.scan_results = tokens_found
            st.session_state.analysis_results = analysis_results
        except Exception as e:
            st.session_state.scan_results = []
            st.session_state.analysis_results = []

    st.session_state.first_scan_done = True
    st.rerun()


# ━━━━━━━━━━━━━━━━━━━ CSS (minimal, clean) ━━━━━━━━━━━━━━━━━━━
st.markdown("""
<style>
.donate-box {
    background: linear-gradient(135deg, #1e1b4b, #312e81, #1e1b4b);
    border: 2px solid #6366f1; border-radius: 16px;
    padding: 2rem; text-align: center; margin: 1rem 0;
}
.donate-box h2 { color: #a5b4fc; margin: 0.5rem 0; }
.donate-box p { color: #c7d2fe; }
.wallet-box {
    background: #0f172a; border: 1px solid #334155;
    border-radius: 10px; padding: 1rem; margin: 0.6rem auto;
    max-width: 550px; text-align: left;
}
.wallet-box .label { color: #94a3b8; font-size: 0.8rem; font-weight: 700; margin-bottom: 4px; }
.wallet-box code {
    color: #e2e8f0; font-size: 0.85rem; word-break: break-all;
    background: #1e293b; padding: 6px 10px; border-radius: 6px;
    display: block; margin-top: 4px; user-select: all; cursor: pointer;
}
</style>
""", unsafe_allow_html=True)


# ━━━━━━━━━━━━━━━━━━━ SIDEBAR ━━━━━━━━━━━━━━━━━━━
with st.sidebar:
    st.title("🔍 Meme Insider Tracker")
    st.caption("Deteksi insider trade meme coin")

    st.divider()

    st.subheader("Filter")
    sel_chain = st.selectbox(
        "Chain",
        ["Semua"] + SUPPORTED_CHAINS,
        format_func=lambda x: "🌐 Semua Chain" if x == "Semua" else CHAIN_NAME.get(x, x),
    )
    sel_severity = st.selectbox(
        "Level Bahaya",
        ["Semua", "high", "medium", "low"],
        format_func=lambda x: {"Semua": "Semua Level", "high": "🔴 Bahaya", "medium": "🟡 Waspada", "low": "🟢 Info"}.get(x, x),
    )

    st.divider()

    if st.button("🔄 Scan Ulang Sekarang", use_container_width=True, type="primary"):
        st.session_state.first_scan_done = False
        st.rerun()

    auto = st.toggle("Auto-refresh tiap 30 detik")

    st.divider()
    st.caption("v1.0 • Gratis • Tanpa API Key")
    st.caption("Data: Dexscreener + On-chain RPC")

if auto:
    time.sleep(30)
    st.session_state.first_scan_done = False
    st.rerun()


# ━━━━━━━━━━━━━━━━━━━ LOAD DATA ━━━━━━━━━━━━━━━━━━━
chain_f = sel_chain if sel_chain != "Semua" else None
sev_f = sel_severity if sel_severity != "Semua" else None
events = get_recent_events(limit=200, chain=chain_f, severity=sev_f)
tokens = get_tracked_tokens(limit=300, chain=chain_f)
clusters = get_clusters(limit=50, chain=chain_f)


# ━━━━━━━━━━━━━━━━━━━ HEADER ━━━━━━━━━━━━━━━━━━━
st.title("🔍 Meme Insider Tracker")
st.markdown("**Deteksi otomatis aktivitas insider & whale di meme coin — 7 chain, real-time, 100% gratis.**")

# ━━━━━━━━━━━━━━━━━━━ METRICS ━━━━━━━━━━━━━━━━━━━
high_count = len([e for e in events if e.get("severity") == "high"])
c1, c2, c3, c4 = st.columns(4)
c1.metric("🪙 Token Terpantau", len(tokens))
c2.metric("🚨 Event Insider", len(events))
c3.metric("🔴 Bahaya Tinggi", high_count)
c4.metric("🕸️ Grup Wallet", len(clusters))


# ━━━━━━━━━━━━━━━━━━━ TABS ━━━━━━━━━━━━━━━━━━━
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Token Terpantau",
    "🚨 Aktivitas Insider",
    "🕸️ Grup Wallet",
    "⚡ Scan Manual",
])


# ━━━━━━━━━━━━━ TAB 1: TOKEN LIST ━━━━━━━━━━━━━
with tab1:
    st.subheader("📊 Daftar Meme Coin yang Ditemukan")
    st.caption("Data langsung dari Dexscreener — diperbarui setiap kali scan")

    if tokens:
        rows = []
        for t in tokens:
            rows.append({
                "Chain": CHAIN_NAME.get(t.get("chain", ""), t.get("chain", "")),
                "Simbol": t.get("symbol", "-"),
                "Nama": t.get("name", "-"),
                "Harga": f"${t['price_usd']:,.8f}" if t.get("price_usd") and t["price_usd"] < 0.01
                         else f"${t['price_usd']:,.4f}" if t.get("price_usd") and t["price_usd"] < 1
                         else f"${t['price_usd']:,.2f}" if t.get("price_usd")
                         else "-",
                "Market Cap": fmt_usd(t.get("market_cap")),
                "Likuiditas": fmt_usd(t.get("liquidity_usd")),
                "Volume 24j": fmt_usd(t.get("volume_24h")),
                "DEX": t.get("dex", "-"),
                "Update": t.get("last_updated", "-"),
            })

        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, height=500, hide_index=True)
        st.info(f"Total: **{len(tokens)}** token ditemukan di **{len(set(t.get('chain','') for t in tokens))}** chain berbeda")
    else:
        st.warning("Belum ada data token. Klik **Scan Ulang Sekarang** di sidebar.")


# ━━━━━━━━━━━━━ TAB 2: INSIDER EVENTS ━━━━━━━━━━━━━
with tab2:
    st.subheader("🚨 Aktivitas Insider Terdeteksi")
    st.caption("Pola mencurigakan yang ditemukan dari analisis on-chain")

    if events:
        for ev in events:
            sev = ev.get("severity", "low")
            ev_type = EVENT_NAME.get(ev.get("event_type", ""), ev.get("event_type", ""))
            chain = CHAIN_NAME.get(ev.get("chain", ""), ev.get("chain", ""))
            waktu = ev.get("detected_at", "")

            # Parse details
            details = {}
            try:
                details = json.loads(ev.get("details", "{}"))
            except Exception:
                pass

            # Build description
            desc_parts = []
            if details.get("balance_pct"):
                desc_parts.append(f"Memegang **{details['balance_pct']:.1f}%** dari total supply")
            if details.get("bundle_size"):
                desc_parts.append(f"**{details['bundle_size']}** wallet beli dalam 1 transaksi")
            if details.get("amount"):
                desc_parts.append(f"Jumlah: **{details['amount']:,.0f}** token")
            if details.get("block"):
                desc_parts.append(f"Block: #{details['block']}")
            if details.get("slot"):
                desc_parts.append(f"Slot: #{details['slot']}")

            detail_str = " • ".join(desc_parts) if desc_parts else ""

            # Display as expander
            label = f"{SEVERITY_LABEL.get(sev, sev)} | {chain} | {ev_type}"
            with st.expander(label, expanded=(sev == "high")):
                col_a, col_b = st.columns([2, 1])
                with col_a:
                    st.markdown(f"**Jenis:** {ev_type}")
                    st.markdown(f"**Chain:** {chain}")
                    st.markdown(f"**Token:** `{ev.get('token_address', '-')}`")
                    st.markdown(f"**Wallet:** `{ev.get('wallet_address', '-')}`")
                    if detail_str:
                        st.markdown(f"**Detail:** {detail_str}")
                with col_b:
                    st.markdown(f"**Waktu:** {waktu}")
                    if ev.get("tx_hash"):
                        st.markdown(f"**TX:** `{fmt_addr(ev['tx_hash'])}`")
                    if ev.get("amount_usd"):
                        st.markdown(f"**Nilai:** {fmt_usd(ev['amount_usd'])}")

        # Stats
        st.divider()
        st.subheader("📈 Ringkasan")
        col_x, col_y = st.columns(2)
        df_ev = pd.DataFrame(events)
        with col_x:
            if "event_type" in df_ev.columns:
                st.markdown("**Jenis Event**")
                counts = df_ev["event_type"].map(lambda x: EVENT_NAME.get(x, x)).value_counts()
                st.bar_chart(counts)
        with col_y:
            if "chain" in df_ev.columns:
                st.markdown("**Per Chain**")
                counts = df_ev["chain"].map(lambda x: CHAIN_NAME.get(x, x)).value_counts()
                st.bar_chart(counts)

    else:
        st.info(
            "Belum ada aktivitas insider terdeteksi di scan terakhir. "
            "Ini bisa berarti token yang ditemukan relatif bersih, atau coba scan ulang."
        )

    # Penjelasan istilah
    st.divider()
    st.subheader("📖 Kamus Istilah")
    st.markdown("""
| Istilah | Arti | Bahaya |
|---------|------|--------|
| **🎯 Sniper Awal** | Wallet yang beli di detik pertama token launch. Biasanya bot insider yang sudah tau duluan. | Tinggi |
| **👨‍💻 Dev Pegang Banyak** | Developer/pembuat token masih hold persentase besar dari supply. Bisa dump kapan saja (rug pull). | Tinggi |
| **🕸️ Grup Wallet** | Beberapa wallet yang ternyata didanai dari 1 sumber. Pura-pura beda orang tapi satu komplotan. | Tinggi |
| **📦 Pembelian Bundel** | Banyak wallet beli dalam 1 transaksi yang sama (khusus Solana). Taktik insider untuk kumpulkan token lewat banyak wallet. | Tinggi |
| **🐋 Whale Dominan** | Satu wallet pegang lebih dari 10% supply. Kalau jual, harga bisa anjlok drastis. | Sedang |
| **⚡ Pembeli Awal** | Wallet-wallet pertama yang beli setelah token dibuat. Belum tentu insider, tapi patut diwaspadai. | Sedang |
""")


# ━━━━━━━━━━━━━ TAB 3: WALLET CLUSTERS ━━━━━━━━━━━━━
with tab3:
    st.subheader("🕸️ Grup Wallet yang Saling Terhubung")
    st.caption("Wallet-wallet yang didanai dari sumber yang sama = kemungkinan besar 1 orang/kelompok")

    if clusters:
        for cl in clusters:
            chain = CHAIN_NAME.get(cl.get("chain", ""), cl.get("chain", ""))
            funder = cl.get("funder_address", "")
            size = cl.get("cluster_size", 0)
            total = cl.get("total_bought_usd", 0)

            with st.expander(f"🔴 {chain} — Pendana: {fmt_addr(funder)} — {size} wallet terhubung"):
                st.markdown(f"**Chain:** {chain}")
                st.markdown(f"**Alamat Pendana (sumber dana):**")
                st.code(funder)
                st.markdown(f"**Jumlah Wallet Terhubung:** {size}")
                st.markdown(f"**Total Pembelian:** {fmt_usd(total)}")
                st.markdown(f"**Terdeteksi:** {cl.get('detected_at', '-')}")

                wallets = []
                try:
                    wallets = json.loads(cl.get("wallet_addresses", "[]"))
                except Exception:
                    pass
                if wallets:
                    st.markdown("**Daftar Wallet:**")
                    for i, w in enumerate(wallets, 1):
                        st.code(f"{i}. {w}")
    else:
        st.info("Belum ada grup wallet terdeteksi. Grup wallet biasanya ditemukan saat menganalisis token dengan on-chain data.")


# ━━━━━━━━━━━━━ TAB 4: MANUAL SCAN ━━━━━━━━━━━━━
with tab4:
    st.subheader("⚡ Scan & Analisis Manual")

    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown("#### 🔎 Cari Meme Coin Baru")
        st.caption("Cari di Dexscreener berdasarkan kata kunci")

        keyword = st.text_input(
            "Kata kunci",
            placeholder="Contoh: pepe, doge, trump, ai",
            help="Pisahkan dengan koma kalau lebih dari satu",
        )
        min_liq = st.number_input("Min. Likuiditas (USD)", min_value=0, value=500, step=100)

        if st.button("🚀 Mulai Scan", use_container_width=True, type="primary"):
            with st.spinner("Memindai..."):
                if keyword:
                    queries = [k.strip() for k in keyword.split(",") if k.strip()]
                    found = []
                    for q in queries:
                        found.extend(search_meme_tokens(query=q, min_liquidity=min_liq))
                        time.sleep(0.3)
                else:
                    found = scan_new_memes()
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
                    for t in found[:15]:
                        st.markdown(
                            f"**{CHAIN_NAME.get(t['chain'], t['chain'])}** • "
                            f"**{t.get('symbol', '?')}** ({t.get('name', '')}) • "
                            f"Liq: {fmt_usd(t.get('liquidity_usd'))} • "
                            f"MCap: {fmt_usd(t.get('market_cap'))}"
                        )

    with col_r:
        st.markdown("#### 🔍 Analisis Token Tertentu")
        st.caption("Masukkan alamat kontrak token untuk cek insider")

        a_chain = st.selectbox("Chain", SUPPORTED_CHAINS, format_func=lambda x: CHAIN_NAME.get(x, x))
        a_addr = st.text_input("Alamat Token", placeholder="0x... atau alamat Solana")

        if st.button("🔍 Analisis", use_container_width=True):
            if not a_addr:
                st.warning("Masukkan alamat token dulu!")
            else:
                with st.spinner(f"Menganalisis di {CHAIN_NAME.get(a_chain, a_chain)}..."):
                    results = analyze_token(a_chain, a_addr)

                if not results:
                    st.success("✅ Tidak ada aktivitas mencurigakan!")
                else:
                    for r in results:
                        sev = r.get("severity", "low")
                        msg = r.get("msg", str(r))
                        rtype = r.get("type", "")
                        if rtype == "error":
                            st.error(f"❌ {msg}")
                        elif sev == "high":
                            st.error(f"🔴 **BAHAYA** — {msg}")
                        elif sev == "medium":
                            st.warning(f"🟡 **WASPADA** — {msg}")
                        else:
                            st.info(f"🟢 {msg}")

                        if r.get("wallets"):
                            with st.expander(f"👁️ Lihat {len(r['wallets'])} wallet"):
                                for w in r["wallets"]:
                                    st.code(w)


# ━━━━━━━━━━━━━━━━━━━ COFFEE / DONATE ━━━━━━━━━━━━━━━━━━━
st.divider()
st.markdown("""
<div class="donate-box">
    <div style="font-size:3rem;">☕</div>
    <h2>Suka Tool Ini? Traktir Saya Kopi!</h2>
    <p>
        Tool ini <b>100% gratis dan open-source</b>. Saya bikin ini supaya komunitas crypto
        bisa terhindar dari rug pull dan insider scam.<br><br>
        Kalau kamu merasa terbantu, kirim kopi kecil sebagai apresiasi.
        Berapapun bikin semangat ngembangin fitur baru! 🙏
    </p>

    <div class="wallet-box">
        <div class="label">☀️ SOLANA (SOL, SPL Token)</div>
        <code>2vMBrEcTd85b1CUwcbU6f3PuKmdUCHkM8kq6mMVp82Ca</code>
    </div>

    <div class="wallet-box">
        <div class="label">💎 ETHEREUM / BSC / BASE / ARBITRUM (ETH, USDT, dll)</div>
        <code>0x2D36d2658B46C509Ecc9BB68D7844bb3ef9D337a</code>
    </div>

    <p style="color:#64748b;font-size:0.8rem;margin-top:1rem;">
        Klik alamat untuk copy • Bisa kirim dari chain manapun • Terima kasih, fren! 🤝
    </p>
</div>
""", unsafe_allow_html=True)


# ━━━━━━━━━━━━━━━━━━━ FOOTER ━━━━━━━━━━━━━━━━━━━
st.divider()
f1, f2, f3 = st.columns(3)
f1.caption(f"Update: {datetime.now().strftime('%d %b %Y, %H:%M')}")
f2.caption(f"Pantau {len(SUPPORTED_CHAINS)} blockchain")
f3.caption("[GitHub](https://github.com/reodkt/meme-insider-tracker)")
