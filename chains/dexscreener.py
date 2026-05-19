"""
Dexscreener API client — fetches new meme pairs across all chains.
No API key required.
"""

import requests
import time
from datetime import datetime, timedelta
from core.config import (
    DEXSCREENER_NEW_PAIRS, DEXSCREENER_SEARCH,
    DEXSCREENER_TOKENS, DEXSCREENER_PAIRS,
    SUPPORTED_CHAINS, INSIDER_CONFIG
)


def _get(url, params=None, retries=3):
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            if attempt == retries - 1:
                print(f"[Dexscreener] Request failed: {e}")
                return None
            time.sleep(1)
    return None


def fetch_latest_profiles():
    """Fetch latest token profiles (newly listed)."""
    data = _get(DEXSCREENER_NEW_PAIRS)
    if not data:
        return []
    tokens = []
    for item in data:
        chain = item.get("chainId", "").lower()
        if chain in SUPPORTED_CHAINS:
            tokens.append({
                "chain": chain,
                "address": item.get("tokenAddress", ""),
                "description": item.get("description", ""),
                "url": item.get("url", ""),
            })
    return tokens


def search_meme_tokens(query="meme", min_liquidity=None):
    """Search for meme tokens on Dexscreener."""
    data = _get(DEXSCREENER_SEARCH, params={"q": query})
    if not data or "pairs" not in data:
        return []

    min_liq = min_liquidity or INSIDER_CONFIG["min_liquidity_usd"]
    results = []

    for pair in data["pairs"]:
        chain = pair.get("chainId", "").lower()
        if chain not in SUPPORTED_CHAINS:
            continue

        liquidity = pair.get("liquidity", {}).get("usd", 0) or 0
        if liquidity < min_liq:
            continue

        created = pair.get("pairCreatedAt")
        if created:
            created_dt = datetime.fromtimestamp(created / 1000)
            max_age = timedelta(hours=INSIDER_CONFIG["max_token_age_hours"])
            if datetime.now() - created_dt > max_age:
                continue

        base_token = pair.get("baseToken", {})
        results.append({
            "chain": chain,
            "token_address": base_token.get("address", ""),
            "symbol": base_token.get("symbol", ""),
            "name": base_token.get("name", ""),
            "pair_address": pair.get("pairAddress", ""),
            "dex": pair.get("dexId", ""),
            "liquidity_usd": liquidity,
            "market_cap": pair.get("marketCap", 0) or 0,
            "price_usd": float(pair.get("priceUsd", 0) or 0),
            "volume_24h": pair.get("volume", {}).get("h24", 0) or 0,
            "created_at": pair.get("pairCreatedAt"),
            "price_change_5m": pair.get("priceChange", {}).get("m5", 0),
            "price_change_1h": pair.get("priceChange", {}).get("h1", 0),
            "price_change_24h": pair.get("priceChange", {}).get("h24", 0),
            "txns_buys_24h": pair.get("txns", {}).get("h24", {}).get("buys", 0),
            "txns_sells_24h": pair.get("txns", {}).get("h24", {}).get("sells", 0),
        })

    return results


def get_token_pairs(chain, token_address):
    """Get all trading pairs for a specific token."""
    url = f"{DEXSCREENER_TOKENS}/{token_address}"
    data = _get(url)
    if not data or "pairs" not in data:
        return []
    return [p for p in data["pairs"] if p.get("chainId", "").lower() == chain]


def get_pair_info(chain, pair_address):
    """Get detailed info for a specific pair."""
    url = f"{DEXSCREENER_PAIRS}/{chain}/{pair_address}"
    data = _get(url)
    if not data or "pairs" not in data:
        return None
    return data["pairs"][0] if data["pairs"] else None


def scan_new_memes(queries=None):
    """
    Main scanning function — searches multiple meme-related queries
    to find new launches across all chains.
    """
    if queries is None:
        queries = [
            "meme", "pepe", "doge", "shib", "inu", "moon",
            "baby", "elon", "trump", "cat", "wojak", "chad",
            "bonk", "floki", "ai", "grok",
        ]

    all_tokens = {}
    for q in queries:
        results = search_meme_tokens(query=q)
        for token in results:
            key = f"{token['chain']}:{token['token_address'].lower()}"
            if key not in all_tokens:
                all_tokens[key] = token
        time.sleep(0.3)  # rate limit

    return list(all_tokens.values())
