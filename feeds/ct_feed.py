"""
CT & Crypto Feed Aggregator — free, no API keys.
Sources: Reddit, CoinGecko trending, crypto news RSS, Dexscreener boosted.
"""

import requests
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone


def _get_json(url, timeout=10):
    try:
        resp = requests.get(url, timeout=timeout, headers={
            "User-Agent": "MemeInsiderTracker/2.0",
            "Accept": "application/json",
        })
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None


def _get_text(url, timeout=10):
    try:
        resp = requests.get(url, timeout=timeout, headers={
            "User-Agent": "MemeInsiderTracker/2.0",
        })
        if resp.status_code == 200:
            return resp.text
    except Exception:
        pass
    return None


# ═══════════════════════════════════════════════════════
# 1. REDDIT — r/CryptoCurrency, r/memecoin, r/solana
# ═══════════════════════════════════════════════════════
REDDIT_SUBS = [
    "CryptoCurrency", "memecoin", "solana",
    "ethtrader", "defi", "CryptoMoonShots",
]


def fetch_reddit_posts(limit=30):
    """Fetch hot/new posts from crypto subreddits."""
    posts = []
    for sub in REDDIT_SUBS:
        data = _get_json(f"https://www.reddit.com/r/{sub}/hot.json?limit=10&t=day")
        if not data or "data" not in data:
            continue
        for child in data["data"].get("children", []):
            p = child.get("data", {})
            if p.get("stickied"):
                continue
            score = p.get("score", 0)
            if score < 5:
                continue
            created = p.get("created_utc", 0)
            try:
                ts = datetime.fromtimestamp(created, tz=timezone.utc)
            except Exception:
                ts = datetime.now(timezone.utc)
            posts.append({
                "source": f"Reddit r/{sub}",
                "source_icon": "🟠",
                "title": p.get("title", ""),
                "url": f"https://reddit.com{p.get('permalink', '')}",
                "score": score,
                "comments": p.get("num_comments", 0),
                "author": p.get("author", ""),
                "time": ts,
                "time_str": ts.strftime("%H:%M"),
                "type": "reddit",
            })
        time.sleep(0.3)

    posts.sort(key=lambda x: x["time"], reverse=True)
    return posts[:limit]


# ═══════════════════════════════════════════════════════
# 2. COINGECKO TRENDING — reflects CT attention
# ═══════════════════════════════════════════════════════
def fetch_trending_coins():
    """Fetch trending coins from CoinGecko (free, no key)."""
    data = _get_json("https://api.coingecko.com/api/v3/search/trending")
    if not data:
        return []

    coins = []
    for item in data.get("coins", []):
        c = item.get("item", {})
        coins.append({
            "source": "CoinGecko Trending",
            "source_icon": "🦎",
            "title": f"#{c.get('score', 0)+1} Trending: {c.get('name', '')} ({c.get('symbol', '')})",
            "url": f"https://www.coingecko.com/en/coins/{c.get('id', '')}",
            "score": c.get("score", 0),
            "market_cap_rank": c.get("market_cap_rank"),
            "price_btc": c.get("price_btc", 0),
            "time": datetime.now(timezone.utc),
            "time_str": "now",
            "type": "trending",
            "thumb": c.get("thumb", ""),
        })

    # Also fetch trending categories
    for item in data.get("nfts", [])[:3]:
        coins.append({
            "source": "CoinGecko NFT Trending",
            "source_icon": "🖼️",
            "title": f"Trending NFT: {item.get('name', '')}",
            "url": f"https://www.coingecko.com",
            "score": 0,
            "time": datetime.now(timezone.utc),
            "time_str": "now",
            "type": "trending_nft",
        })

    return coins


# ═══════════════════════════════════════════════════════
# 3. CRYPTO NEWS RSS FEEDS
# ═══════════════════════════════════════════════════════
NEWS_RSS_FEEDS = [
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("CoinTelegraph", "https://cointelegraph.com/rss"),
    ("Decrypt", "https://decrypt.co/feed"),
    ("The Block", "https://www.theblock.co/rss.xml"),
    ("DL News", "https://www.dlnews.com/arc/outboundfeeds/rss/"),
]


