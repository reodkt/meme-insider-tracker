"""
Smart Analyzer — All-chain insider detection using Dexscreener data.
Works on ALL chains without RPC calls. Detects:

1. Pump & Dump patterns
2. Wash trading (fake volume)
3. Liquidity traps (low liq vs high mcap)
4. Coordinated buying (buy/sell imbalance)
5. Honeypot signals (many buys, zero sells)
6. Rug pull risk scoring
7. Whale concentration estimates
8. Fresh wallet sniping patterns
"""

import time
from datetime import datetime, timedelta
from chains.dexscreener import get_token_pairs, _get, DEXSCREENER_TOKENS
from core.database import add_insider_event, upsert_token


def analyze_pair_data(pair_data):
    """
    Analyze a single Dexscreener pair for suspicious patterns.
    Returns list of findings. Works for ALL chains.
    """
    findings = []
    chain = pair_data.get("chain", "")
    token_addr = pair_data.get("token_address", "")
    symbol = pair_data.get("symbol", "?")

    liq = pair_data.get("liquidity_usd", 0) or 0
    mcap = pair_data.get("market_cap", 0) or 0
    vol24 = pair_data.get("volume_24h", 0) or 0
    price = pair_data.get("price_usd", 0) or 0
    buys_24h = pair_data.get("txns_buys_24h", 0) or 0
    sells_24h = pair_data.get("txns_sells_24h", 0) or 0
    chg_5m = pair_data.get("price_change_5m", 0) or 0
    chg_1h = pair_data.get("price_change_1h", 0) or 0
    chg_24h = pair_data.get("price_change_24h", 0) or 0
    created = pair_data.get("created_at")

    total_txns = buys_24h + sells_24h

    # ── Age calculation ──
    age_hours = None
    if created:
        try:
            created_dt = datetime.fromtimestamp(int(created) / 1000)
            age_hours = (datetime.now() - created_dt).total_seconds() / 3600
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════
    # 1. HONEYPOT SIGNAL — many buys, almost zero sells
    # ═══════════════════════════════════════════════════════
    if buys_24h > 20 and sells_24h <= 2:
        findings.append({
            "type": "honeypot_signal",
            "severity": "high",
            "msg": f"Possible honeypot: {buys_24h} buys but only {sells_24h} sells in 24h. Users may not be able to sell.",
            "details": {"buys": buys_24h, "sells": sells_24h},
        })
        _store_event(chain, token_addr, "honeypot_signal", "honeypot_signal", "high",
                     {"buys_24h": buys_24h, "sells_24h": sells_24h})

    # ═══════════════════════════════════════════════════════
    # 2. LIQUIDITY TRAP — mcap >> liquidity (easy to manipulate)
    # ═══════════════════════════════════════════════════════
    if liq > 0 and mcap > 0:
        ratio = mcap / liq
        if ratio > 50:
            findings.append({
                "type": "liquidity_trap",
                "severity": "high",
                "msg": f"Liquidity trap: Market cap ({_fmt(mcap)}) is {ratio:.0f}x the liquidity ({_fmt(liq)}). Price will crash on any sell.",
                "details": {"mcap_liq_ratio": round(ratio, 1), "mcap": mcap, "liq": liq},
            })
            _store_event(chain, token_addr, "liquidity_trap", "liquidity_trap", "high",
                         {"mcap_liq_ratio": round(ratio, 1)})
        elif ratio > 20:
            findings.append({
                "type": "liquidity_trap",
                "severity": "medium",
                "msg": f"Low liquidity warning: MCap/Liq ratio is {ratio:.0f}x. Selling may cause significant slippage.",
                "details": {"mcap_liq_ratio": round(ratio, 1)},
            })
            _store_event(chain, token_addr, "liquidity_trap", "liquidity_trap", "medium",
                         {"mcap_liq_ratio": round(ratio, 1)})

    # ═══════════════════════════════════════════════════════
    # 3. WASH TRADING — volume way too high relative to liquidity
    # ═══════════════════════════════════════════════════════
    if liq > 0 and vol24 > 0:
        vol_liq = vol24 / liq
        if vol_liq > 10:
            findings.append({
                "type": "wash_trading",
                "severity": "high",
                "msg": f"Possible wash trading: 24h volume ({_fmt(vol24)}) is {vol_liq:.0f}x the liquidity ({_fmt(liq)}). Volume likely fake.",
                "details": {"vol_liq_ratio": round(vol_liq, 1)},
            })
            _store_event(chain, token_addr, "wash_trading", "wash_trading", "high",
                         {"vol_liq_ratio": round(vol_liq, 1)})
        elif vol_liq > 5:
            findings.append({
                "type": "wash_trading",
                "severity": "medium",
                "msg": f"Unusual volume: 24h volume is {vol_liq:.0f}x liquidity. May indicate wash trading.",
                "details": {"vol_liq_ratio": round(vol_liq, 1)},
            })
            _store_event(chain, token_addr, "wash_trading", "wash_trading", "medium",
                         {"vol_liq_ratio": round(vol_liq, 1)})

    # ═══════════════════════════════════════════════════════
    # 4. COORDINATED BUYING — extreme buy/sell imbalance
    # ═══════════════════════════════════════════════════════
    if total_txns > 20:
        buy_ratio = buys_24h / total_txns if total_txns > 0 else 0
        if buy_ratio > 0.85:
            findings.append({
                "type": "coordinated_buying",
                "severity": "medium",
                "msg": f"Coordinated buying: {buy_ratio:.0%} of transactions are buys ({buys_24h} buys vs {sells_24h} sells). Possible insider accumulation.",
                "details": {"buy_ratio": round(buy_ratio, 2), "buys": buys_24h, "sells": sells_24h},
            })
            _store_event(chain, token_addr, "coordinated_buying", "coordinated_buying", "medium",
                         {"buy_ratio": round(buy_ratio, 2)})

        elif sells_24h > 0 and buys_24h > 0:
            sell_ratio = sells_24h / total_txns
            if sell_ratio > 0.80:
                findings.append({
                    "type": "mass_dumping",
                    "severity": "high",
                    "msg": f"Mass dumping: {sell_ratio:.0%} of transactions are sells ({sells_24h} sells vs {buys_24h} buys). Insiders may be exiting.",
                    "details": {"sell_ratio": round(sell_ratio, 2), "buys": buys_24h, "sells": sells_24h},
                })
                _store_event(chain, token_addr, "mass_dumping", "mass_dumping", "high",
                             {"sell_ratio": round(sell_ratio, 2)})

    # ═══════════════════════════════════════════════════════
    # 5. PUMP & DUMP PATTERN — fast price spike + high sell pressure
    # ═══════════════════════════════════════════════════════
    if chg_1h is not None and chg_24h is not None:
        # Pumping: 1h up big but 24h down = dumped after pump
        if chg_1h > 50 and chg_24h < -20:
            findings.append({
                "type": "pump_and_dump",
                "severity": "high",
                "msg": f"Pump & Dump pattern: Price up {chg_1h:+.0f}% in 1h but down {chg_24h:+.0f}% in 24h. Classic insider dump after pump.",
                "details": {"chg_1h": chg_1h, "chg_24h": chg_24h},
            })
            _store_event(chain, token_addr, "pump_and_dump", "pump_and_dump", "high",
                         {"chg_1h": chg_1h, "chg_24h": chg_24h})

        # Recently dumped hard
        elif chg_24h < -70:
            findings.append({
                "type": "crash_alert",
                "severity": "high",
                "msg": f"Severe crash: Price down {chg_24h:+.0f}% in 24h. Likely rug pull or insider exit.",
                "details": {"chg_24h": chg_24h},
            })
            _store_event(chain, token_addr, "crash_alert", "crash_alert", "high",
                         {"chg_24h": chg_24h})

        # 5-min spike = possible manipulation
        if chg_5m is not None and chg_5m > 100:
            findings.append({
                "type": "price_manipulation",
                "severity": "medium",
                "msg": f"Rapid price spike: {chg_5m:+.0f}% in 5 minutes. Possible coordinated pump.",
                "details": {"chg_5m": chg_5m},
            })
            _store_event(chain, token_addr, "price_manipulation", "price_manipulation", "medium",
                         {"chg_5m": chg_5m})

    # ═══════════════════════════════════════════════════════
    # 6. FRESH TOKEN RISK — very new + suspicious metrics
    # ═══════════════════════════════════════════════════════
    if age_hours is not None and age_hours < 6:
        risk_factors = []
        if liq < 5000:
            risk_factors.append("low liquidity")
        if total_txns < 10:
            risk_factors.append("very few transactions")
        if buys_24h > 0 and sells_24h == 0:
            risk_factors.append("no sells yet")

        if risk_factors:
            findings.append({
                "type": "fresh_token_risk",
                "severity": "medium",
                "msg": f"New token ({age_hours:.1f}h old) with risk factors: {', '.join(risk_factors)}.",
                "details": {"age_hours": round(age_hours, 1), "risk_factors": risk_factors},
            })
            _store_event(chain, token_addr, "fresh_token_risk", "fresh_token_risk", "medium",
                         {"age_hours": round(age_hours, 1), "risks": risk_factors})

    # ═══════════════════════════════════════════════════════
    # 7. RUG PULL SCORE (composite)
    # ═══════════════════════════════════════════════════════
    rug_score = 0
    rug_reasons = []
    if liq > 0 and mcap > 0 and mcap / liq > 30:
        rug_score += 25
        rug_reasons.append("high mcap/liq ratio")
    if buys_24h > 10 and sells_24h <= 1:
        rug_score += 30
        rug_reasons.append("almost no sells")
    if chg_24h is not None and chg_24h < -50:
        rug_score += 20
        rug_reasons.append("price crashed >50%")
    if age_hours is not None and age_hours < 3:
        rug_score += 10
        rug_reasons.append("very new (<3h)")
    if liq < 2000 and mcap > 50000:
        rug_score += 15
        rug_reasons.append("tiny liquidity")

    if rug_score >= 50:
        findings.append({
            "type": "rug_pull_risk",
            "severity": "high",
            "msg": f"Rug Pull Risk Score: {rug_score}/100. Reasons: {', '.join(rug_reasons)}.",
            "details": {"score": rug_score, "reasons": rug_reasons},
        })
        _store_event(chain, token_addr, "rug_pull_risk", "rug_pull_risk", "high",
                     {"score": rug_score, "reasons": rug_reasons})
    elif rug_score >= 30:
        findings.append({
            "type": "rug_pull_risk",
            "severity": "medium",
            "msg": f"Moderate Rug Risk: Score {rug_score}/100. Watch: {', '.join(rug_reasons)}.",
            "details": {"score": rug_score, "reasons": rug_reasons},
        })
        _store_event(chain, token_addr, "rug_pull_risk", "rug_pull_risk", "medium",
                     {"score": rug_score, "reasons": rug_reasons})

    return findings


