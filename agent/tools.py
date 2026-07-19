from shop.models import Product, ProductImage
import uuid
from langchain.tools import tool
from agent.tools_helper import generate_sql, validate_sql, execute_sql
from langchain_groq import ChatGroq
import os 
import logging

logger = logging.getLogger(__name__)

@tool
def add_product(
    name: str,
    price: float,
    stock: int,
    description: str = "",
    available_sizes: list[str] = [],
    is_featured: bool = False,
    image_urls: list[str] = [],
) -> str:
    """
    Adds a new product to the store database.

    Args:
        name: Name of the product
        price: Price of the product
        stock: Available stock quantity
        description: Optional product description
        available_sizes: List of available sizes e.g. ["S", "M", "L", "XL"]
        is_featured: Whether to feature this product on the landing page(do not use string use python boolean value True or False)
        image_urls: List of image URLs for the product
    """
    sku_code = "SKU-" + str(uuid.uuid4())[:8]
    product = Product.objects.create(
        name=name,
        price=price,
        stock=stock,
        sku_code=sku_code,
        description=description,
        available_sizes=available_sizes,
        is_featured=is_featured,
    )

    for url in image_urls:
        ProductImage.objects.create(product=product, image=url)

    return f"Product '{product.name}' added successfully with SKU {sku_code}"

@tool
def update_product(
    sku_code: str,
    name: str | None = None,
    price: float | None = None,
    stock: int | None = None,
    description: str | None = None,
    available_sizes: list[str] | None = None,
    is_featured: bool | None = None,
) -> str:
    """
    Update an existing product using its SKU code.

    Args:
        sku_code: Unique SKU code of the product
        name: New product name
        price: Updated price
        stock: Updated stock quantity
        description: Updated product description
        available_sizes: Updated list of available sizes e.g. ["S", "M", "L"]
        is_featured: Set True to feature on landing page, False to un-feature
    """
    print(sku_code, name, price, stock, description, available_sizes, is_featured)
    try:
        product = Product.objects.get(sku_code=sku_code)
    except Product.DoesNotExist:
        return f"Product with SKU {sku_code} not found."

    if name is not None:
        product.name = name
    if price is not None:
        product.price = price
    if stock is not None:
        product.stock = stock
    if description is not None:
        product.description = description
    if available_sizes is not None:
        product.available_sizes = available_sizes
    if is_featured is not None:
        product.is_featured = is_featured
    product.save()

    return f"Product '{product.name}' updated successfully."


@tool
def delete_product(sku_code: str) -> str:
    """
    Delete a product using its SKU code.
    IMPORTANT: Only call this tool AFTER the user has explicitly confirmed the deletion.
    If the user has not confirmed, ask for confirmation first and do not call this tool yet.

    Args:
        sku_code: Unique SKU code of the product to delete
    """
    print(sku_code)
    try:
        product = Product.objects.get(sku_code=sku_code)
    except Product.DoesNotExist:
        return f"Product with SKU {sku_code} not found."

    name = product.name
    product.delete()
    return f"✅ Product '{name}' (SKU {sku_code}) deleted successfully."
    
    
@tool
def analytics_tool(query: str) -> str:
    """
    Executes analytics queries on the database.

    IMPORTANT:
    - Input is natural language (NOT SQL)
    - This tool automatically converts it to SQL and executes it
    - ALWAYS use this tool for:
        - sales reports
        - revenue
        - product analytics
        - inventory insights

    DO NOT ask the user for SQL.
    DO NOT refuse analytics queries.
    NEVER ask the user for schema clarification
    """
    try:
        model = ChatGroq(
            model="llama-3.1-8b-instant",
            temperature=0,
            api_key=os.getenv("GROQ_SQL_API_KEY"),
        )
        sql = generate_sql(query, model)

        validate_sql(sql)

        result = execute_sql(sql)

        if not result:
            return "No data found."

        return f"Query result: {result}"

    except Exception as e:
        return f"Error: {str(e)}"


@tool
def send_email_tool(
    recipient: str,
    subject: str,
    body: str,
) -> str:
    """
    Sends an email to a customer or admin.

    Args:
        recipient: Destination email address
        subject: Subject of the email
        body: Plain text body of the email
    """
    from django.core.mail import send_mail
    from django.conf import settings
    import re
    
    try:
        if not re.match(r"[^@]+@[^@]+\.[^@]+", recipient):
            return f"Error: Invalid recipient email address: '{recipient}'"

        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'store@example.com')
        
        send_mail(
            subject=subject,
            message=body,
            from_email=from_email,
            recipient_list=[recipient],
            fail_silently=False,
        )
        return f"Email sent successfully to {recipient} with subject '{subject}'"
    except Exception as e:
        return f"Error sending email: {str(e)}"


