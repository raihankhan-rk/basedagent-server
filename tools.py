from cdp import Wallet
from cdp_langchain.tools import CdpTool
from pydantic import BaseModel, Field
from typing import Optional

REQUEST_FUNDS_ON_MAINNET_PROMPT = """
This tool generates a payment request link when the agent needs has insufficient funds on mainnet.
The link will direct to a payment portal where users can send funds to the agent's wallet.
"""

class RequestFundsOnMainnetInput(BaseModel):
    """Input argument schema for requesting funds."""
    
    amount: float = Field(
        ...,
        description="The amount of funds needed. Can be a decimal number."
    )
    token: str = Field(
        ...,
        description="The token symbol (e.g., 'ETH', 'USDC')"
    )

def request_funds_on_mainnet(wallet: Wallet, amount: float, token: str) -> str:
    """Request funds when the agent is on mainnet with insufficient funds.

    Args:
        wallet (Wallet): The wallet requesting funds.
        amount (float): The amount of funds needed. Example: 0.01
        token (str): The token symbol for the requested funds. Example: ETH

    Returns:
        str: The payment request link.
    """
    # Use the provided sender address or get it from the wallet
    receiver = wallet.default_address.address_id
    
    # Generate the payment request link
    payment_link = f"https://frameskit.vercel.app/payment?amount={amount}&token={token}&receiver={receiver}"
    
    return f"Hey there! Can you send me {amount} {token} to this address: {payment_link}?"