def fetch_crypto_news(limit=20):
    """Fetch latest crypto news from RSS feeds."""
    articles = []
    for name, url in NEWS_RSS_FEEDS:
        xml = _get_text(url)
        if not xml:
            continue
        try:
            root = ET.fromstring(xml)
            # Handle both RSS and Atom formats
            items = root.findall(".//item") or root.findall(
                ".//{http://www.w3.org/2005/Atom}entry"
            )
            for item in items[:8]:
                title = (
                    _xml_text(item, "title")
                    or _xml_text(item, "{http://www.w3.org/2005/Atom}title")
                    or ""
                )
                link = (
                    _xml_text(item, "link")
                    or _xml_attr(item, "{http://www.w3.org/2005/Atom}link", "href")
                    or ""
                )
                pub = (
                    _xml_text(item, "pubDate")
                    or _xml_text(item, "{http://www.w3.org/2005/Atom}published")
                    or ""
                )
                desc = (
                    _xml_text(item, "description")
                    or _xml_text(item, "{http://www.w3.org/2005/Atom}summary")
                    or ""
                )
                # Clean HTML from description
                desc = _strip_html(desc)[:200]

                ts = _parse_rss_date(pub)

                # Filter: only crypto-related
                text = f"{title} {desc}".lower()
                crypto_keywords = [
                    "crypto", "bitcoin", "btc", "ethereum", "eth", "solana", "sol",
                    "meme", "token", "defi", "nft", "web3", "blockchain", "trading",
                    "whale", "pump", "dump", "rug", "airdrop", "dex", "swap",
                    "binance", "coinbase", "uniswap", "chain", "wallet", "staking",
                    "altcoin", "bull", "bear", "market", "price", "liquidity",
                ]
                if not any(kw in text for kw in crypto_keywords):
                    continue

                articles.append({
                    "source": name,
                    "source_icon": "📰",
                    "title": title,
                    "url": link,
                    "description": desc,
                    "time": ts,
                    "time_str": ts.strftime("%H:%M") if ts else "",
                    "type": "news",
                })
        except Exception:
            continue
        time.sleep(0.2)

    articles.sort(key=lambda x: x.get("time") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return articles[:limit]


# ═══════════════════════════════════════════════════════
# 4. DEXSCREENER BOOSTED — tokens getting promoted (CT indicator)
# ═══════════════════════════════════════════════════════
def fetch_dex_boosted_feed():
    """Fetch boosted tokens as feed items."""
    from core.config import DEXSCREENER_BOOSTS_LATEST, DEXSCREENER_BOOSTS_TOP, SUPPORTED_CHAINS

    items = []
    for label, url in [("Latest Boost", DEXSCREENER_BOOSTS_LATEST), ("Top Boost", DEXSCREENER_BOOSTS_TOP)]:
        data = _get_json(url)
        if not data:
            continue
        tokens = data if isinstance(data, list) else data.get("tokens", [])
        for t in tokens[:15]:
            chain = t.get("chainId", "").lower()
            if chain not in SUPPORTED_CHAINS:
                continue
            addr = t.get("tokenAddress", "")
            desc = t.get("description", "")[:100]
            items.append({
                "source": f"Dexscreener {label}",
                "source_icon": "🚀",
                "title": f"Boosted on {chain.upper()}: {desc or addr[:20]}",
                "url": t.get("url", f"https://dexscreener.com/{chain}/{addr}"),
                "chain": chain,
                "token_address": addr,
                "time": datetime.now(timezone.utc),
                "time_str": "now",
                "type": "boosted",
            })
        time.sleep(0.3)

    return items


# ═══════════════════════════════════════════════════════
# MAIN: Aggregate all feeds
# ═══════════════════════════════════════════════════════
def get_ct_feed(limit=50):
    """Get aggregated CT/crypto feed from all sources."""
    feed = []

    # Fetch all sources (with error handling)
    try:
        feed.extend(fetch_reddit_posts(limit=20))
    except Exception:
        pass

    try:
        feed.extend(fetch_trending_coins())
    except Exception:
        pass

    try:
        feed.extend(fetch_crypto_news(limit=20))
    except Exception:
        pass

    try:
        feed.extend(fetch_dex_boosted_feed())
    except Exception:
        pass

    # Sort by time (newest first)
    feed.sort(
        key=lambda x: x.get("time") or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return feed[:limit]


# ── Helpers ──
def _xml_text(elem, tag):
    child = elem.find(tag)
    return child.text.strip() if child is not None and child.text else None


def _xml_attr(elem, tag, attr):
    child = elem.find(tag)
    return child.get(attr) if child is not None else None


def _strip_html(text):
    if not text:
        return ""
    import re
    return re.sub(r"<[^>]+>", "", text).strip()


def _parse_rss_date(date_str):
    if not date_str:
        return datetime.now(timezone.utc)
    from email.utils import parsedate_to_datetime
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        pass
    # Try ISO format
    for fmt in ["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"]:
        try:
            return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
        except Exception:
            continue
    return datetime.now(timezone.utc)
