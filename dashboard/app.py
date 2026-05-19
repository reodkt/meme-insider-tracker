"""
Meme Insider Tracker — Real-time meme coin insider detection across all chains.
"""

import streamlit as st
import pandas as pd
import json
import time
from datetime import datetime

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from core.database import init_db, get_recent_events, get_tracked_tokens, get_clusters, upsert_token
from core.config import SUPPORTED_CHAINS, INSIDER_CONFIG
from chains.dexscreener import scan_new_memes, search_meme_tokens
from analyzers.insider_detector import analyze_token

# ── Page Config ──
st.set_page_config(page_title="Meme Insider Tracker", page_icon="🔍", layout="wide")
init_db()

# ── Responsive CSS ──
st.markdown("""<style>
@media (max-width: 768px) {
    .block-container { padding: 1rem 0.5rem !important; }
    [data-testid="stMetric"] { padding: 0.3rem !important; }
    [data-testid="stMetric"] label { font-size: 0.7rem !important; }
    [data-testid="stMetric"] [data-testid="stMetricValue"] { font-size: 1.2rem !important; }
}
[data-testid="stMetric"] {
    background: #262730; border-radius: 10px; padding: 0.8rem;
    border: 1px solid #3d3d5c;
}
</style>""", unsafe_allow_html=True)

# ── Constants ──
CHAIN_NAME = {
    "ethereum": "Ethereum", "bsc": "BSC", "base": "Base",
    "arbitrum": "Arbitrum", "polygon": "Polygon",
    "avalanche": "Avalanche", "solana": "Solana",
}
EVENT_NAME = {
    "early_sniper": "Sniper (Early Buy)",
    "dev_large_holding": "Dev Large Holding",
    "wallet_cluster": "Wallet Cluster",
    "whale_holding": "Whale Dominance",
    "early_buyer": "Early Buyer",
    "bundled_buy": "Bundled Buy",
}
SEV_LABEL = {"high": "HIGH", "medium": "WARN", "low": "INFO"}
SEV_ICON = {"high": "🔴", "medium": "🟡", "low": "🟢"}


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


# ── Auto-Scan on First Load ──
if "loaded" not in st.session_state:
    st.session_state.loaded = False

if not st.session_state.loaded:
    with st.spinner("Loading latest meme coins from all chains..."):
        try:
            found = scan_new_memes(queries=[
                "meme", "pepe", "doge", "bonk", "moon",
                "shib", "floki", "trump", "ai", "cat",
            ])
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
                        created_at=str(t.get("created_at", "")),
                    )
                except Exception:
                    pass

            evm_set = {"ethereum", "bsc", "base", "arbitrum", "polygon", "avalanche"}
            evm = sorted(
                [t for t in found if t.get("chain") in evm_set],
                key=lambda x: x.get("liquidity_usd", 0), reverse=True,
            )
            for t in evm[:5]:
                try:
                    analyze_token(t["chain"], t["token_address"], pair_data=t)
                except Exception:
                    pass
                time.sleep(0.5)
        except Exception:
            pass

    st.session_state.loaded = True
    st.rerun()


# ── Sidebar ──
with st.sidebar:
    st.title("🔍 Meme Insider Tracker")
    st.caption("Real-time insider detection for meme coins")
    st.divider()

    st.subheader("Filters")
    sel_chain = st.selectbox(
        "Chain",
        ["All"] + SUPPORTED_CHAINS,
        format_func=lambda x: "All Chains" if x == "All" else CHAIN_NAME.get(x, x),
    )
    sel_sev = st.selectbox(
        "Severity",
        ["All", "high", "medium", "low"],
        format_func=lambda x: {"All": "All Levels", "high": "🔴 High", "medium": "🟡 Medium", "low": "🟢 Low"}.get(x, x),
    )

    st.divider()

    if st.button("🔄 Rescan Now", use_container_width=True, type="primary"):
        st.session_state.loaded = False
        st.rerun()

    auto = st.toggle("Auto-refresh (30s)")

    st.divider()
    st.caption("v1.0 · Free · No API Key")
    st.caption("Data: Dexscreener + On-chain RPC")

if auto:
    time.sleep(30)
    st.session_state.loaded = False
    st.rerun()


# ── Load Data ──
cf = sel_chain if sel_chain != "All" else None
sf = sel_sev if sel_sev != "All" else None
events = get_recent_events(limit=200, chain=cf, severity=sf)
tokens = get_tracked_tokens(limit=300, chain=cf)
clusters = get_clusters(limit=50, chain=cf)


# ── Header ──
st.title("🔍 Meme Insider Tracker")
st.markdown("Automatic insider & whale detection for meme coins — **7 chains, real-time, 100% free.**")

