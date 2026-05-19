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
from core.config import SUPPORTED_CHAINS
from chains.dexscreener import scan_new_memes, search_meme_tokens
from analyzers.smart_analyzer import batch_analyze, analyze_token_full

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
    .stTabs [data-baseweb="tab"] { font-size: 0.8rem !important; padding: 6px 10px !important; }
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
    "honeypot_signal": "🍯 Honeypot",
    "liquidity_trap": "🪤 Liquidity Trap",
    "wash_trading": "🔄 Wash Trading",
    "coordinated_buying": "🤝 Coordinated Buying",
    "mass_dumping": "📉 Mass Dumping",
    "pump_and_dump": "💣 Pump & Dump",
    "crash_alert": "💥 Price Crash",
    "price_manipulation": "📊 Price Manipulation",
    "fresh_token_risk": "🆕 New Token Risk",
    "rug_pull_risk": "🚨 Rug Pull Risk",
    "early_sniper": "🎯 Sniper",
    "dev_large_holding": "👨‍💻 Dev Holding",
    "wallet_cluster": "🕸️ Wallet Cluster",
    "whale_holding": "🐋 Whale",
    "early_buyer": "⚡ Early Buyer",
    "bundled_buy": "📦 Bundled Buy",
}
SEV_LABEL = {"high": "HIGH", "medium": "WARN", "low": "INFO"}
SEV_ICON = {"high": "🔴", "medium": "🟡", "low": "🟢"}

DEX_URL = "https://dexscreener.com"
EXPLORER_URL = {
    "ethereum": "https://etherscan.io/token/",
    "bsc": "https://bscscan.com/token/",
    "base": "https://basescan.org/token/",
    "arbitrum": "https://arbiscan.io/token/",
    "polygon": "https://polygonscan.com/token/",
    "avalanche": "https://snowscan.xyz/token/",
    "solana": "https://solscan.io/token/",
}


def dex_link(chain, addr):
    return f"{DEX_URL}/{chain}/{addr}"


def exp_link(chain, addr):
    b = EXPLORER_URL.get(chain, "")
    return f"{b}{addr}" if b else ""


def wallet_exp_link(chain, addr):
    b = EXPLORER_URL.get(chain, "")
    return f"{b.replace('/token/', '/address/')}{addr}" if b else ""


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


# ══════════════════════════════════════════════════════
# AUTO-SCAN + ANALYZE ALL CHAINS ON FIRST LOAD
# ══════════════════════════════════════════════════════
if "loaded" not in st.session_state:
    st.session_state.loaded = False

if not st.session_state.loaded:
    with st.spinner("🔍 Scanning all chains for meme coins & analyzing insider patterns..."):
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

            # Analyze ALL tokens (all chains) using smart analyzer
            batch_analyze(found)

        except Exception:
            pass

    st.session_state.loaded = True
    st.rerun()


# ── Sidebar ──
with st.sidebar:
    st.title("🔍 Meme Insider Tracker")
    st.caption("Real-time insider detection · All chains")
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
    sel_type = st.multiselect(
        "Event Types",
        list(EVENT_NAME.keys()),
        format_func=lambda x: EVENT_NAME.get(x, x),
        default=[],
        help="Leave empty to show all types",
    )

    st.divider()

    if st.button("🔄 Rescan Now", use_container_width=True, type="primary"):
        st.session_state.loaded = False
        st.rerun()

    auto = st.toggle("Auto-refresh (30s)")
    st.divider()
    st.caption("v2.0 · Free · No API Key · All Chains")

if auto:
    time.sleep(30)
    st.session_state.loaded = False
    st.rerun()


# ── Load Data ──
cf = sel_chain if sel_chain != "All" else None
sf = sel_sev if sel_sev != "All" else None
events_raw = get_recent_events(limit=500, chain=cf, severity=sf)
tokens = get_tracked_tokens(limit=300, chain=cf)
clusters = get_clusters(limit=50, chain=cf)

# Filter events by type if selected
if sel_type:
    events = [e for e in events_raw if e.get("event_type") in sel_type]
else:
    events = events_raw


# ── Header ──
st.title("🔍 Meme Insider Tracker")
st.markdown("Automatic insider & whale detection for meme coins — **7 chains, real-time, 100% free.**")

# ── Metrics ──
high_ct = len([e for e in events if e.get("severity") == "high"])
warn_ct = len([e for e in events if e.get("severity") == "medium"])
chains_active = len(set(e.get("chain", "") for e in events if e.get("chain")))
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Tokens", len(tokens))
c2.metric("Alerts", len(events))
c3.metric("🔴 High", high_ct)
c4.metric("🟡 Warn", warn_ct)
c5.metric("Chains", chains_active)


