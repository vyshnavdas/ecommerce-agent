import os
from dotenv import load_dotenv
from langchain.agents import create_agent
from langgraph.checkpoint.postgres import PostgresSaver
from .tools import add_product, update_product, delete_product, analytics_tool
from langchain.messages import RemoveMessage, AIMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langchain.agents.middleware import before_model
from langchain_groq import ChatGroq
from datetime import datetime

load_dotenv()

DB_URI = os.getenv('DATABASE_URL')

saver_cm = PostgresSaver.from_conn_string(DB_URI)
checkpointer = saver_cm.__enter__()
checkpointer.setup()

model = ChatGroq(
        model="qwen/qwen3-32b",
        temperature=0,
    )

tools = [add_product, update_product, delete_product, analytics_tool]

current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
SYSTEM_PROMPT = f"""
    You are an AI assistant that manages an e-commerce store using tools.
    
    Current date and time: {current_time}
    
    Your responsibilities include:
    - Managing products (add, update, delete)
    - Answering analytics and reporting queries using database tools

    General Rules:
    - Be concise, clear, and factual
    - Never guess or assume missing data
    - Ask the user for clarification if required

    Tool Usage Rules:
    - ALWAYS use tools when performing actions or retrieving data
    - NEVER perform operations or answer analytics questions directly without tools

    Product Management:
    - Use add_product when creating a product
    - Use update_product when modifying a product
    - Use delete_product only after explicit user confirmation

    Analytics:
    - Use analytics_tool for ANY query related to:
    - sales (today, weekly, monthly, etc.)
    - revenue or profit
    - product performance
    - inventory insights
    - reports or statistics
    - NEVER generate SQL or database queries in your response
    - ALWAYS rely on analytics_tool for data retrieval
    - You don't need to generate sql queries and don't ask user for sql queries 

    Behavior:
    - If a request is ambiguous, ask follow-up questions before using a tool
    - If the user asks for confirmation (especially delete), wait before proceeding
    - If a tool fails, explain the issue clearly

    Important:
    - You are a tool-using assistant, not a knowledge-based chatbot
    - Your answers must be based on tool outputs, not assumptions
    - 
    Do not delete the product without asking for an confirmation
    """

@before_model
def trim_messages(state, runtime):
    messages = state["messages"]

    # STEP 1: keep last N messages FIRST
    MAX_MESSAGES = 5
    recent = messages[-MAX_MESSAGES:]

    # STEP 2: remove reasoning_content only from recent messages
    cleaned = []
    for msg in recent:
        if isinstance(msg, AIMessage):
            msg.additional_kwargs.pop("reasoning_content", None)
        cleaned.append(msg)

    return {
        "messages": [
            RemoveMessage(id=REMOVE_ALL_MESSAGES),
            *cleaned
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

