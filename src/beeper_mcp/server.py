import argparse
import logging
import os

from decimal import ROUND_DOWN, Decimal
import time
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from beeper.chain import BeeperClient
from beeper.util import BSC_MAINNET_SETTINGS, BSC_TESTNET_SETTINGS, format_decimal
from web3 import Web3

load_dotenv()

parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, default=8000)
parser.add_argument("--transport", type=str, default="stdio", choices=["stdio", "sse"])
parser.add_argument("--log-level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
args = parser.parse_args()

mcp = FastMCP(
    "Beeper MCP Server", port=args.port, debug=True, log_level=args.log_level,
)

logger = logging.getLogger(__name__)

chain = os.getenv("BEEPER_CHAIN")
logger.info(f"Beeper chain: {chain}")

if chain == "bsc":
    default_token_address = os.getenv('BEEPER_TARGET_TOKEN', "0x238950013FA29A3575EB7a3D99C00304047a77b5")
    chain_settings = BSC_MAINNET_SETTINGS
elif chain == "bsc-testnet":
    default_token_address = os.getenv('BEEPER_TARGET_TOKEN', "0x2e6b3f12408d5441e56c3C20848A57fd53a78931")
    chain_settings = BSC_TESTNET_SETTINGS
else:
    raise ValueError(f"Invalid chain: {chain}, must be one of: bsc, bsc-testnet")

logger.info(f"Beeper token address: {default_token_address}")

wallet_account = os.getenv("BEEPER_ACCOUNT")
if not wallet_account:  
    raise ValueError("BEEPER_ACCOUNT is not set")

logger.info(f"Beeper wallet account: {wallet_account}")

wallet_private_key = os.getenv("BEEPER_SECRET_KEY")
if not wallet_private_key:
    raise ValueError("BEEPER_SECRET_KEY is not set")

bc = BeeperClient(chain_settings, wallet_account, wallet_private_key)

@mcp.tool()
def get_default_wallet_address():
    """Get the default wallet address"""
    global wallet_account
    return wallet_account

@mcp.tool()
def get_default_token_address():
    """Get the default token address"""
    global default_token_address
    return default_token_address

@mcp.tool()
def switch_default_token_address(new_token_address: str) -> str:
    """Switch to default token address to new token address"""
    global default_token_address
    if not Web3.is_address(new_token_address):
        return f"Invalid token address: {new_token_address}"
    default_token_address = new_token_address
    return f"default token address is changed to: {default_token_address}" 

@mcp.tool()
def get_balance(address: str) -> str:
    """Get the balance of an address"""
    global bc
    balance = bc.get_balance(address, "")
    return format_decimal(balance)

@mcp.tool()
def get_token_balance(address: str, token_address: str) -> float:
    """Get the token balance of an address"""
    global bc
    balance = bc.get_balance(address, token_address)
    return format_decimal(balance)

@mcp.tool()
def transfer(recipient_address: str, amount: Decimal = 0.01) -> int:
    """Transfer BNB to an address with amount"""
    global bc
    try:
        amount = int(amount * 10**18)   
        tx = bc.transfer_asset(recipient_address, "", amount)
        res = {
            "tx_hash": tx,
            "status": "success",
            "bnb_amount_transferred": format_decimal(amount),
            "recipient": recipient_address
        }
        return res
    except Exception as e:
        res = {
            "status": "failed",
            "recipient_address": recipient_address,
            "error": str(e)
        }
        return res

@mcp.tool()
def transfer_token(recipient_address: str, token_address: str, amount: Decimal = 0.01) -> int:
    """Transfer token to an address with amount"""
    global bc
    try:
        amount = int(amount * 10**18)
        token_balance_before = bc.get_balance(wallet_account, token_address)
        tx = bc.transfer_asset(recipient_address, token_address, amount)
        token_balance_after = bc.get_balance(wallet_account, token_address)
        while token_balance_after == token_balance_before:
            time.sleep(1)
            token_balance_after = bc.get_balance(wallet_account, token_address)
        token_delta = token_balance_after - token_balance_before

        res = {
            "tx_hash": tx,
            "status": "success",
            "recipient": recipient_address,
            "token_balance": format_decimal(token_balance_after),
            "token_amount_transferred": format_decimal(token_delta)
        }
        return res
    except Exception as e:
        res = {
            "status": "failed",
            "token_address": token_address,
            "error": str(e)
        }
        return res

@mcp.tool()
def swap_token(token_in: str, token_out: str, amount: Decimal = 0.01) -> int:
    """Swap token_in to token_out with amount of token_in"""
    global bc
    try:
        amount = int(amount * 10**18)
        tx = bc.make_trade(token_in, token_out, amount)
        res = {
            "tx_hash": tx,
            "status": "success",
            "amount": format_decimal(amount),
            "token_in": token_in,
            "token_out": token_out
        }
        return res
    except Exception as e:
        res = {
            "status": "failed",
            "token_in": token_in,
            "token_out": token_out,
            "error": str(e)
        }
        return res

@mcp.tool()
def get_token_price(token_address: str) -> float:
    """Get the estimated price of a token in BNB"""
    global bc
    return bc.get_raw_price(token_address, "")

@mcp.tool()
def buy_token(token_address: str, amount: Decimal = 0.01) -> int:
    """Buy token with amount of BNB"""
    global bc, wallet_account
    try:
        amount = int(amount * 10**18)
        token_balance_before = bc.get_balance(wallet_account, token_address)
        tx = bc.make_trade("", token_address, amount)
        token_balance_after = bc.get_balance(wallet_account, token_address)
        while token_balance_after == token_balance_before:
            time.sleep(1)
            token_balance_after = bc.get_balance(wallet_account, token_address)
        token_delta = token_balance_after - token_balance_before

        res = {
            "tx_hash": tx,
            "status": "success",
            "bnb_amount_consumed": format_decimal(amount),
            "token_address": token_address,
            "token_balance": format_decimal(token_balance_after),
            "token_amount_received": format_decimal(token_delta)
        }
        return res
    except Exception as e:
        res = {
            "status": "failed",
            "token_address": token_address,
            "error": str(e)
        }
        return res
    
@mcp.tool()
def sell_token(token_address: str, amount: Decimal = 0.01) -> int:
    """Sell amount of token"""
    global bc
    try:
        amount = int(amount * 10**18)
        token_balance_before = bc.get_balance(wallet_account, token_address)
        tx = bc.make_trade(token_address, "", amount)
        token_balance_after = bc.get_balance(wallet_account, token_address)
        while token_balance_after == token_balance_before:
            time.sleep(1)
            token_balance_after = bc.get_balance(wallet_account, token_address)
    
        res = {
            "tx_hash": tx,
            "status": "success",
            "token_amount_sold": format_decimal(amount),
            "token_address": token_address,
            "token_balance": format_decimal(token_balance_after),
        }
        return res
    except Exception as e:
        res = {
            "status": "failed",
            "token_address": token_address,
            "error": str(e)
        }
        return res

@mcp.tool()
def claim_rewards(token_address: str):
    """Claim rewards"""
    global bc
    try:
        tx = bc.claim_reward(token_address)
        res = {
            "tx_hash": tx,
            "status": "success",
            "token_address": token_address
        }
        return res
    except Exception as e:
        res = {
            "status": "failed",
            "token_address": token_address,
            "error": str(e)
        }
        return res
    
def main():
    logging.info(f"Starting Beeper MCP Server")

    mcp.run(transport=args.transport)

if __name__ == "__main__":
    main()