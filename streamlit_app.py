"""
Meme Insider Tracker — Real-time meme coin insider detection across all chains.
"""

import streamlit as st
import pandas as pd
import json
import time
from datetime import datetime

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import init_db, get_recent_events, get_tracked_tokens, get_clusters, upsert_token, purge_old_data
from core.config import SUPPORTED_CHAINS
from chains.dexscreener import scan_new_memes, search_meme_tokens
from analyzers.smart_analyzer import batch_analyze, analyze_token_full
from feeds.ct_feed import get_ct_feed

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
CHAIN_NAME = {"solana": "Solana"}
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

# Token types considered scam/dangerous — filtered out from Tokens tab by default
SCAM_TYPES = {
    "honeypot_signal", "rug_pull_risk", "liquidity_trap",
    "pump_and_dump", "wash_trading", "mass_dumping", "crash_alert",
}

DEX_URL = "https://dexscreener.com"
EXPLORER_URL = {"solana": "https://solscan.io/token/"}


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
    with st.spinner("🔍 Scanning Solana for meme coins & analyzing insider patterns..."):
        # Purge stale data (>6h) before every scan
        purge_old_data(max_age_hours=6)

        try:
            found = scan_new_memes(queries=[
                "meme", "pepe", "doge", "bonk", "moon",
                "shib", "floki", "trump", "ai", "cat",
                "pump", "sol", "solana", "degen", "frog",
                "dog", "ape", "based", "jup", "wen",
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
sel_chain = "solana"  # Solana only
with st.sidebar:
    st.title("🔍 Meme Insider Tracker")
    st.caption("Real-time insider detection · Solana")
    st.divider()

    st.subheader("Filters")
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

    if st.button("🔄 Rescan Now", width="stretch", type="primary"):
        st.session_state.loaded = False
        st.rerun()

    auto = st.toggle("Auto-refresh (30s)")
    show_scam = st.toggle("Show scam/honeypot tokens", value=False,
                          help="Show tokens flagged as honeypot, rug pull, pump & dump, etc.")
    st.divider()
    st.caption("v2.0 · Solana · Free · No API Key")

if auto:
    time.sleep(30)
    st.session_state.loaded = False
    st.rerun()


# ── Load Data ──
cf = "solana"
sf = sel_sev if sel_sev != "All" else None
events_raw = get_recent_events(limit=500, chain=cf, severity=sf)
all_events_raw = get_recent_events(limit=2000, chain=cf, severity=None)
tokens_raw = get_tracked_tokens(limit=300, chain=cf)
clusters = get_clusters(limit=50, chain=cf)

# Filter events by type if selected
if sel_type:
    events = [e for e in events_raw if e.get("event_type") in sel_type]
else:
    events = events_raw

# Build set of flagged (scam) token keys: "chain:address"
_flagged_tokens = set()
for ev in all_events_raw:
    if ev.get("event_type") in SCAM_TYPES and ev.get("severity") == "high":
        key = f"{ev.get('chain','')}:{ev.get('token_address','').lower()}"
        _flagged_tokens.add(key)

# Filter tokens: exclude scam tokens unless toggle is on
if show_scam:
    tokens = tokens_raw
else:
    tokens = [
        t for t in tokens_raw
        if f"{t.get('chain','')}:{t.get('address','').lower()}" not in _flagged_tokens
    ]


# ── Header ──
st.title("🔍 Meme Insider Tracker")
st.markdown("Automatic insider & whale detection for **Solana meme coins** — real-time, 100% free.")

# ── Metrics ──
high_ct = len([e for e in events if e.get("severity") == "high"])
warn_ct = len([e for e in events if e.get("severity") == "medium"])
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Tokens", len(tokens))
c2.metric("🛡️ Filtered", len(_flagged_tokens))
c3.metric("Alerts", len(events))
c4.metric("🔴 High", high_ct)
c5.metric("🟡 Warn", warn_ct)


# ── Tabs ──
tab1, tab2, tab5, tab3, tab4 = st.tabs([
    "🚨 Insider Alerts", "📊 Tokens", "📱 CT Live", "🕸️ Wallet Clusters", "⚡ Scan & Analyze",
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
                    st.link_button("📈 Chart", dex_link(raw_chain, token_addr), width="stretch")
                    st.link_button("🔗 Explorer", exp_link(raw_chain, token_addr), width="stretch")
                    if ev.get("wallet_address") and ev["wallet_address"] != ev.get("event_type"):
                        st.link_button("👛 Wallet", wallet_exp_link(raw_chain, ev["wallet_address"]), width="stretch")

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
    st.subheader("📊 Tracked Meme Coins — Sorted by Insider Activity")
    st.caption("Tokens with the most insider alerts shown first. Live data from Dexscreener.")

    filtered_ct = len(tokens_raw) - len(tokens)
    if filtered_ct > 0:
        st.info(f"🛡️ **{filtered_ct}** scam/honeypot tokens hidden. Enable *\"Show scam/honeypot tokens\"* in sidebar to see them.")

    if tokens:
        # Count alerts per token from events
        _token_alert_count = {}
        for ev in all_events_raw:
            tk = f"{ev.get('chain','')}:{ev.get('token_address','').lower()}"
            _token_alert_count[tk] = _token_alert_count.get(tk, 0) + 1

        # Sort tokens by alert count (most active first)
        tokens_sorted = sorted(
            tokens,
            key=lambda t: _token_alert_count.get(
                f"{t.get('chain','')}:{t.get('address','').lower()}", 0
            ),
            reverse=True,
        )

        rows = []
        for t in tokens_sorted:
            price = t.get("price_usd", 0)
            chain = t.get("chain", "")
            addr = t.get("address", "")
            pair = t.get("pair_address", "")
            target = pair if pair else addr
            tk = f"{chain}:{addr.lower()}"
            is_flagged = tk in _flagged_tokens
            alert_ct = _token_alert_count.get(tk, 0)
            rows.append({
                "Alerts": f"🔴 {alert_ct}" if alert_ct > 0 else "-",
                "Status": "🚫 SCAM" if is_flagged else "✅ OK",
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
            pd.DataFrame(rows), width="stretch", height=480, hide_index=True,
            column_config={
                "Chart": st.column_config.LinkColumn("Chart", display_text="📈 View"),
                "Explorer": st.column_config.LinkColumn("Explorer", display_text="🔗 View"),
            },
        )
        st.caption(f"{len(tokens)} tokens across {len(set(t.get('chain','') for t in tokens))} chains")
    else:
        st.info("No tokens found yet. Click **Rescan Now**.")


# ══════════════════════════════════════════════════════
# TAB 5: CT LIVE FEED
# ══════════════════════════════════════════════════════
with tab5:
    st.subheader("📱 CT & Crypto Live Feed")
    st.caption("Real-time crypto news, trending coins, Reddit discussions, and boosted tokens. Auto-refreshes with rescan.")

    # Source filter
    src_filter = st.multiselect(
        "Filter Sources",
        ["Reddit", "CoinGecko Trending", "Crypto News", "Dexscreener Boosted"],
        default=[],
        help="Leave empty to show all sources",
        key="ct_src_filter",
    )

    SRC_MAP = {
        "Reddit": "reddit",
        "CoinGecko Trending": "trending",
        "Crypto News": "news",
        "Dexscreener Boosted": "boosted",
    }

    with st.spinner("Loading CT feed..."):
        ct_feed = get_ct_feed(limit=60)

    if src_filter:
        allowed = {SRC_MAP[s] for s in src_filter}
        ct_feed = [f for f in ct_feed if f.get("type") in allowed or f.get("type", "").startswith(tuple(allowed))]

    if ct_feed:
        # Summary metrics
        fc1, fc2, fc3, fc4 = st.columns(4)
        fc1.metric("Total Items", len(ct_feed))
        fc2.metric("🟠 Reddit", len([f for f in ct_feed if f["type"] == "reddit"]))
        fc3.metric("📰 News", len([f for f in ct_feed if f["type"] == "news"]))
        fc4.metric("🦎 Trending", len([f for f in ct_feed if f["type"].startswith("trending")]))

        st.divider()

        for item in ct_feed:
            src_icon = item.get("source_icon", "")
            source = item.get("source", "")
            title = item.get("title", "")
            url = item.get("url", "")
            time_str = item.get("time_str", "")
            item_type = item.get("type", "")

            # Color by type
            if item_type == "reddit":
                score = item.get("score", 0)
                comments = item.get("comments", 0)
                with st.container():
                    st.markdown(
                        f"{src_icon} **{source}** · {time_str} · "
                        f"⬆️ {score} · 💬 {comments}"
                    )
                    st.markdown(f"[{title}]({url})")
                    st.divider()

            elif item_type.startswith("trending"):
                with st.container():
                    st.markdown(f"{src_icon} **{source}**")
                    st.markdown(f"[{title}]({url})")
                    st.divider()

            elif item_type == "news":
                desc = item.get("description", "")
                with st.container():
                    st.markdown(f"{src_icon} **{source}** · {time_str}")
                    st.markdown(f"**[{title}]({url})**")
                    if desc:
                        st.caption(desc[:150])
                    st.divider()

            elif item_type == "boosted":
                chain = item.get("chain", "")
                with st.container():
                    st.markdown(
                        f"{src_icon} **{source}** · "
                        f"{CHAIN_NAME.get(chain, chain)}"
                    )
                    st.markdown(f"[{title}]({url})")
                    st.divider()
    else:
        st.info("No CT feed items found. Try again in a moment.")


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

                st.link_button("👛 Funder on Explorer", wallet_exp_link(raw_chain, funder), width="stretch")

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

        if st.button("🚀 Scan + Analyze", width="stretch", type="primary"):
            with st.spinner("Scanning & analyzing Solana meme coins..."):
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
        st.caption("Enter a Solana token address to check for insider activity")

        ac = "solana"
        aa = st.text_input("Token Address", placeholder="Solana token address...", key="aa")

        if st.button("🔍 Deep Analyze", width="stretch"):
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

                    st.link_button("📈 View on Dexscreener", dex_link(ac, aa), width="stretch")
                    st.link_button("🔗 View on Explorer", exp_link(ac, aa), width="stretch")


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
    st.markdown("**Solana (SOL)**")
    st.code("2vMBrEcTd85b1CUwcbU6f3PuKmdUCHkM8kq6mMVp82Ca")
    st.caption("Click address to copy · Any amount appreciated · Thanks fren! 🤝")

# ── Footer ──
f1, f2 = st.columns(2)
f1.caption(f"Updated: {datetime.now().strftime('%d %b %Y, %H:%M')} · Solana only")
f2.caption("[GitHub](https://github.com/reodkt/meme-insider-tracker)")
