from django.db import connection
from django.apps import apps
from langchain_core.messages import SystemMessage, HumanMessage

def generate_sql(user_query: str, model) -> str:
    schema = """
        Table: shop_product
        Columns:
        - id (PK)
        - name
        - price
        - sku_code
        - stock

        Table: shop_order
        Columns:
        - id (PK)
        - created_at
        - total_amount

        Table: shop_orderitem
        Columns:
        - id (PK)
        - order_id (FK -> shop_order.id)
        - product_id (FK -> shop_product.id)
        - quantity
        - price
    """

    response = model.invoke([
        SystemMessage(content=f"""
            You are a PostgreSQL expert.

            STRICT RULES:
            - Only generate SELECT queries
            - Never use INSERT, UPDATE, DELETE, DROP, ALTER
            - Use ONLY the tables and columns provided
            - Use proper JOINs for foreign keys
            - Return ONLY SQL (no explanation, no markdown)
            - Always use table names exactly as given
            - Do not guess table names
            - ALWAYS summarize results using aggregation functions (SUM, COUNT, AVG)
            - ALWAYS use GROUP BY when dealing with products or sales

            Schema:
            {schema}
        """),
        HumanMessage(content=user_query)
    ])

    sql = response.content.strip()

    # 🔧 Clean common LLM junk
    sql = sql.replace("```sql", "").replace("```", "").strip()

    # 🔒 Extra safety check
    if not sql.lower().startswith("select"):
        raise Exception(f"Invalid SQL generated: {sql}")

    return sql


def validate_sql(sql: str):
    print(sql)
    sql_lower = sql.lower().strip()

    if not sql_lower.startswith("select"):
        raise Exception("Blocked: Only SELECT queries allowed")

    blocked_keywords = ["insert", "update", "delete", "drop", "alter"]
    if any(keyword in sql_lower for keyword in blocked_keywords):
        raise Exception("Blocked: Unsafe SQL detected")


def execute_sql(sql: str):
    with connection.cursor() as cursor:
        cursor.execute(sql)
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()

    return [dict(zip(columns, row)) for row in rows]

# def get_schema():
#     schema_lines = []

#     for model in apps.get_models():
#         table_name = model._meta.db_table
#         fields = []

#         for field in model._meta.fields:
#             field_info = field.name

#             if field.primary_key:
#                 field_info += " (PK)"
            
#             if field.is_relation:
#                 related_model = field.related_model._meta.db_table
#                 field_info += f" (FK -> {related_model})"

#             fields.append(field_info)

#         schema_lines.append(f"{table_name}({', '.join(fields)})")

#     return "\n".join(schema_lines)
