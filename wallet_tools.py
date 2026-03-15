# ============================================================
# wallet_tools.py — Ethereum Wallet Operations
# ============================================================
# This module contains every on-chain action the agent can do:
#   • Check the user's ETH balance (via MetaMask address)
#   • Check the agent's ETH balance
#   • Transfer ETH from user → agent (signed via MetaMask)
#   • Create a new wallet
#
# All functions receive and return AgentState so they plug
# directly into LangGraph as nodes.
# ============================================================

import os
from web3 import Web3
from dotenv import load_dotenv
from state import AgentState

# Load environment variables
load_dotenv()

# ---------------------------------------------------------
# Connect to the Ethereum Sepolia testnet via Infura
# ---------------------------------------------------------
INFURA_RPC = os.getenv("INFURA_RPC")
web3 = Web3(Web3.HTTPProvider(INFURA_RPC))

if web3.is_connected():
    print("[wallet_tools] Connected to Ethereum Sepolia via Infura")
else:
    print("[wallet_tools] WARNING — could not connect to Infura RPC")

# ---------------------------------------------------------
# Load the agent wallet from its private key
# (User wallet is now connected via MetaMask on the frontend)
# ---------------------------------------------------------
AGENT_PRIVATE_KEY = os.getenv("AGENT_PRIVATE_KEY")
agent_account = web3.eth.account.from_key(AGENT_PRIVATE_KEY)
AGENT_ADDRESS = agent_account.address

print(f"[wallet_tools] Agent wallet: {AGENT_ADDRESS}")


# ============================================================
# Tool 1 — Check User Wallet Balance
# ============================================================
def check_user_balance(state: AgentState) -> dict:
    """Reads the MetaMask-connected user wallet's ETH balance."""

    user_addr = state.get("user_address", "")
    if not user_addr:
        return {"result": "Please connect your wallet first (click Connect Wallet)."}

    user_addr = Web3.to_checksum_address(user_addr)
    balance_wei = web3.eth.get_balance(user_addr)
    balance_eth = web3.from_wei(balance_wei, "ether")

    return {"result": f"User wallet balance: {balance_eth} ETH\nAddress: {user_addr}"}


# ============================================================
# Tool 2 — Check Agent Wallet Balance
# ============================================================
def check_agent_balance(state: AgentState) -> dict:
    """Reads the agent wallet's ETH balance."""

    balance_wei = web3.eth.get_balance(AGENT_ADDRESS)
    balance_eth = web3.from_wei(balance_wei, "ether")

    return {"result": f"Agent wallet balance: {balance_eth} ETH\nAddress: {AGENT_ADDRESS}"}


# ============================================================
# Tool 3 — Transfer ETH from User → Agent (MetaMask signs)
# ============================================================
def transfer_to_agent(state: AgentState) -> dict:
    """Returns a SIGN_TX marker so the frontend triggers MetaMask signing."""

    user_addr = state.get("user_address", "")
    if not user_addr:
        return {"result": "Please connect your wallet first (click Connect Wallet)."}

    user_addr = Web3.to_checksum_address(user_addr)
    amount_str = state.get("amount", "")
    if not amount_str:
        return {"result": "Error: No transfer amount specified."}

    try:
        amount_eth = float(amount_str)
    except ValueError:
        return {"result": f"Error: Invalid amount '{amount_str}'."}

    if amount_eth <= 0:
        return {"result": "Error: Amount must be greater than zero."}

    amount_wei = str(web3.to_wei(amount_eth, "ether"))

    # Frontend will parse this marker and trigger MetaMask
    return {
        "result": f"SIGN_TX:{amount_eth}:{amount_wei}:{user_addr}:{AGENT_ADDRESS}"
    }


# ============================================================
# Tool 4 — Create a New Wallet
# ============================================================
def create_wallet(state: AgentState) -> dict:
    """Generate a brand-new Ethereum wallet."""

    new_account = web3.eth.account.create()

    return {
        "result": (
            f"New wallet created!\n"
            f"  Address:     {new_account.address}\n"
            f"  Private Key: {new_account.key.hex()}\n"
            f"\n⚠️  Save the private key securely — it cannot be recovered!"
        )
    }
