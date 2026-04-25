import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain.agents import create_agent, AgentState
from langgraph.checkpoint.postgres import PostgresSaver
from .tools import add_product, update_product, delete_product
from langchain.messages import RemoveMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langchain.agents.middleware import before_model
from langgraph.runtime import Runtime
from typing import Any

load_dotenv()

DB_URI = os.getenv('DATABASE_URL')

saver_cm = PostgresSaver.from_conn_string(DB_URI)
checkpointer = saver_cm.__enter__()
checkpointer.setup()

model = ChatGroq(
    model="qwen/qwen3-32b",
    temperature=0,
    streaming=True,
)

tools = [add_product, update_product, delete_product]

SYSTEM_PROMPT = """
You are an AI assistant that manages an e-commerce store.

Rules:
- Do not use any  markup language in replies
- Only modify the store using the provided tools
- If a user asks to add or update a product, call the appropriate tool
- Be concise and clear in responses
- If you need any additional details for accessing a tool, always ask
- Do not delete the product without the confirmation
"""

@before_model
def trim_messages(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
    messages = state["messages"]
    
    KEEP_RECENT = 10
    
    if len(messages) <= 3:
        return None
    

    recent_messages = messages[-KEEP_RECENT:]
    
    return {
        "messages": [
            RemoveMessage(id=REMOVE_ALL_MESSAGES),
            *recent_messages
        ]
    }

    
agent = create_agent(
    model=model,
    tools=tools,
    checkpointer=checkpointer,
    system_prompt=SYSTEM_PROMPT,
    middleware=[
        trim_messages,
    ]
)

