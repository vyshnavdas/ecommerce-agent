from django.core.management.base import BaseCommand
from shop.models import Product, Order, OrderItem
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
import random


class Command(BaseCommand):
    help = "Seed database with analytics-friendly dataset"

    def handle(self, *args, **kwargs):
        self.stdout.write("Seeding advanced dataset...")

        # Clear old data
        OrderItem.objects.all().delete()
        Order.objects.all().delete()
        Product.objects.all().delete()

        # 🔹 Create products with roles
        bestseller = Product.objects.create(
            name="Bestseller Shirt",
            price=Decimal(1000),
            sku_code="SKU-1",
            stock=100
        )

        slow_product = Product.objects.create(
            name="Slow Shoes",
            price=Decimal(2000),
            sku_code="SKU-2",
            stock=50
        )

        no_sales_product = Product.objects.create(
            name="Dead Stock Jacket",
            price=Decimal(3000),
            sku_code="SKU-3",
            stock=30
        )

        out_of_stock = Product.objects.create(
            name="Out of Stock Hat",
            price=Decimal(500),
            sku_code="SKU-4",
            stock=0
        )

        normal_product = Product.objects.create(
            name="Regular Jeans",
            price=Decimal(1500),
            sku_code="SKU-5",
            stock=80
        )

        products = [bestseller, slow_product, normal_product]

        # 🔹 Create orders over last 10 days
        for day in range(10):
            date = timezone.now() - timedelta(days=day)

            # trend: more orders on recent days
            order_count = 2 + day  

            # weekend boost
            if date.weekday() >= 5:
                order_count += 3

            for _ in range(order_count):
                order = Order.objects.create(
                    created_at=date,
                    total_amount=0
                )

                total = Decimal(0)

                # Bestseller appears often
                if random.random() < 0.8:
                    qty = random.randint(1, 4)
                    OrderItem.objects.create(
                        order=order,
                        product=bestseller,
                        quantity=qty,
                        price=bestseller.price
                    )
                    total += bestseller.price * qty

                # Slow product rarely appears
                if random.random() < 0.3:
                    qty = 1
                    OrderItem.objects.create(
                        order=order,
                        product=slow_product,
                        quantity=qty,
                        price=slow_product.price
                    )
                    total += slow_product.price

                # Normal product medium frequency
                if random.random() < 0.5:
                    qty = random.randint(1, 2)
                    OrderItem.objects.create(
                        order=order,
                        product=normal_product,
                        quantity=qty,
                        price=normal_product.price
                    )
                    total += normal_product.price * qty

                # occasional high-value spike
                if random.random() < 0.1:
                    qty = 10
                    OrderItem.objects.create(
                        order=order,
                        product=bestseller,
                        quantity=qty,
                        price=bestseller.price
                    )
                    total += bestseller.price * qty

                order.total_amount = total
                order.save()

        self.stdout.write(self.style.SUCCESS("Advanced dataset created!"))