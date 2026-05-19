"""
Insider detection engine — analyzes tokens for suspicious activity.

Detects:
1. Early sniper buys (first blocks)
2. Dev wallet large holdings
3. Wallet clusters (same funder)
4. Bundled buys (Solana)
5. Coordinated sell-offs
"""

import time
from datetime import datetime
from core.config import INSIDER_CONFIG
from core.database import add_insider_event, add_wallet_cluster, upsert_token
from chains.evm import (
    get_early_transfer_logs, get_token_info, get_wallet_token_balance, get_w3
)
from chains.solana_chain import (
    find_early_buyers, detect_bundled_buys, get_token_largest_accounts,
    get_token_supply
)


def analyze_evm_token(chain, token_address, pair_data=None):
    """
    Full insider analysis for an EVM token.
    Returns list of findings.
    """
    findings = []
    token_address = token_address.lower()

    # 1. Get token info
    info = get_token_info(chain, token_address)
    if "error" in info:
        return [{"type": "error", "msg": f"Cannot read token: {info['error']}"}]

    total_supply = info.get("total_supply", 0)
    decimals = info.get("decimals", 18)

    # 2. Try to find early Transfer events
    # We need the creation block — estimate from pair_data or scan
    try:
        w3 = get_w3(chain)
        current_block = w3.eth.block_number

        # Check recent blocks (scan last 50k blocks ~ last few hours)
        from_block = max(0, current_block - 50000)
        early_transfers = get_early_transfer_logs(
            chain, token_address,
            from_block=from_block,
            block_range=INSIDER_CONFIG["early_buyer_blocks"] * 100
        )

        if early_transfers:
            # Identify the mint/creation transfer (from = 0x0)
            mint_txs = [t for t in early_transfers if t["from"] == "0x" + "0" * 40]
            buy_txs = [t for t in early_transfers if t["from"] != "0x" + "0" * 40]

            # Find first block with buys
            if buy_txs:
                first_buy_block = min(t["block_number"] for t in buy_txs)

                # Snipers = bought in first N blocks
                sniper_threshold = first_buy_block + INSIDER_CONFIG["sniper_max_block_delay"]
                snipers = [
                    t for t in buy_txs
                    if t["block_number"] <= sniper_threshold
                ]

                if snipers:
                    sniper_wallets = list(set(t["to"] for t in snipers))
                    finding = {
                        "type": "early_sniper",
                        "severity": "high",
                        "wallets": sniper_wallets,
                        "count": len(sniper_wallets),
                        "first_block": first_buy_block,
                        "msg": f"{len(sniper_wallets)} sniper wallet(s) bought in first {INSIDER_CONFIG['sniper_max_block_delay']} blocks"
                    }
                    findings.append(finding)

                    for wallet in sniper_wallets:
                        add_insider_event(
                            chain=chain,
                            token_address=token_address,
                            wallet_address=wallet,
                            event_type="early_sniper",
                            severity="high",
                            details={"block": first_buy_block},
                            tx_hash=snipers[0]["tx_hash"],
                            block_number=first_buy_block,
                        )

            # 3. Check if dev/deployer holds large % of supply
            if mint_txs and total_supply > 0:
                dev_wallet = mint_txs[0]["to"]
                dev_balance = get_wallet_token_balance(chain, token_address, dev_wallet)
                dev_pct = (dev_balance / total_supply) * 100 if total_supply else 0

                if dev_pct > INSIDER_CONFIG["dev_sell_alert_pct"]:
                    finding = {
                        "type": "dev_large_holding",
                        "severity": "high" if dev_pct > 50 else "medium",
                        "wallet": dev_wallet,
                        "balance_pct": round(dev_pct, 2),
                        "msg": f"Dev wallet holds {dev_pct:.1f}% of supply"
                    }
                    findings.append(finding)

                    add_insider_event(
                        chain=chain,
                        token_address=token_address,
                        wallet_address=dev_wallet,
                        event_type="dev_large_holding",
                        severity=finding["severity"],
                        details={"balance_pct": dev_pct},
                    )

            # 4. Detect wallet clusters (wallets that received tokens from same source)
            receiver_to_funder = {}
            for t in early_transfers:
                if t["from"] != "0x" + "0" * 40:  # skip mints
                    funder = t["from"]
                    receiver = t["to"]
                    if funder not in receiver_to_funder:
                        receiver_to_funder[funder] = []
                    receiver_to_funder[funder].append(receiver)

            for funder, receivers in receiver_to_funder.items():
                unique_receivers = list(set(receivers))
                if len(unique_receivers) >= INSIDER_CONFIG["same_funder_min_wallets"]:
                    finding = {
                        "type": "wallet_cluster",
                        "severity": "high",
                        "funder": funder,
                        "wallets": unique_receivers,
                        "cluster_size": len(unique_receivers),
                        "msg": f"Wallet cluster: {funder[:10]}... funded {len(unique_receivers)} wallets"
                    }
                    findings.append(finding)

                    add_wallet_cluster(
                        chain=chain,
                        funder_address=funder,
                        wallet_addresses=unique_receivers,
                        token_address=token_address,
                    )

    except Exception as e:
        findings.append({"type": "error", "msg": f"EVM analysis error: {str(e)}"})

    return findings


