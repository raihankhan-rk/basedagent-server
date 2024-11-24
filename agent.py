import os
import sys

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from langchain_core.runnables.history import RunnableWithMessageHistory

# Import CDP Agentkit Langchain Extension.
from cdp_langchain.agent_toolkits import CdpToolkit
from cdp_langchain.utils import CdpAgentkitWrapper
from cdp_langchain.tools import CdpTool

from tools import request_funds_on_mainnet, RequestFundsOnMainnetInput, REQUEST_FUNDS_ON_MAINNET_PROMPT
from prompts import SYSTEM_PROMPT

from dotenv import load_dotenv

load_dotenv()

# Configure a file to persist the agent's CDP MPC Wallet Data.
wallet_data_file = "wallet_data.txt"


def initialize_agent(values: dict = None, history=None):
    """Initialize the agent with CDP Agentkit."""
    # Initialize LLM.
    llm = ChatOpenAI(model="gpt-4o-mini")

    # Configure CDP Agentkit Langchain Extension.
    if values is None:
        values = {}
        
        # Only read from file if no values provided
        if os.path.exists(wallet_data_file):
            with open(wallet_data_file) as f:
                wallet_data = f.read()
                values = {"cdp_wallet_data": wallet_data}

    agentkit = CdpAgentkitWrapper(**values)

    # Initialize CDP Agentkit Toolkit and get tools.
    cdp_toolkit = CdpToolkit.from_cdp_agentkit_wrapper(agentkit)
    tools = cdp_toolkit.get_tools()

    request_funds_tool = CdpTool(
        name="request_funds_on_mainnet",
        description=REQUEST_FUNDS_ON_MAINNET_PROMPT,
        cdp_agentkit_wrapper=agentkit,
        args_schema=RequestFundsOnMainnetInput,
        func=request_funds_on_mainnet,
    )
    
    tools.append(request_funds_tool)

    # Store buffered conversation history in memory.
    memory = MemorySaver()
    
    # Create ReAct Agent using the LLM and CDP Agentkit tools.
    chain = create_react_agent(
        llm,
        tools=tools,
        checkpointer=memory,
        state_modifier=SYSTEM_PROMPT,
    )

    # If history is provided, wrap the chain with message history
    if history:
        chain = RunnableWithMessageHistory(
            chain,
            lambda session_id: history,
            input_messages_key="messages",
            history_messages_key="history"
        )

    return chain, {
        "configurable": {
            "session_id": "cli_user",
            "thread_id": "cli_user"  # Required by langgraph checkpointer
        }
    }


# Chat Mode
async def run_chat_mode(agent_executor, config):
    """Run the agent interactively based on user input."""
    print("Starting chat mode... Type 'exit' to end.")
    while True:
        try:
            user_input = input("\nUser: ")
            if user_input.lower() == "exit":
                break

            # Run agent with the user's input in chat mode using stream
            agent_input = {"messages": [HumanMessage(content=user_input)]}
            
            # Use stream to see intermediate steps
            async for chunk in agent_executor.astream(
                agent_input,
                config
            ):
                # Show tool calls and their results
                if isinstance(chunk, dict):
                    if "agent" in chunk and chunk["agent"].get("messages"):
                        print("\nThinking:", chunk["agent"]["messages"][0].content)
                    elif "tools" in chunk and chunk["tools"].get("messages"):
                        print("\nTool Call:", chunk["tools"]["messages"][0].content)
                    
                    # If there are tool calls, show them
                    if "agent" in chunk and hasattr(chunk["agent"].get("messages", [None])[0], "additional_kwargs"):
                        tool_calls = chunk["agent"]["messages"][0].additional_kwargs.get("tool_calls", [])
                        for tool_call in tool_calls:
                            if isinstance(tool_call, dict):
                                print(f"\nUsing tool: {tool_call.get('function', {}).get('name')}")
                                print(f"With args: {tool_call.get('function', {}).get('arguments')}")

            print("\n-------------------")

        except KeyboardInterrupt:
            print("Goodbye Agent!")
            sys.exit(0)
        except Exception as e:
            print(f"Error: {str(e)}")

async def main():
    """Start the chatbot agent."""
    agent_executor, config = initialize_agent()
    await run_chat_mode(agent_executor=agent_executor, config=config)

if __name__ == "__main__":
    print("Starting Agent...")
    import asyncio
    asyncio.run(main())