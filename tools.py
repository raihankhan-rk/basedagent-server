from cdp import Wallet
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from bs4 import BeautifulSoup
import requests

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
    payment_link = f"https://frameskit.vercel.app/payment?amount={amount}&token={token}&recipientAddress={receiver}"
    
    return f"Hey there! Can you send me {amount} {token} to this address: {payment_link}?"


TRENDING_MEME_TOKENS_PROMPT = """
This tool fetches current trending meme tokens from CoinMarketCap, providing their names, 
prices, and 24-hour price changes. Use this when you need information about popular 
meme cryptocurrencies or want to analyze trending meme tokens in the market.
"""

class GetTrendingMemeTokensInput(BaseModel):
    """Input argument schema for fetching meme tokens."""
    limit: Optional[int] = Field(
        default=10,
        description="Number of meme tokens to return (default: 10)"
    )

def get_trending_meme_tokens(limit: Optional[int] = 10) -> List[Dict[str, str]]:
    """Fetch trending meme tokens from CoinMarketCap.

    Args:
        limit (Optional[int]): Number of meme tokens to return. Defaults to 10.

    Returns:
        List[Dict[str, str]]: List of meme tokens with their details.
        Each dict contains 'name', 'price', and 'change_24h'.
    """
    url = "https://coinmarketcap.com/view/memes"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        coin_names = soup.find_all(class_='coin-item-name')
        prices = soup.find_all(class_='dzgUIj')
        changes = soup.find_all(class_='ivvJzO')
        
        meme_tokens = []
        for name, price, change in zip(coin_names, prices, changes):
            # Check if there's a down caret icon to determine if change is negative
            is_negative = bool(change.find(class_='icon-Caret-down'))
            change_value = change.text.strip()
            
            # Add negative sign if down caret was found
            if is_negative:
                change_value = f"-{change_value}"
            
            meme_tokens.append({
                "name": name.text.strip(),
                "price": price.text.strip(),
                "change_24h": change_value
            })
            
            if len(meme_tokens) >= limit:
                break
                
        return meme_tokens
            
    except requests.RequestException as e:
        raise Exception(f"Error fetching meme tokens: {e}")