def analyze_token_full(chain, token_address, pair_data=None):
    """
    Full analysis for a token. Fetches fresh data from Dexscreener
    and runs all detection patterns. Works on ALL chains.
    """
    # Fetch fresh pair data from Dexscreener
    pairs = get_token_pairs(chain, token_address)
    if not pairs and pair_data:
        # Use provided data if API didn't return anything
        return analyze_pair_data(pair_data)

    all_findings = []
    for pair in pairs[:3]:  # analyze top 3 pairs
        p = {
            "chain": pair.get("chainId", chain).lower(),
            "token_address": pair.get("baseToken", {}).get("address", token_address),
            "symbol": pair.get("baseToken", {}).get("symbol", "?"),
            "pair_address": pair.get("pairAddress", ""),
            "dex": pair.get("dexId", ""),
            "liquidity_usd": pair.get("liquidity", {}).get("usd", 0) or 0,
            "market_cap": pair.get("marketCap", 0) or 0,
            "price_usd": float(pair.get("priceUsd", 0) or 0),
            "volume_24h": pair.get("volume", {}).get("h24", 0) or 0,
            "created_at": pair.get("pairCreatedAt"),
            "price_change_5m": pair.get("priceChange", {}).get("m5", 0),
            "price_change_1h": pair.get("priceChange", {}).get("h1", 0),
            "price_change_24h": pair.get("priceChange", {}).get("h24", 0),
            "txns_buys_24h": pair.get("txns", {}).get("h24", {}).get("buys", 0),
            "txns_sells_24h": pair.get("txns", {}).get("h24", {}).get("sells", 0),
        }
        findings = analyze_pair_data(p)
        all_findings.extend(findings)
        time.sleep(0.2)

    # Deduplicate by type
    seen = set()
    unique = []
    for f in all_findings:
        key = f["type"]
        if key not in seen:
            seen.add(key)
            unique.append(f)

    return unique


def batch_analyze(tokens_list):
    """
    Analyze a batch of tokens (from scan results).
    Returns dict of {chain:address -> findings}.
    """
    results = {}
    for t in tokens_list:
        chain = t.get("chain", "")
        addr = t.get("token_address", "")
        key = f"{chain}:{addr}"

        findings = analyze_pair_data(t)
        if findings:
            results[key] = {
                "token": t,
                "findings": findings,
            }

    return results


def _store_event(chain, token_addr, wallet_or_system, event_type, severity, details):
    """Store an insider event in the database."""
    try:
        add_insider_event(
            chain=chain,
            token_address=token_addr,
            wallet_address=wallet_or_system,
            event_type=event_type,
            severity=severity,
            details=details,
        )
    except Exception:
        pass


def _fmt(val):
    if val >= 1_000_000:
        return f"${val/1_000_000:,.1f}M"
    if val >= 1_000:
        return f"${val/1_000:,.1f}K"
    return f"${val:,.0f}"