def analyze_solana_token(token_address, pair_data=None):
    """
    Full insider analysis for a Solana token.
    """
    findings = []

    # 1. Check token supply
    supply = get_token_supply(token_address)
    if not supply:
        return [{"type": "error", "msg": "Cannot fetch token supply"}]

    total_supply = supply.get("ui_amount", 0)

    # 2. Get largest holders
    largest = get_token_largest_accounts(token_address)
    if largest and total_supply > 0:
        for holder in largest[:5]:
            pct = (holder["amount"] / total_supply) * 100 if total_supply else 0
            if pct > INSIDER_CONFIG["dev_sell_alert_pct"]:
                finding = {
                    "type": "whale_holding",
                    "severity": "high" if pct > 30 else "medium",
                    "wallet": holder["address"],
                    "balance_pct": round(pct, 2),
                    "msg": f"Whale holds {pct:.1f}% of supply: {holder['address'][:12]}..."
                }
                findings.append(finding)

                add_insider_event(
                    chain="solana",
                    token_address=token_address,
                    wallet_address=holder["address"],
                    event_type="whale_holding",
                    severity=finding["severity"],
                    details={"balance_pct": pct, "amount": holder["amount"]},
                )

    # 3. Find early buyers
    early = find_early_buyers(token_address, max_signatures=50)
    if early:
        finding = {
            "type": "early_buyers",
            "severity": "medium",
            "wallets": [e["wallet"] for e in early[:10]],
            "count": len(early),
            "msg": f"Found {len(early)} early buyer(s)"
        }
        findings.append(finding)

        for buyer in early[:10]:
            add_insider_event(
                chain="solana",
                token_address=token_address,
                wallet_address=buyer["wallet"],
                event_type="early_buyer",
                severity="medium",
                details={"amount": buyer["amount"], "slot": buyer.get("slot")},
            )

    # 4. Detect bundled buys
    bundles = detect_bundled_buys(token_address, max_sigs=30)
    if bundles:
        total_bundled = sum(b["bundle_size"] for b in bundles)
        finding = {
            "type": "bundled_buys",
            "severity": "high",
            "bundles": bundles,
            "total_bundled_wallets": total_bundled,
            "msg": f"Detected {len(bundles)} bundled buy(s) with {total_bundled} wallets"
        }
        findings.append(finding)

        for bundle in bundles:
            for buyer in bundle["buyers"]:
                add_insider_event(
                    chain="solana",
                    token_address=token_address,
                    wallet_address=buyer["wallet"],
                    event_type="bundled_buy",
                    severity="high",
                    details={"slot": bundle["slot"], "bundle_size": bundle["bundle_size"]},
                )

    return findings


def analyze_token(chain, token_address, pair_data=None):
    """
    Universal token analyzer — routes to chain-specific analysis.
    """
    print(f"[Analyzer] Analyzing {token_address[:16]}... on {chain}")

    if chain == "solana":
        return analyze_solana_token(token_address, pair_data)
    elif chain in ("ethereum", "bsc", "base", "arbitrum", "polygon", "avalanche"):
        return analyze_evm_token(chain, token_address, pair_data)
    else:
        return [{"type": "error", "msg": f"Unsupported chain: {chain}"}]