# ── Tabs ──
tab1, tab2, tab3, tab4 = st.tabs([
    "🚨 Insider Alerts", "📊 Tokens", "🕸️ Wallet Clusters", "⚡ Scan & Analyze",
])


# ══════════════════════════════════════════════════════
# TAB 1: INSIDER ALERTS (main tab now)
# ══════════════════════════════════════════════════════
with tab1:
    st.subheader("🚨 Insider Activity — All Chains")
    st.caption(
        "Suspicious patterns detected via on-chain data + Dexscreener analytics. "
        "Use the sidebar filters to narrow by chain, severity, or event type."
    )

    if events:
        # Group by severity
        high_events = [e for e in events if e.get("severity") == "high"]
        med_events = [e for e in events if e.get("severity") == "medium"]
        low_events = [e for e in events if e.get("severity") == "low"]

        if high_events:
            st.markdown("### 🔴 High Risk")
        for ev in high_events:
            _render_event(ev) if False else None  # placeholder, rendered below

        # Render all events
        for ev in events:
            sev = ev.get("severity", "low")
            icon = SEV_ICON.get(sev, "")
            ev_type = EVENT_NAME.get(ev.get("event_type", ""), ev.get("event_type", ""))
            chain = CHAIN_NAME.get(ev.get("chain", ""), ev.get("chain", ""))
            when = ev.get("detected_at", "")
            token_addr = ev.get("token_address", "")
            raw_chain = ev.get("chain", "")

            details = {}
            try:
                details = json.loads(ev.get("details", "{}"))
            except Exception:
                pass

            # Build detail lines
            detail_lines = []
            if details.get("buys_24h") or details.get("buys"):
                b = details.get("buys_24h") or details.get("buys", 0)
                s = details.get("sells_24h") or details.get("sells", 0)
                detail_lines.append(f"Buys: **{b}** · Sells: **{s}**")
            if details.get("mcap_liq_ratio"):
                detail_lines.append(f"MCap/Liq ratio: **{details['mcap_liq_ratio']}x**")
            if details.get("vol_liq_ratio"):
                detail_lines.append(f"Volume/Liq ratio: **{details['vol_liq_ratio']}x**")
            if details.get("buy_ratio"):
                detail_lines.append(f"Buy ratio: **{details['buy_ratio']:.0%}**")
            if details.get("sell_ratio"):
                detail_lines.append(f"Sell ratio: **{details['sell_ratio']:.0%}**")
            if details.get("chg_1h"):
                detail_lines.append(f"1h change: **{details['chg_1h']:+.0f}%**")
            if details.get("chg_24h"):
                detail_lines.append(f"24h change: **{details['chg_24h']:+.0f}%**")
            if details.get("chg_5m"):
                detail_lines.append(f"5m change: **{details['chg_5m']:+.0f}%**")
            if details.get("score"):
                detail_lines.append(f"Risk score: **{details['score']}/100**")
            if details.get("reasons"):
                reasons = details["reasons"]
                if isinstance(reasons, list):
                    detail_lines.append(f"Reasons: {', '.join(reasons)}")
            if details.get("balance_pct"):
                detail_lines.append(f"Holds **{details['balance_pct']:.1f}%** of supply")
            if details.get("age_hours"):
                detail_lines.append(f"Token age: **{details['age_hours']:.1f}h**")

            label = f"{icon} {SEV_LABEL.get(sev, sev)} · {chain} · {ev_type}"
            with st.expander(label, expanded=(sev == "high")):
                col_info, col_links = st.columns([3, 1])
                with col_info:
                    st.markdown(f"**{ev_type}** on **{chain}**")
                    st.markdown(f"Token: `{token_addr}`")
                    if ev.get("wallet_address") and ev["wallet_address"] != ev.get("event_type"):
                        st.markdown(f"Wallet: `{ev['wallet_address']}`")
                    for line in detail_lines:
                        st.markdown(f"- {line}")
                    st.caption(f"Detected: {when}")
                with col_links:
                    st.link_button("📈 Chart", dex_link(raw_chain, token_addr), use_container_width=True)
                    st.link_button("🔗 Explorer", exp_link(raw_chain, token_addr), use_container_width=True)
                    if ev.get("wallet_address") and ev["wallet_address"] != ev.get("event_type"):
                        st.link_button("👛 Wallet", wallet_exp_link(raw_chain, ev["wallet_address"]), use_container_width=True)

        # Summary charts
        st.divider()
        st.subheader("📈 Summary")

        cx, cy, cz = st.columns(3)
        df_ev = pd.DataFrame(events)

        with cx:
            if "event_type" in df_ev.columns:
                st.markdown("**By Alert Type**")
                st.bar_chart(df_ev["event_type"].map(lambda x: EVENT_NAME.get(x, x)).value_counts())
        with cy:
            if "chain" in df_ev.columns:
                st.markdown("**By Chain**")
                st.bar_chart(df_ev["chain"].map(lambda x: CHAIN_NAME.get(x, x)).value_counts())
        with cz:
            if "severity" in df_ev.columns:
                st.markdown("**By Severity**")
                st.bar_chart(df_ev["severity"].value_counts())

    else:
        st.info("No insider activity detected yet. Click **Rescan Now** or wait for auto-refresh.")

    # Glossary
    st.divider()
    with st.expander("📖 What do these alerts mean?"):
        st.markdown("""
| Alert | What It Means | Risk |
|-------|--------------|------|
| 🍯 **Honeypot** | Many buys but almost zero sells — users may be unable to sell | 🔴 High |
| 🪤 **Liquidity Trap** | Market cap is way higher than liquidity — price crashes on any sell | 🔴 High |
| 🔄 **Wash Trading** | Volume is abnormally high vs liquidity — volume is likely fake | 🔴 High |
| 💣 **Pump & Dump** | Price spiked then crashed — classic insider manipulation | 🔴 High |
| 📉 **Mass Dumping** | Overwhelming sell transactions — insiders exiting | 🔴 High |
| 💥 **Price Crash** | Price dropped >70% in 24h — likely rug pull | 🔴 High |
| 🚨 **Rug Pull Risk** | Composite score based on multiple danger signals | 🔴 High |
| 🤝 **Coordinated Buy** | Extreme buy/sell imbalance — possible insider accumulation | 🟡 Medium |
| 📊 **Price Manipulation** | >100% spike in 5 minutes — coordinated pump | 🟡 Medium |
| 🆕 **New Token Risk** | Very fresh token with multiple risk factors | 🟡 Medium |
| 🎯 **Sniper** | Bought in the very first block — bot or insider | 🔴 High |
| 🕸️ **Wallet Cluster** | Multiple wallets funded from same source | 🔴 High |
| 🐋 **Whale** | One wallet holds >10% of supply | 🟡 Medium |
""")