@tool
def schedule_task(
    task_name: str,
    schedule_type: str,
    task_args: str | None = None,
    task_kwargs: str | None = None,
    cron_expression: str | None = None,
    run_at: str | None = None,
) -> str:
    """
    Schedules any registered background task using Celery.

    Args:
        task_name: The registered Celery task name (e.g. "agent.tasks.send_weekly_sales_report", "agent.tasks.restore_product_price", "agent.tasks.send_email").
        schedule_type: Type of schedule ("cron" or "clocked").
        task_args: Optional JSON-serialized list of positional arguments to pass to the task (e.g. '["test@example.com"]' or '["SKU-XYZ", 12.99]').
        task_kwargs: Optional JSON-serialized dictionary of keyword arguments to pass to the task (e.g. '{"sku_code": "SKU-XYZ"}').
        cron_expression: Cron string (e.g. "0 9 * * 1" for Mondays at 9am) if schedule_type is "cron".
          Format: "minute hour day_of_month month_of_year day_of_week". Use "*" for any.
        run_at: Date/time for clocked tasks (e.g. "2026-07-20 14:00:00" or relative like "in 24 hours", "in 1 hour").
    """
    import json
    from django_celery_beat.models import PeriodicTask, CrontabSchedule, ClockedSchedule
    from django.utils import timezone
    from datetime import datetime, timedelta
    
    print(f"[Agent Tool] schedule_task tool called: task_name={task_name}, schedule_type={schedule_type}, task_args={task_args}, task_kwargs={task_kwargs}, cron_expression={cron_expression}, run_at={run_at}", flush=True)
    
    # 1. Clean and validate inputs
    task_name = task_name.strip()
    schedule_type = schedule_type.strip().lower()
    
    # Parse JSON-serialized task_args and task_kwargs
    try:
        args_list = json.loads(task_args) if task_args else []
        if not isinstance(args_list, list):
            return f"Error: task_args must be a JSON list/array, got {type(args_list).__name__}."
    except Exception as e:
        return f"Error parsing JSON for task_args: {str(e)}"
        
    try:
        kwargs_dict = json.loads(task_kwargs) if task_kwargs else {}
        if not isinstance(kwargs_dict, dict):
            return f"Error: task_kwargs must be a JSON dictionary/object, got {type(kwargs_dict).__name__}."
    except Exception as e:
        return f"Error parsing JSON for task_kwargs: {str(e)}"
    
    # Derive a descriptive name for the task
    short_task_name = task_name.split(".")[-1]
    param_str = f"args={args_list}" if args_list else ""
    if kwargs_dict:
        param_str += f" kwargs={kwargs_dict}"
    default_name = f"Dynamic: {short_task_name} ({param_str.strip()})"
    
    # 2. Handle schedules
    if schedule_type == "cron":
        if not cron_expression:
            return "Error: 'cron_expression' is required for cron schedule type."
        parts = cron_expression.strip().split()
        if len(parts) != 5:
            return f"Error: Invalid cron_expression '{cron_expression}'. Must have 5 fields: 'minute hour day_of_month month_of_year day_of_week'"
        
        cron_schedule, _ = CrontabSchedule.objects.get_or_create(
            minute=parts[0],
            hour=parts[1],
            day_of_month=parts[2],
            month_of_year=parts[3],
            day_of_week=parts[4],
        )
        
        task, created = PeriodicTask.objects.update_or_create(
            name=default_name,
            defaults={
                "crontab": cron_schedule,
                "task": task_name,
                "args": json.dumps(args_list),
                "kwargs": json.dumps(kwargs_dict),
                "enabled": True,
                "clocked": None,
                "one_off": False,
            }
        )
        verb = "created" if created else "updated"
        print(f"[Agent Tool] Successfully {verb} cron task: {task.name} (cron: {cron_expression})", flush=True)
        return f"Success: Recurring task '{task.name}' {verb} with cron schedule '{cron_expression}'."
        
    elif schedule_type == "clocked":
        if not run_at:
            return "Error: 'run_at' is required for clocked schedule type."
            
        run_at = run_at.strip().lower()
        now = timezone.now()
        
        # Parse relative duration (e.g. "in 24 hours", "in 15 minutes", "in 1 day")
        if run_at.startswith("in "):
            try:
                parts = run_at.split()
                amount = float(parts[1])
                unit = parts[2].rstrip('s')
                
                if unit == "hour":
                    delta = timedelta(hours=amount)
                elif unit == "minute":
                    delta = timedelta(minutes=amount)
                elif unit == "second":
                    delta = timedelta(seconds=amount)
                elif unit == "day":
                    delta = timedelta(days=amount)
                else:
                    return f"Error: Unsupported unit '{unit}' in 'run_at' expression. Supported units: hour, minute, second, day."
                
                target_time = now + delta
            except Exception as e:
                return f"Error parsing relative 'run_at' string '{run_at}': {str(e)}"
        else:
            # Parse absolute datetime format YYYY-MM-DD HH:MM:SS
            try:
                naive_dt = datetime.strptime(run_at, "%Y-%m-%d %H:%M:%S")
                target_time = timezone.make_aware(naive_dt, timezone.get_current_timezone())
            except Exception as e:
                return f"Error parsing absolute 'run_at' string '{run_at}'. Expected format: 'YYYY-MM-DD HH:MM:SS' or relative format like 'in 24 hours'. Details: {str(e)}"
                
        if target_time <= now:
            return f"Error: The scheduled time '{target_time}' is in the past. Current time is '{now}'."
            
        clocked_schedule, _ = ClockedSchedule.objects.get_or_create(
            clocked_time=target_time
        )
        
        unique_name = f"{default_name} (runs at {target_time.strftime('%Y-%m-%d %H:%M:%S')})"
        
        task = PeriodicTask.objects.create(
            name=unique_name,
            task=task_name,
            clocked=clocked_schedule,
            one_off=True,
            args=json.dumps(args_list),
            kwargs=json.dumps(kwargs_dict),
            enabled=True,
        )
        print(f"[Agent Tool] Successfully scheduled clocked task: {task.name} (run_at: {target_time})", flush=True)
        return f"Success: One-off task '{task.name}' scheduled to run at {target_time}."
    else:
        return f"Error: Unsupported schedule_type '{schedule_type}'. Supported: 'cron', 'clocked'."


