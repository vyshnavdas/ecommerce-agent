from shop.models import Product, ProductImage
import uuid
from langchain.tools import tool
from .tools_helper import generate_sql, validate_sql, execute_sql
from langchain_groq import ChatGroq
import os 

@tool
def add_product(name: str, price: float, stock: int, image_urls: list[str] = []) -> str:
    """
    Adds a new product to the store database.

    Args:
        name: Name of the product
        price: Price of the product
        stock: Available stock quantity
        image_urls: List of image URLs for the product
    """
    sku_code = "SKU-" + str(uuid.uuid4())[:8]
    product = Product.objects.create(
        name=name,
        price=price,
        stock=stock,
        sku_code=sku_code
    )

    for url in image_urls:
        ProductImage.objects.create(product=product, image=url)

    return f"Product '{product.name}' added successfully with SKU {sku_code}"

@tool
def update_product(sku_code: str, 
                   name: str | None = None, 
                   price: float | None = None, 
                   stock: int | None = None
    ) -> str:
    """
    Update an existing product using its SKU code.
    
    Args:
        sku_code: Unique SKU code of the product
        name: New product name
        price: Updated price
        stock: Updated stock quantity
    """
    print(sku_code, name, price, stock)
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
    product.save()

    return f"Product {product.name} updated successfully."


@tool
def delete_product(sku_code: str, confirm: bool = False) -> str:
    """
    Delete a product using its SKU code.
    Do not delete the product without asking for an confirmation
    """
    print(sku_code)
    try:
        product = Product.objects.get(sku_code=sku_code)
    except Product.DoesNotExist:
        return f"Product with SKU {sku_code} not found."
    
    if not confirm:
        return f"Are you sure want to delete {sku_code} ?"    

    product.delete()
    return f"✅ Product '{product.name}' (SKU {sku_code}) deleted."
    
    
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

