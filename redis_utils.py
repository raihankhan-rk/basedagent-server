import json
from typing import Optional, List
import redis.asyncio as redis
from redis.exceptions import RedisError
from langchain_core.messages import HumanMessage

class RedisManager:
    def __init__(self, url: str):
        self.redis_client = redis.from_url(url, decode_responses=True)
    
    async def get_wallet_data(self, user_address: str) -> Optional[dict]:
        """Get wallet data for a specific user."""
        try:
            wallet_data = await self.redis_client.get(f"wallet:{user_address}")
            return json.loads(wallet_data) if wallet_data else None
        except RedisError as e:
            print(f"Redis error while getting wallet data: {e}")
            return None

    async def save_wallet_data(self, user_address: str, wallet_data: dict) -> bool:
        """Save wallet data for a specific user."""
        try:
            exists = await self.redis_client.exists(f"wallet:{user_address}")
            if not exists:
                await self.redis_client.set(
                    f"wallet:{user_address}",
                    json.dumps(wallet_data)
                )
            return True
        except RedisError as e:
            print(f"Redis error while saving wallet data: {e}")
            return False

    async def get_chat_history(self, user_address: str) -> List[HumanMessage]:
        """Get chat history for a user."""
        try:
            history = await self.redis_client.get(f"chat:{user_address}")
            if history:
                messages = json.loads(history)
                return [HumanMessage(content=msg) for msg in messages]
            return []
        except RedisError as e:
            print(f"Redis error while getting chat history: {e}")
            return []

    async def save_chat_history(self, user_address: str, messages: List[HumanMessage]) -> bool:
        """Save chat history for a user."""
        try:
            history = [msg.content for msg in messages]
            await self.redis_client.set(
                f"chat:{user_address}",
                json.dumps(history),
                ex=3600 * 24 * 7  # 7 days expiry
            )
            return True
        except RedisError as e:
            print(f"Redis error while saving chat history: {e}")
            return False

    async def close(self):
        """Close the Redis connection."""
        await self.redis_client.close()