"""
Main scanner — continuously scans for new meme tokens and analyzes them.
Run: python scanner.py
"""

import time
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from core.config import SCAN_INTERVAL, ANALYSIS_INTERVAL, INSIDER_CONFIG
from core.database import init_db, upsert_token, get_tracked_tokens
from chains.dexscreener import scan_new_memes, search_meme_tokens
from analyzers.insider_detector import analyze_token


BANNER = """
╔══════════════════════════════════════════════════════════════╗
║           MEME INSIDER TRACKER - All Chain Scanner           ║
║                                                              ║
║  Scanning: ETH | BSC | Base | Arbitrum | Polygon | Solana    ║
║  Detection: Snipers | Dev Wallets | Clusters | Bundles       ║
╚══════════════════════════════════════════════════════════════╝
"""


def scan_and_store():
    """Scan Dexscreener for new meme tokens and store them."""
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Scanning for new meme tokens...")

    tokens = scan_new_memes()
    new_count = 0

    for token in tokens:
        try:
            upsert_token(
                chain=token["chain"],
                address=token["token_address"],
                symbol=token.get("symbol", ""),
                name=token.get("name", ""),
                pair_address=token.get("pair_address", ""),
                dex=token.get("dex", ""),
                liquidity_usd=token.get("liquidity_usd", 0),
                market_cap=token.get("market_cap", 0),
                price_usd=token.get("price_usd", 0),
                volume_24h=token.get("volume_24h", 0),
                created_at=str(token.get("created_at", "")),
            )
            new_count += 1
        except Exception as e:
            print(f"  [!] Error storing {token.get('symbol', '?')}: {e}")

    print(f"  Found {len(tokens)} tokens, stored/updated {new_count}")
    return tokens


def analyze_new_tokens(tokens, max_analyze=10):
    """Analyze the most promising tokens for insider activity."""
    # Sort by liquidity (higher liquidity = more interesting)
    tokens.sort(key=lambda t: t.get("liquidity_usd", 0), reverse=True)

    analyzed = 0
    for token in tokens[:max_analyze]:
        chain = token["chain"]
        address = token["token_address"]
        symbol = token.get("symbol", "???")

        print(f"\n  Analyzing [{chain.upper()}] {symbol} ({address[:16]}...)")

        try:
            findings = analyze_token(chain, address, pair_data=token)

            if findings:
                for f in findings:
                    severity = f.get("severity", "info")
                    msg = f.get("msg", str(f))
                    icon = {"high": "!!!", "medium": "!!", "low": "."}.get(severity, " ")
                    print(f"    [{icon}] [{severity.upper()}] {msg}")
            else:
                print(f"    [OK] No suspicious activity")

            analyzed += 1
        except Exception as e:
            print(f"    [ERR] Analysis failed: {e}")

        time.sleep(1)  # rate limit between analyses

    return analyzed


def run_scanner():
    """Main scanner loop."""
    print(BANNER)
    print(f"Starting scanner at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Scan interval: {SCAN_INTERVAL}s | Analysis interval: {ANALYSIS_INTERVAL}s")
    print(f"Min liquidity: ${INSIDER_CONFIG['min_liquidity_usd']:,}")
    print(f"Max token age: {INSIDER_CONFIG['max_token_age_hours']}h")
    print("-" * 60)

    init_db()

    cycle = 0
    while True:
        try:
            cycle += 1
            print(f"\n{'='*60}")
            print(f"SCAN CYCLE #{cycle}")
            print(f"{'='*60}")

            # Step 1: Scan for new tokens
            tokens = scan_and_store()

            # Step 2: Analyze tokens
            if tokens:
                analyzed = analyze_new_tokens(tokens)
                print(f"\n  Analyzed {analyzed} tokens this cycle")
            else:
                print("  No new tokens found this cycle")

            # Summary
            all_tracked = get_tracked_tokens(limit=1000)
            print(f"\n  Total tokens in DB: {len(all_tracked)}")
            print(f"  Next scan in {SCAN_INTERVAL}s...")

            time.sleep(SCAN_INTERVAL)

        except KeyboardInterrupt:
            print("\n\nScanner stopped by user.")
            break
        except Exception as e:
            print(f"\n[ERROR] Scanner error: {e}")
            print(f"  Retrying in {SCAN_INTERVAL}s...")
            time.sleep(SCAN_INTERVAL)


if __name__ == "__main__":
    run_scanner()