# ══════════════════════════════════════════════════════
# TAB 2: TOKEN LIST
# ══════════════════════════════════════════════════════
with tab2:
    st.subheader("📊 Tracked Meme Coins")
    st.caption("Live data from Dexscreener — click Chart to view price history")

    if tokens:
        rows = []
        for t in tokens:
            price = t.get("price_usd", 0)
            chain = t.get("chain", "")
            addr = t.get("address", "")
            pair = t.get("pair_address", "")
            target = pair if pair else addr
            rows.append({
                "Chain": CHAIN_NAME.get(chain, chain),
                "Symbol": t.get("symbol", "-"),
                "Name": t.get("name", "-"),
                "Price": f"${price:,.8f}" if price and price < 0.01
                         else f"${price:,.4f}" if price and price < 1
                         else f"${price:,.2f}" if price else "-",
                "Market Cap": fmt_usd(t.get("market_cap")),
                "Liquidity": fmt_usd(t.get("liquidity_usd")),
                "Vol 24h": fmt_usd(t.get("volume_24h")),
                "DEX": t.get("dex", "-"),
                "Chart": dex_link(chain, target),
                "Explorer": exp_link(chain, addr),
            })
        st.dataframe(
            pd.DataFrame(rows), use_container_width=True, height=480, hide_index=True,
            column_config={
                "Chart": st.column_config.LinkColumn("Chart", display_text="📈 View"),
                "Explorer": st.column_config.LinkColumn("Explorer", display_text="🔗 View"),
            },
        )
        st.caption(f"{len(tokens)} tokens across {len(set(t.get('chain','') for t in tokens))} chains")
    else:
        st.info("No tokens found yet. Click **Rescan Now**.")


# ══════════════════════════════════════════════════════
# TAB 3: WALLET CLUSTERS
# ══════════════════════════════════════════════════════
with tab3:
    st.subheader("🕸️ Linked Wallet Groups")
    st.caption("Wallets funded by the same source = likely one person or coordinated group")

    if clusters:
        for cl in clusters:
            chain = CHAIN_NAME.get(cl.get("chain", ""), cl.get("chain", ""))
            raw_chain = cl.get("chain", "")
            funder = cl.get("funder_address", "")
            size = cl.get("cluster_size", 0)
            total = cl.get("total_bought_usd", 0)

            with st.expander(f"🔴 {chain} · Funder: {fmt_addr(funder)} · {size} wallets"):
                st.markdown(f"**Chain:** {chain}")
                st.markdown("**Funder:**")
                st.code(funder)
                st.markdown(f"**Linked Wallets:** {size}")
                st.markdown(f"**Total Bought:** {fmt_usd(total)}")
                st.markdown(f"**Detected:** {cl.get('detected_at', '-')}")

                st.link_button("👛 Funder on Explorer", wallet_exp_link(raw_chain, funder), use_container_width=True)

                wallets = []
                try:
                    wallets = json.loads(cl.get("wallet_addresses", "[]"))
                except Exception:
                    pass
                if wallets:
                    st.markdown("**Wallets:**")
                    for i, w in enumerate(wallets, 1):
                        st.code(f"{i}. {w}")
    else:
        st.info("No wallet clusters detected yet. These are found during deep on-chain analysis.")


