import os
from dotenv import load_dotenv
from langchain.agents import create_agent
from langgraph.checkpoint.postgres import PostgresSaver
from .tools import add_product, update_product, delete_product, analytics_tool
from langchain.messages import RemoveMessage, AIMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langchain.agents.middleware import before_model
from langchain_google_genai import ChatGoogleGenerativeAI
from datetime import datetime

load_dotenv()

DB_URI = os.getenv('DATABASE_URL')

saver_cm = PostgresSaver.from_conn_string(DB_URI)
checkpointer = saver_cm.__enter__()
checkpointer.setup()

model = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite",
    api_key=os.getenv("GOOGLE_API_KEY"),
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
      - Always ask for: name, price, stock
      - Optionally ask for: description, available_sizes (list like ["S","M","L","XL"]), is_featured
      - is_featured=True makes the product appear on the landing page hero section
    - Use update_product when modifying a product — you can update any of:
      name, price, stock, description, available_sizes, is_featured
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

    # Group messages into turns starting with HumanMessage
    turns = []
    current_turn = []
    for msg in messages:
        if msg.type == "human" and current_turn:
            turns.append(current_turn)
            current_turn = [msg]
        else:
            current_turn.append(msg)
    if current_turn:
        turns.append(current_turn)

    # Keep only the last 3 complete turns
    MAX_TURNS = 3
    recent_turns = turns[-MAX_TURNS:]

    cleaned = []
    for turn in recent_turns:
        for msg in turn:
            if isinstance(msg, AIMessage):
                msg.additional_kwargs.pop("reasoning_content", None)
                msg.additional_kwargs.pop("reasoning", None)
                if hasattr(msg, "response_metadata") and isinstance(msg.response_metadata, dict):
                    msg.response_metadata.pop("reasoning_content", None)
                    msg.response_metadata.pop("reasoning", None)
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