# ── Metrics ──
high_ct = len([e for e in events if e.get("severity") == "high"])
c1, c2, c3, c4 = st.columns(4)
c1.metric("Tokens Tracked", len(tokens))
c2.metric("Insider Events", len(events))
c3.metric("High Alerts", high_ct)
c4.metric("Wallet Clusters", len(clusters))

# ── Tabs ──
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Tokens", "🚨 Insider Activity", "🕸️ Wallet Clusters", "⚡ Scan & Analyze",
])


# ── TAB 1: Tokens ──
with tab1:
    st.subheader("Tracked Meme Coins")
    st.caption("Live data from Dexscreener — refreshed on every scan")

    if tokens:
        rows = []
        for t in tokens:
            price = t.get("price_usd", 0)
            rows.append({
                "Chain": CHAIN_NAME.get(t.get("chain", ""), t.get("chain", "")),
                "Symbol": t.get("symbol", "-"),
                "Name": t.get("name", "-"),
                "Price": f"${price:,.8f}" if price and price < 0.01
                         else f"${price:,.4f}" if price and price < 1
                         else f"${price:,.2f}" if price else "-",
                "Market Cap": fmt_usd(t.get("market_cap")),
                "Liquidity": fmt_usd(t.get("liquidity_usd")),
                "Vol 24h": fmt_usd(t.get("volume_24h")),
                "DEX": t.get("dex", "-"),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, height=480, hide_index=True)
        st.caption(f"Showing {len(tokens)} tokens across {len(set(t.get('chain','') for t in tokens))} chains")
    else:
        st.info("No tokens found yet. Click **Rescan Now** in the sidebar.")


# ── TAB 2: Insider Events ──
with tab2:
    st.subheader("Insider Activity Detected")
    st.caption("Suspicious on-chain patterns found by the analyzer")

    if events:
        for ev in events:
            sev = ev.get("severity", "low")
            icon = SEV_ICON.get(sev, "")
            ev_type = EVENT_NAME.get(ev.get("event_type", ""), ev.get("event_type", ""))
            chain = CHAIN_NAME.get(ev.get("chain", ""), ev.get("chain", ""))
            when = ev.get("detected_at", "")

            details = {}
            try:
                details = json.loads(ev.get("details", "{}"))
            except Exception:
                pass

            desc = []
            if details.get("balance_pct"):
                desc.append(f"Holds **{details['balance_pct']:.1f}%** of total supply")
            if details.get("bundle_size"):
                desc.append(f"**{details['bundle_size']}** wallets in 1 transaction")
            if details.get("amount"):
                desc.append(f"Amount: **{details['amount']:,.0f}** tokens")

            label = f"{icon} {SEV_LABEL.get(sev, sev)} | {chain} | {ev_type}"
            with st.expander(label, expanded=(sev == "high")):
                st.markdown(f"**Type:** {ev_type}")
                st.markdown(f"**Chain:** {chain}")
                st.markdown(f"**Token:** `{ev.get('token_address', '-')}`")
                st.markdown(f"**Wallet:** `{ev.get('wallet_address', '-')}`")
                if desc:
                    st.markdown(f"**Details:** {' · '.join(desc)}")
                st.markdown(f"**Detected:** {when}")

        st.divider()
        st.subheader("Summary")
        df_ev = pd.DataFrame(events)
        ca, cb = st.columns(2)
        with ca:
            if "event_type" in df_ev.columns:
                st.markdown("**By Type**")
                st.bar_chart(df_ev["event_type"].map(lambda x: EVENT_NAME.get(x, x)).value_counts())
        with cb:
            if "chain" in df_ev.columns:
                st.markdown("**By Chain**")
                st.bar_chart(df_ev["chain"].map(lambda x: CHAIN_NAME.get(x, x)).value_counts())
    else:
        st.info("No insider activity detected in the latest scan. Tokens may be clean, or try scanning again.")

    st.divider()
    st.subheader("Glossary")
    st.markdown("""
| Term | Meaning | Risk |
|------|---------|------|
| **Sniper (Early Buy)** | Wallet that bought in the very first block after launch. Likely a bot or insider with advance info. | High |
| **Dev Large Holding** | Token creator still holds a large % of supply. Rug pull risk. | High |
| **Wallet Cluster** | Multiple wallets funded by the same source. Coordinated insider activity. | High |
| **Bundled Buy** | Many wallets bought in a single transaction (Solana). Insider sniping tactic. | High |
| **Whale Dominance** | One wallet holds >10% of supply. Can crash the price at any time. | Medium |
| **Early Buyer** | Among the first wallets to buy. Not always malicious, but worth watching. | Medium |
""")


# ── TAB 3: Wallet Clusters ──
with tab3:
    st.subheader("Wallet Clusters Detected")
    st.caption("Wallets funded by the same source = likely one person or coordinated group")

    if clusters:
        for cl in clusters:
            chain = CHAIN_NAME.get(cl.get("chain", ""), cl.get("chain", ""))
            funder = cl.get("funder_address", "")
            size = cl.get("cluster_size", 0)
            total = cl.get("total_bought_usd", 0)

            with st.expander(f"🔴 {chain} — Funder: {fmt_addr(funder)} — {size} linked wallets"):
                st.markdown(f"**Chain:** {chain}")
                st.markdown(f"**Funder Address:**")
                st.code(funder)
                st.markdown(f"**Linked Wallets:** {size}")
                st.markdown(f"**Total Bought:** {fmt_usd(total)}")
                st.markdown(f"**Detected:** {cl.get('detected_at', '-')}")

                wallets = []
                try:
                    wallets = json.loads(cl.get("wallet_addresses", "[]"))
                except Exception:
                    pass
                if wallets:
                    st.markdown("**Wallet List:**")
                    for i, w in enumerate(wallets, 1):
                        st.code(f"{i}. {w}")
    else:
        st.info("No wallet clusters detected yet.")


# ── TAB 4: Manual Scan ──
with tab4:
    st.subheader("Scan & Analyze")

    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown("#### Search New Meme Coins")
        st.caption("Search Dexscreener for newly launched tokens")

        kw = st.text_input("Keywords", placeholder="e.g. pepe, doge, trump, ai")
        ml = st.number_input("Min Liquidity (USD)", min_value=0, value=500, step=100)

        if st.button("🚀 Start Scan", use_container_width=True, type="primary"):
            with st.spinner("Scanning Dexscreener..."):
                if kw:
                    queries = [k.strip() for k in kw.split(",") if k.strip()]
                    res = []
                    for q in queries:
                        res.extend(search_meme_tokens(query=q, min_liquidity=ml))
                        time.sleep(0.3)
                else:
                    res = scan_new_memes()
                    res = [t for t in res if t.get("liquidity_usd", 0) >= ml]

                for t in res:
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

                st.success(f"Found **{len(res)}** tokens!")
                for t in res[:15]:
                    ch = CHAIN_NAME.get(t["chain"], t["chain"])
                    st.markdown(
                        f"**{ch}** · **{t.get('symbol', '?')}** ({t.get('name', '')}) · "
                        f"Liq: {fmt_usd(t.get('liquidity_usd'))} · MCap: {fmt_usd(t.get('market_cap'))}"
                    )

    with col_r:
        st.markdown("#### Analyze Specific Token")
        st.caption("Enter a contract address to check for insider activity")

        ac = st.selectbox("Chain", SUPPORTED_CHAINS, format_func=lambda x: CHAIN_NAME.get(x, x), key="ac")
        aa = st.text_input("Token Address", placeholder="0x... or Solana address", key="aa")

        if st.button("🔍 Analyze", use_container_width=True):
            if not aa:
                st.warning("Enter a token address first.")
            else:
                with st.spinner(f"Analyzing on {CHAIN_NAME.get(ac, ac)}..."):
                    results = analyze_token(ac, aa)
                if not results:
                    st.success("No suspicious activity detected!")
                else:
                    for r in results:
                        sev = r.get("severity", "low")
                        msg = r.get("msg", str(r))
                        rt = r.get("type", "")
                        if rt == "error":
                            st.error(f"Error: {msg}")
                        elif sev == "high":
                            st.error(f"🔴 **HIGH** — {msg}")
                        elif sev == "medium":
                            st.warning(f"🟡 **WARN** — {msg}")
                        else:
                            st.info(f"🟢 {msg}")
                        if r.get("wallets"):
                            with st.expander(f"View {len(r['wallets'])} related wallets"):
                                for w in r["wallets"]:
                                    st.code(w)


# ── Donate (small, bottom) ──
st.divider()
with st.expander("☕ Buy Me a Coffee — Support This Project"):
    st.markdown(
        "This tool is **free & open-source**. "
        "If it helped you dodge a rug pull or spot an insider early, "
        "consider sending a small tip. Every bit helps keep this project alive!"
    )
    col_s, col_e = st.columns(2)
    with col_s:
        st.markdown("**Solana (SOL)**")
        st.code("2vMBrEcTd85b1CUwcbU6f3PuKmdUCHkM8kq6mMVp82Ca")
    with col_e:
        st.markdown("**ETH / BSC / Base / Arbitrum**")
        st.code("0x2D36d2658B46C509Ecc9BB68D7844bb3ef9D337a")
    st.caption("Click the address to copy · Any amount is appreciated · Thank you, fren! 🤝")


# ── Footer ──
f1, f2, f3 = st.columns(3)
f1.caption(f"Updated: {datetime.now().strftime('%d %b %Y, %H:%M')}")
f2.caption(f"Tracking {len(SUPPORTED_CHAINS)} blockchains")
f3.caption("[GitHub](https://github.com/reodkt/meme-insider-tracker)")
