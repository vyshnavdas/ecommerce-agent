from django.contrib import admin
from .models import Product, ProductImage, Order, OrderItem, Cart, CartItem, Review


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display  = ('name', 'sku_code', 'price', 'stock', 'is_featured')
    list_filter   = ('is_featured',)
    search_fields = ('name', 'sku_code')
    list_editable = ('price', 'stock', 'is_featured')


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ('product', 'image')


class OrderItemInline(admin.TabularInline):
    model  = OrderItem
    extra  = 0
    fields = ('product', 'size', 'quantity', 'price')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display  = ('id', 'user', 'status', 'total_amount', 'created_at')
    list_filter   = ('status',)
    search_fields = ('user__username', 'stripe_payment_intent_id')
    inlines       = [OrderItemInline]
    readonly_fields = ('created_at', 'stripe_payment_intent_id')


class CartItemInline(admin.TabularInline):
    model  = CartItem
    extra  = 0
    fields = ('product', 'size', 'quantity')


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'session_key', 'created_at')
    inlines      = [CartItemInline]


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('product__name', 'user__username', 'comment')