# ══════════════════════════════════════════════════════
# TAB 4: MANUAL SCAN & ANALYZE
# ══════════════════════════════════════════════════════
with tab4:
    st.subheader("⚡ Scan & Analyze")

    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown("#### Search New Meme Coins")
        st.caption("Scan Dexscreener for new launches + auto-analyze for insider patterns")

        kw = st.text_input("Keywords", placeholder="e.g. pepe, doge, trump, ai")
        ml = st.number_input("Min Liquidity (USD)", min_value=0, value=500, step=100)

        if st.button("🚀 Scan + Analyze", use_container_width=True, type="primary"):
            with st.spinner("Scanning & analyzing all chains..."):
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

                # Analyze all found tokens
                analysis = batch_analyze(res)

                st.success(f"Found **{len(res)}** tokens · **{len(analysis)}** with alerts!")

                for t in res[:20]:
                    ch = CHAIN_NAME.get(t["chain"], t["chain"])
                    pair = t.get("pair_address", "") or t.get("token_address", "")
                    link = dex_link(t["chain"], pair)
                    key = f"{t['chain']}:{t.get('token_address','').lower()}"
                    alert_count = len(analysis.get(key, {}).get("findings", []))
                    alert_str = f" · **{alert_count} alerts** 🚨" if alert_count > 0 else ""
                    st.markdown(
                        f"**{ch}** · **{t.get('symbol', '?')}** · "
                        f"Liq: {fmt_usd(t.get('liquidity_usd'))} · "
                        f"MCap: {fmt_usd(t.get('market_cap'))}"
                        f"{alert_str} · [📈 Chart]({link})"
                    )

    with col_r:
        st.markdown("#### Analyze Specific Token")
        st.caption("Enter a contract address to check for insider activity on any chain")

        ac = st.selectbox("Chain", SUPPORTED_CHAINS, format_func=lambda x: CHAIN_NAME.get(x, x), key="ac")
        aa = st.text_input("Token Address", placeholder="0x... or Solana address", key="aa")

        if st.button("🔍 Deep Analyze", use_container_width=True):
            if not aa:
                st.warning("Enter a token address first.")
            else:
                with st.spinner(f"Deep analyzing on {CHAIN_NAME.get(ac, ac)}..."):
                    results = analyze_token_full(ac, aa)

                if not results:
                    st.success("✅ No suspicious activity detected!")
                else:
                    st.warning(f"Found **{len(results)}** alert(s):")
                    for r in results:
                        sev = r.get("severity", "low")
                        msg = r.get("msg", str(r))
                        rt = r.get("type", "")
                        if sev == "high":
                            st.error(f"🔴 {msg}")
                        elif sev == "medium":
                            st.warning(f"🟡 {msg}")
                        else:
                            st.info(f"🟢 {msg}")

                    st.link_button("📈 View on Dexscreener", dex_link(ac, aa), use_container_width=True)
                    st.link_button("🔗 View on Explorer", exp_link(ac, aa), use_container_width=True)


# ══════════════════════════════════════════════════════
# DONATE (small expander at bottom)
# ══════════════════════════════════════════════════════
st.divider()
with st.expander("☕ Buy Me a Coffee — Support This Project"):
    st.markdown(
        "This tool is **free & open-source**. "
        "If it helped you dodge a rug pull or spot an insider early, "
        "consider sending a small tip to keep this project alive!"
    )
    cs, ce = st.columns(2)
    with cs:
        st.markdown("**Solana (SOL)**")
        st.code("2vMBrEcTd85b1CUwcbU6f3PuKmdUCHkM8kq6mMVp82Ca")
    with ce:
        st.markdown("**ETH / BSC / Base / Arb**")
        st.code("0x2D36d2658B46C509Ecc9BB68D7844bb3ef9D337a")
    st.caption("Click address to copy · Any amount appreciated · Thanks fren! 🤝")

# ── Footer ──
f1, f2, f3 = st.columns(3)
f1.caption(f"Updated: {datetime.now().strftime('%d %b %Y, %H:%M')}")
f2.caption(f"Tracking {len(SUPPORTED_CHAINS)} chains")
f3.caption("[GitHub](https://github.com/reodkt/meme-insider-tracker)")
