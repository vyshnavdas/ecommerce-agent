from shop.models import Product, ProductImage
import uuid
from langchain.tools import tool
from .tools_helper import generate_sql, validate_sql, execute_sql
from langchain_groq import ChatGroq
import os 

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

