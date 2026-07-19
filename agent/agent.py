import os
import sys
import django
from django.apps import apps
from dotenv import load_dotenv

load_dotenv()

if not apps.ready:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecommerce.settings')
    django.setup()

from langchain.agents import create_agent
from langgraph.checkpoint.postgres import PostgresSaver
from agent.tools import add_product, update_product, delete_product, analytics_tool, send_email_tool, schedule_task, list_scheduled_tasks, cancel_scheduled_task
from langchain.messages import RemoveMessage, AIMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langchain.agents.middleware import before_model
from langchain_google_genai import ChatGoogleGenerativeAI
from datetime import datetime

DB_URI = os.getenv('DATABASE_URL')

# Check if running under LangGraph Studio / API dev server
is_langgraph = any(k.startswith("LANGGRAPH_") for k in os.environ) or (len(sys.argv) > 0 and 'langgraph' in sys.argv[0])

if is_langgraph:
    checkpointer = None
else:
    saver_cm = PostgresSaver.from_conn_string(DB_URI)
    checkpointer = saver_cm.__enter__()
    checkpointer.setup()

model = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite",
    api_key=os.getenv("GOOGLE_API_KEY"),
    )

tools = [add_product, update_product, delete_product, analytics_tool, send_email_tool, schedule_task, list_scheduled_tasks, cancel_scheduled_task]

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

    Email:
    - Use send_email_tool to send emails to customers or admins (e.g. sending reports, order status updates, confirmation notices, etc.)

    Task Scheduling:
    - Use schedule_task to schedule background tasks. Specify `task_name` using their registered Celery name.
    - IMPORTANT: `task_args` and `task_kwargs` MUST be passed as JSON-serialized strings (e.g. task_args='["test@example.com"]' or task_args='["SKU-XYZ", 12.99]'). Do NOT pass raw python lists or dicts.
    - Supported tasks:
      - "agent.tasks.send_weekly_sales_report": To send a weekly sales summary. Pass positional `task_args` (JSON array of string): e.g. task_args='["recipient_email"]'.
      - "agent.tasks.restore_product_price": To reset a product price back to original. Pass positional `task_args` (JSON array): e.g. task_args='["sku_code", 12.99]'.
      - "agent.tasks.send_email": To send a custom scheduled email. Pass positional `task_args` (JSON array of strings): e.g. task_args='["recipient", "subject", "body"]'.
    - Schedule Types:
      - "cron": For recurring tasks (e.g. sending a sales report every Monday). Requires a standard 5-field cron_expression like "0 9 * * 1" (minute hour day_of_month month_of_year day_of_week).
      - "clocked": For one-off tasks (e.g. running an offer for 24 hours). Requires run_at (either absolute "YYYY-MM-DD HH:MM:SS" or relative e.g., "in 24 hours", "in 1 hour", "in 15 minutes").
    - Running an Offer for a duration (e.g. 24 hours):
      1. First update the product's price immediately using update_product.
      2. Immediately schedule the price restoration using schedule_task with task_name="agent.tasks.restore_product_price", schedule_type="clocked", run_at="in 24 hours", and task_args as a JSON string containing the sku_code and original_price (e.g. task_args='["SKU-XYZ", 10.99]').
    - Use list_scheduled_tasks to check active scheduled tasks.
    - Use cancel_scheduled_task to cancel/remove a scheduled task by name.

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

