from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import json
import logging
from dotenv import load_dotenv

from redis_utils import RedisManager
from main import initialize_agent
from langchain_core.messages import HumanMessage
from cdp_langchain.utils import CdpAgentkitWrapper

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = FastAPI()
# Redis for wallet data
wallet_redis_manager = RedisManager(
    url=os.getenv("WALLET_REDIS_URL")
)

# Redis for chat history
chat_redis_manager = RedisManager(
    url=os.getenv("CHAT_HISTORY_REDIS_URL")
)

class ChatRequest(BaseModel):
    prompt: str
    user: str  # User's wallet address

class ChatResponse(BaseModel):
    response: str

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        # Get wallet data for the user
        wallet_data = wallet_redis_manager.get_wallet_data(request.user)
        logger.info(f"Wallet data retrieved for user {request.user}: {wallet_data is not None}")
        
        # Initialize values for CdpAgentkitWrapper
        values = {}
        if wallet_data:
            values = {"cdp_wallet_data": json.dumps(wallet_data)}
        else:
            temp_wrapper = CdpAgentkitWrapper()
            initial_wallet = temp_wrapper.export_wallet()
            wallet_redis_manager.save_wallet_data(request.user, json.loads(initial_wallet))
            values = {"cdp_wallet_data": initial_wallet}
        
        # Get chat history
        chat_history = chat_redis_manager.get_chat_history(request.user)
        logger.info(f"Chat history retrieved for user {request.user}: {chat_history}")
        
        # Initialize agent
        agent_executor, _ = initialize_agent(values)
        
        # Format the input with messages and history if exists
        messages = [HumanMessage(content=request.prompt)]
        if chat_history:
            messages = chat_history + messages
            
        agent_input = {"messages": messages}
        agent_config = {
            "configurable": {
                "session_id": request.user,
                "thread_id": request.user
            }
        }
        
        # Run the agent
        response_chunks = []
        for chunk in agent_executor.stream(
            agent_input,
            agent_config
        ):
            if "agent" in chunk:
                response_content = chunk["agent"]["messages"][0].content
                response_chunks.append(response_content)
            elif "tools" in chunk:
                response_content = chunk["tools"]["messages"][0].content
                response_chunks.append(response_content)
        
        final_response = " ".join(response_chunks)
        
        # Save the conversation to Redis
        chat_redis_manager.save_chat_history(
            request.user,
            messages + [HumanMessage(content=final_response)]
        )
        
        return ChatResponse(response=final_response)
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 