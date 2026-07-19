from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail
from django.conf import settings
from shop.models import Order, OrderItem, Product
from django.db.models import Sum

@shared_task(name="agent.tasks.send_weekly_sales_report")
def send_weekly_sales_report(recipient_email):
    print(f"[Celery Task] Weekly sales report task started for recipient: {recipient_email}", flush=True)
    
    now = timezone.now()
    one_week_ago = now - timedelta(days=7)
    
    # Get successful orders
    orders = Order.objects.filter(
        created_at__gte=one_week_ago,
        status__in=['paid', 'shipped', 'delivered']
    )
    
    total_sales = orders.aggregate(total=Sum('total_amount'))['total'] or 0.0
    total_orders = orders.count()
    
    # Get top selling products
    items = OrderItem.objects.filter(order__in=orders) \
        .values('product__name', 'product__sku_code') \
        .annotate(qty=Sum('quantity'), revenue=Sum('price')) \
        .order_by('-qty')[:5]
        
    # Construct Plain-Text Report
    report = []
    report.append("==========================================")
    report.append("          WEEKLY SALES REPORT             ")
    report.append("==========================================")
    report.append(f"Report Generated: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    report.append(f"Period: {one_week_ago.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')}")
    report.append("")
    report.append(f"Total Revenue: INR {total_sales:.2f}")
    report.append(f"Total Completed Orders: {total_orders}")
    report.append("")
    report.append("TOP 5 SELLING PRODUCTS:")
    report.append("-----------------------")
    
    if len(items) > 0:
        for idx, item in enumerate(items, 1):
            report.append(f"{idx}. {item['product__name']} (SKU: {item['product__sku_code']})")
            report.append(f"   Quantity Sold: {item['qty']} | Revenue: INR {item['revenue']:.2f}")
    else:
        report.append("No sales recorded during this period.")
        
    report.append("")
    report.append("==========================================")
    
    body = "\n".join(report)
    subject = f"Weekly Sales Report: {one_week_ago.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')}"
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'store@example.com')
    
    print(f"[Celery Task] Generating report with total sales = {total_sales}, total orders = {total_orders}. Sending email...", flush=True)
    
    send_mail(
        subject=subject,
        message=body,
        from_email=from_email,
        recipient_list=[recipient_email],
        fail_silently=False,
    )
    
    print(f"[Celery Task] Weekly sales report sent successfully to {recipient_email}", flush=True)
    
    return f"Report sent successfully to {recipient_email}. Total Sales: {total_sales}, Total Orders: {total_orders}"


@shared_task(name="agent.tasks.restore_product_price")
def restore_product_price(sku_code, original_price):
    print(f"[Celery Task] Restore product price task triggered for SKU: {sku_code}, restoring to original price: {original_price}", flush=True)
    try:
        product = Product.objects.get(sku_code=sku_code)
        product.price = original_price
        product.save()
        print(f"[Celery Task] Successfully restored price of {product.name} ({sku_code}) back to {original_price}", flush=True)
        return f"Successfully restored price of {product.name} ({sku_code}) back to {original_price}"
    except Product.DoesNotExist:
        print(f"[Celery Task ERROR] Product with SKU {sku_code} not found.", flush=True)
        return f"Product with SKU {sku_code} not found."


@shared_task(name="agent.tasks.send_email")
def send_email_task(recipient, subject, body):
    print(f"[Celery Task] Sending scheduled email to {recipient} with subject: {subject}", flush=True)
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'store@example.com')
    send_mail(
        subject=subject,
        message=body,
        from_email=from_email,
        recipient_list=[recipient],
        fail_silently=False,
    )
    print(f"[Celery Task] Scheduled email sent successfully to {recipient}", flush=True)
    return f"Email sent to {recipient} with subject '{subject}'"