@tool
def list_scheduled_tasks() -> str:
    """
    Lists all currently scheduled and active background tasks in the database.
    """
    from django_celery_beat.models import PeriodicTask
    
    print("[Agent Tool] list_scheduled_tasks tool called. Querying active scheduled tasks...", flush=True)
    tasks = PeriodicTask.objects.filter(enabled=True).order_by('name')
    print(f"[Agent Tool] Found {tasks.count()} active scheduled tasks.", flush=True)
    if not tasks.exists():
        return "No scheduled tasks found."
        
    lines = []
    lines.append(f"{'Task Name':<60} | {'Schedule Type':<15} | {'Schedule Details':<30} | {'Args':<40}")
    lines.append("-" * 155)
    
    for t in tasks:
        if t.crontab:
            sch_type = "Cron"
            sch_details = f"minute={t.crontab.minute} hour={t.crontab.hour} day_of_week={t.crontab.day_of_week}"
        elif t.clocked:
            sch_type = "Clocked"
            sch_details = str(t.clocked.clocked_time)
        elif t.interval:
            sch_type = "Interval"
            sch_details = f"every {t.interval.every} {t.interval.period}"
        else:
            sch_type = "Other"
            sch_details = "N/A"
            
        lines.append(f"{t.name:<60} | {sch_type:<15} | {sch_details:<30} | {t.args:<40}")
        
    return "\n".join(lines)


@tool
def cancel_scheduled_task(task_name: str) -> str:
    """
    Cancels and deletes a scheduled task by name.

    Args:
        task_name: The exact name of the task as listed by list_scheduled_tasks.
    """
    from django_celery_beat.models import PeriodicTask
    
    print(f"[Agent Tool] cancel_scheduled_task tool called for query: {task_name}", flush=True)
    try:
        task = PeriodicTask.objects.get(name=task_name)
        task_desc = task.name
        task.delete()
        print(f"[Agent Tool] Successfully cancelled and deleted scheduled task: {task_desc}", flush=True)
        return f"Success: Scheduled task '{task_desc}' cancelled and deleted."
    except PeriodicTask.DoesNotExist:
        # Try substring match
        matches = PeriodicTask.objects.filter(name__icontains=task_name)
        if matches.count() == 1:
            task = matches.first()
            task_desc = task.name
            task.delete()
            print(f"[Agent Tool] Successfully cancelled and deleted scheduled task: {task_desc} (matched by substring)", flush=True)
            return f"Success: Scheduled task '{task_desc}' (matched by substring) cancelled and deleted."
        elif matches.count() > 1:
            names = [m.name for m in matches]
            print(f"[Agent Tool WARNING] Cancellation failed: Multiple tasks matched query '{task_name}': {names}", flush=True)
            return f"Error: Multiple tasks matched '{task_name}'. Please be more specific: {names}"
        print(f"[Agent Tool WARNING] Cancellation failed: No task matched query '{task_name}'", flush=True)
        return f"Error: Scheduled task named '{task_name}' not found."


