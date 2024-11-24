from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security.api_key import APIKeyHeader, APIKey
from starlette.status import HTTP_403_FORBIDDEN
from pydantic import BaseModel
import os
import json
import logging
from dotenv import load_dotenv
from contextlib import asynccontextmanager

from redis_utils import RedisManager
from main import initialize_agent
from langchain_core.messages import HumanMessage
from cdp_langchain.utils import CdpAgentkitWrapper

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# API Key setup - hardcoded
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise ValueError("API_KEY not found in environment variables")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Create a state class to hold our connections
class AppState:
    def __init__(self):
        self.wallet_redis = RedisManager(url=os.getenv("WALLET_REDIS_URL"))
        self.chat_redis = RedisManager(url=os.getenv("CHAT_HISTORY_REDIS_URL"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize shared state
    app.state.connections = AppState()
    yield
    # Clean up connections
    await app.state.connections.wallet_redis.close()
    await app.state.connections.chat_redis.close()

app = FastAPI(lifespan=lifespan)

class ChatRequest(BaseModel):
    prompt: str
    user: str  # User's wallet address

class ChatResponse(BaseModel):
    response: str

async def get_api_key(
    api_key_header: str = Security(api_key_header),
) -> APIKey:
    if api_key_header == API_KEY:
        return api_key_header
    raise HTTPException(
        status_code=HTTP_403_FORBIDDEN, detail="Could not validate API key"
    )

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    api_key: APIKey = Depends(get_api_key)
):
    try:
        # Get wallet data for the user
        wallet_data = await app.state.connections.wallet_redis.get_wallet_data(request.user)
        logger.info(f"Wallet data retrieved for user {request.user}: {wallet_data is not None}")
        
        # Initialize values for CdpAgentkitWrapper
        values = {}
        if wallet_data:
            values = {"cdp_wallet_data": json.dumps(wallet_data)}
        else:
            temp_wrapper = CdpAgentkitWrapper()
            initial_wallet = temp_wrapper.export_wallet()
            await app.state.connections.wallet_redis.save_wallet_data(
                request.user, 
                json.loads(initial_wallet)
            )
            values = {"cdp_wallet_data": initial_wallet}
        
        # Get chat history
        chat_history = await app.state.connections.chat_redis.get_chat_history(request.user)
        logger.info(f"Chat history retrieved for user {request.user}")
        
        # Initialize agent for this request
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
        
        # Use stream to see intermediate steps
        final_response = None
        all_messages = []
        
        async for chunk in agent_executor.astream(
            agent_input,
            agent_config
        ):
            if isinstance(chunk, dict):
                if "agent" in chunk and chunk["agent"].get("messages"):
                    msg = chunk["agent"]["messages"][0]
                    all_messages.append(msg)
                    
                    # Log only tool calls
                    if hasattr(msg, "additional_kwargs"):
                        tool_calls = msg.additional_kwargs.get("tool_calls", [])
                        for tool_call in tool_calls:
                            if isinstance(tool_call, dict):
                                tool_name = tool_call.get('function', {}).get('name')
                                tool_args = tool_call.get('function', {}).get('arguments')
                                logger.info(f"Using tool {tool_name} with args {tool_args}")
                
                # Log tool responses
                elif "tools" in chunk and chunk["tools"].get("messages"):
                    msg = chunk["tools"]["messages"][0]
                    all_messages.append(msg)
                    logger.info(f"Tool response: {msg.content}")
        
        # Get the final response from the last non-empty message
        final_response = next(
            (msg.content for msg in reversed(all_messages) if msg.content),
            "No response generated"
        )
        
        # Save the conversation to Redis
        await app.state.connections.chat_redis.save_chat_history(
            request.user,
            messages + [HumanMessage(content=final_response)]
        )
        
        print("-"*50)
        print(f"\n{final_response}\n")
        print("-"*50)
        return ChatResponse(response=final_response)
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 