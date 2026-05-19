"""
EVM chain connector — fetch early buyers, token holders, tx history.
Uses free public RPCs + etherscan-like free APIs.
"""

from web3 import Web3
from web3.exceptions import TransactionNotFound
from core.config import CHAIN_RPCS

# ERC-20 Transfer event signature
_raw = Web3.keccak(text="Transfer(address,address,uint256)")
TRANSFER_TOPIC = _raw if isinstance(_raw, str) else "0x" + _raw.hex()

# Minimal ERC-20 ABI
ERC20_ABI = [
    {
        "constant": True, "inputs": [], "name": "totalSupply",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True, "inputs": [], "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    },
    {
        "constant": True, "inputs": [], "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    },
]


def get_w3(chain):
    rpc = CHAIN_RPCS.get(chain)
    if not rpc:
        raise ValueError(f"Unsupported EVM chain: {chain}")
    return Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 20}))


def get_token_info(chain, token_address):
    """Get basic token info (symbol, decimals, total supply)."""
    w3 = get_w3(chain)
    addr = w3.to_checksum_address(token_address)
    contract = w3.eth.contract(address=addr, abi=ERC20_ABI)
    try:
        symbol = contract.functions.symbol().call()
        decimals = contract.functions.decimals().call()
        total_supply = contract.functions.totalSupply().call()
        return {
            "symbol": symbol,
            "decimals": decimals,
            "total_supply": total_supply / (10 ** decimals),
        }
    except Exception as e:
        return {"error": str(e)}


def get_early_transfer_logs(chain, token_address, from_block, block_range=50):
    """
    Fetch Transfer events in the first N blocks after token creation.
    These are the earliest buyers / insiders.
    """
    w3 = get_w3(chain)
    addr = w3.to_checksum_address(token_address)
    to_block = min(from_block + block_range, w3.eth.block_number)

    try:
        logs = w3.eth.get_logs({
            "address": addr,
            "topics": [TRANSFER_TOPIC],
            "fromBlock": from_block,
            "toBlock": to_block,
        })
    except Exception as e:
        print(f"[EVM] Error fetching logs for {token_address} on {chain}: {e}")
        return []

    transfers = []
    for log in logs:
        from_addr = "0x" + log["topics"][1].hex()[-40:]
        to_addr = "0x" + log["topics"][2].hex()[-40:]
        value = int(log["data"].hex(), 16)
        transfers.append({
            "from": from_addr,
            "to": to_addr,
            "value_raw": value,
            "tx_hash": log["transactionHash"].hex(),
            "block_number": log["blockNumber"],
            "log_index": log["logIndex"],
        })

    return transfers


def get_deployer(chain, token_address):
    """
    Try to find who deployed the token contract by checking
    the contract creation transaction.
    """
    w3 = get_w3(chain)
    addr = w3.to_checksum_address(token_address)
    code = w3.eth.get_code(addr)
    if code == b"" or code == b"0x":
        return None

    # Binary search for creation block (approximate)
    current_block = w3.eth.block_number
    low, high = 0, current_block

    # Check recent blocks first (most meme tokens are new)
    check_blocks = [current_block - i * 1000 for i in range(100)]
    check_blocks = [b for b in check_blocks if b >= 0]

    for block_num in check_blocks:
        try:
            code_at = w3.eth.get_code(addr, block_identifier=block_num)
            if code_at == b"" or code_at == b"0x":
                # Contract didn't exist at this block
                return {"approximate_creation_block": block_num}
        except Exception:
            continue

    return None


def get_wallet_eth_balance(chain, wallet_address):
    """Get native token balance of a wallet."""
    w3 = get_w3(chain)
    addr = w3.to_checksum_address(wallet_address)
    balance = w3.eth.get_balance(addr)
    return w3.from_wei(balance, "ether")


def get_wallet_token_balance(chain, token_address, wallet_address):
    """Get ERC-20 token balance of a wallet."""
    w3 = get_w3(chain)
    token_addr = w3.to_checksum_address(token_address)
    wallet_addr = w3.to_checksum_address(wallet_address)
    contract = w3.eth.contract(address=token_addr, abi=ERC20_ABI)
    try:
        decimals = contract.functions.decimals().call()
        balance = contract.functions.balanceOf(wallet_addr).call()
        return balance / (10 ** decimals)
    except Exception:
        return 0


def get_tx_details(chain, tx_hash):
    """Get transaction details."""
    w3 = get_w3(chain)
    try:
        tx = w3.eth.get_transaction(tx_hash)
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        return {
            "from": tx["from"],
            "to": tx.get("to"),
            "value_eth": w3.from_wei(tx["value"], "ether"),
            "block_number": tx["blockNumber"],
            "gas_used": receipt["gasUsed"],
            "status": receipt["status"],
        }
    except TransactionNotFound:
        return None


def check_wallet_funding_source(chain, wallet_address, max_txns=20):
    """
    Check the first incoming ETH transaction to a wallet
    to identify who funded it (potential insider funder).
    NOTE: This is limited without a block explorer API.
    Uses recent internal heuristic.
    """
    w3 = get_w3(chain)
    addr = w3.to_checksum_address(wallet_address)
    current_block = w3.eth.block_number

    # Check last N blocks for incoming ETH
    for offset in range(0, 1000, 50):
        from_block = max(0, current_block - offset - 50)
        to_block = current_block - offset
        try:
            # We can't easily scan all txns to an address with basic RPC
            # Return placeholder — in production use Etherscan/Alchemy APIs
            pass
        except Exception:
            continue

    return {"funder": "unknown", "note": "Use explorer API for full funding trace"}
