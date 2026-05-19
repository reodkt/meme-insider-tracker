"""
Solana chain connector — fetch token transactions, early buyers.
Uses free Solana RPC.
"""

import requests
import time
from core.config import SOLANA_RPC


def _rpc_call(method, params=None):
    """Make a JSON-RPC call to Solana."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params or [],
    }
    try:
        resp = requests.post(SOLANA_RPC, json=payload, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            print(f"[Solana RPC] Error: {data['error']}")
            return None
        return data.get("result")
    except Exception as e:
        print(f"[Solana RPC] Request failed: {e}")
        return None


def get_token_supply(mint_address):
    """Get token supply info."""
    result = _rpc_call("getTokenSupply", [mint_address])
    if result and "value" in result:
        val = result["value"]
        return {
            "amount": val.get("amount", "0"),
            "decimals": val.get("decimals", 0),
            "ui_amount": val.get("uiAmount", 0),
        }
    return None


def get_token_largest_accounts(mint_address):
    """Get the largest token holders — useful for finding whales/insiders."""
    result = _rpc_call("getTokenLargestAccounts", [mint_address])
    if result and "value" in result:
        holders = []
        for acc in result["value"]:
            holders.append({
                "address": acc["address"],
                "amount": acc.get("uiAmount", 0),
                "amount_raw": acc.get("amount", "0"),
            })
        return holders
    return []


def get_signatures_for_address(address, limit=50, before=None):
    """Get recent transaction signatures for an address."""
    opts = {"limit": limit}
    if before:
        opts["before"] = before
    result = _rpc_call("getSignaturesForAddress", [address, opts])
    if result:
        return [{
            "signature": sig["signature"],
            "slot": sig.get("slot"),
            "block_time": sig.get("blockTime"),
            "err": sig.get("err"),
        } for sig in result]
    return []


def get_transaction(signature):
    """Get full transaction details."""
    result = _rpc_call("getTransaction", [
        signature,
        {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}
    ])
    return result


def get_account_info(address):
    """Get account info (owner, data, lamports)."""
    result = _rpc_call("getAccountInfo", [
        address,
        {"encoding": "jsonParsed"}
    ])
    if result and "value" in result:
        return result["value"]
    return None


def find_early_buyers(mint_address, max_signatures=100):
    """
    Find the earliest buyers of a token by scanning transaction history.
    Returns list of wallets that bought earliest.
    """
    sigs = get_signatures_for_address(mint_address, limit=max_signatures)
    if not sigs:
        return []

    # Sort by slot (earliest first)
    sigs.sort(key=lambda x: x.get("slot", 0))

    early_buyers = []
    seen_wallets = set()

    for sig_info in sigs[:30]:  # analyze first 30 txns
        tx = get_transaction(sig_info["signature"])
        if not tx or not tx.get("meta"):
            continue

        # Look at post token balances for buyers
        post_balances = tx.get("meta", {}).get("postTokenBalances", [])
        pre_balances = tx.get("meta", {}).get("preTokenBalances", [])

        for post in post_balances:
            if post.get("mint") != mint_address:
                continue
            owner = post.get("owner", "")
            if owner and owner not in seen_wallets:
                post_amount = float(post.get("uiTokenAmount", {}).get("uiAmount", 0) or 0)
                # Check if this was a buy (balance increased)
                pre_amount = 0
                for pre in pre_balances:
                    if pre.get("owner") == owner and pre.get("mint") == mint_address:
                        pre_amount = float(pre.get("uiTokenAmount", {}).get("uiAmount", 0) or 0)
                        break

                if post_amount > pre_amount:
                    early_buyers.append({
                        "wallet": owner,
                        "amount": post_amount - pre_amount,
                        "slot": sig_info.get("slot"),
                        "block_time": sig_info.get("block_time"),
                        "signature": sig_info["signature"],
                    })
                    seen_wallets.add(owner)

        time.sleep(0.1)  # rate limit

    return early_buyers


def detect_bundled_buys(mint_address, max_sigs=50):
    """
    Detect bundled buys — multiple wallets buying in the same transaction
    or same slot. Common insider tactic on Solana.
    """
    sigs = get_signatures_for_address(mint_address, limit=max_sigs)
    if not sigs:
        return []

    sigs.sort(key=lambda x: x.get("slot", 0))

    # Group by slot
    slot_buyers = {}
    for sig_info in sigs[:30]:
        tx = get_transaction(sig_info["signature"])
        if not tx or not tx.get("meta"):
            continue

        slot = sig_info.get("slot", 0)
        post_balances = tx.get("meta", {}).get("postTokenBalances", [])

        buyers_in_tx = []
        for post in post_balances:
            if post.get("mint") != mint_address:
                continue
            owner = post.get("owner", "")
            amount = float(post.get("uiTokenAmount", {}).get("uiAmount", 0) or 0)
            if owner and amount > 0:
                buyers_in_tx.append({"wallet": owner, "amount": amount})

        if len(buyers_in_tx) > 1:
            # Multiple buyers in same transaction = likely bundled
            if slot not in slot_buyers:
                slot_buyers[slot] = []
            slot_buyers[slot].extend(buyers_in_tx)

        time.sleep(0.1)

    bundles = []
    for slot, buyers in slot_buyers.items():
        if len(buyers) >= 2:
            bundles.append({
                "slot": slot,
                "buyers": buyers,
                "bundle_size": len(buyers),
            })

    return bundles
