import json
from typing import Optional, List
import redis
from redis.exceptions import RedisError
from langchain_core.messages import HumanMessage, AIMessage

class RedisManager:
    def __init__(self, url: str):
        self.redis_client = redis.from_url(url, decode_responses=True)
    
    def get_wallet_data(self, user_address: str) -> Optional[dict]:
        """Get wallet data for a specific user."""
        try:
            wallet_data = self.redis_client.get(f"wallet:{user_address}")
            return json.loads(wallet_data) if wallet_data else None
        except RedisError as e:
            print(f"Redis error while getting wallet data: {e}")
            return None

    def save_wallet_data(self, user_address: str, wallet_data: dict) -> bool:
        """Save wallet data for a specific user. Only called once per user."""
        try:
            # Only save if wallet doesn't exist for this user
            if not self.redis_client.exists(f"wallet:{user_address}"):
                self.redis_client.set(
                    f"wallet:{user_address}",
                    json.dumps(wallet_data)
                )
            return True
        except RedisError as e:
            print(f"Redis error while saving wallet data: {e}")
            return False

    def get_chat_history(self, user_address: str) -> List[HumanMessage]:
        """Get chat history for a user."""
        try:
            history = self.redis_client.get(f"chat:{user_address}")
            if history:
                messages = json.loads(history)
                return [HumanMessage(content=msg) for msg in messages]
            return []
        except RedisError as e:
            print(f"Redis error while getting chat history: {e}")
            return []

    def save_chat_history(self, user_address: str, messages: List[HumanMessage]) -> bool:
        """Save chat history for a user."""
        try:
            # Convert messages to simple strings
            history = [msg.content for msg in messages]
            self.redis_client.set(
                f"chat:{user_address}",
                json.dumps(history),
                ex=3600 * 24 * 7  # 7 days expiry
            )
            return True
        except RedisError as e:
            print(f"Redis error while saving chat history: {e}")
            return False 