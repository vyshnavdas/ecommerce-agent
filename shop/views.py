from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.views.decorators.http import require_POST
import stripe

from .models import Product, Cart, CartItem, Order, OrderItem

stripe.api_key = settings.STRIPE_SECRET_KEY


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_or_create_cart(request):
    """Return (cart, created) for the current session or logged-in user."""
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
    else:
        if not request.session.session_key:
            request.session.create()
        session_key = request.session.session_key
        cart, created = Cart.objects.get_or_create(session_key=session_key, user=None)
    return cart


# ---------------------------------------------------------------------------
# Landing
# ---------------------------------------------------------------------------

def landing(request):
    featured = Product.objects.filter(is_featured=True, stock__gt=0)[:4]
    return render(request, 'landing.html', {'featured': featured})


# ---------------------------------------------------------------------------
# Product list & detail
# ---------------------------------------------------------------------------

def product_list(request):
    products = Product.objects.filter(stock__gt=0).order_by('name')
    size_filter = request.GET.get('size', '')
    if size_filter:
        products = [p for p in products if size_filter in (p.available_sizes or [])]
    return render(request, 'product_list.html', {
        'products': products,
        'size_filter': size_filter,
        'sizes': ['XS', 'S', 'M', 'L', 'XL', 'XXL'],
    })


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    return render(request, 'product_detail.html', {'product': product})


# ---------------------------------------------------------------------------
# Cart
# ---------------------------------------------------------------------------

def cart_detail(request):
    cart = _get_or_create_cart(request)
    return render(request, 'cart.html', {'cart': cart})


@require_POST
def add_to_cart(request, pk):
    product = get_object_or_404(Product, pk=pk)
    size = request.POST.get('size', '')
    quantity = int(request.POST.get('quantity', 1))
    cart = _get_or_create_cart(request)
    item, created = CartItem.objects.get_or_create(cart=cart, product=product, size=size)
    if not created:
        item.quantity += quantity
    else:
        item.quantity = quantity
    item.save()
    messages.success(request, f'"{product.name}" added to cart.')
    return redirect('cart_detail')


@require_POST
def remove_from_cart(request, item_id):
    cart = _get_or_create_cart(request)
    CartItem.objects.filter(id=item_id, cart=cart).delete()
    messages.info(request, 'Item removed from cart.')
    return redirect('cart_detail')


@require_POST
def update_cart(request, item_id):
    cart = _get_or_create_cart(request)
    quantity = int(request.POST.get('quantity', 1))
    if quantity < 1:
        CartItem.objects.filter(id=item_id, cart=cart).delete()
    else:
        CartItem.objects.filter(id=item_id, cart=cart).update(quantity=quantity)
    return redirect('cart_detail')


# ---------------------------------------------------------------------------
# Checkout
# ---------------------------------------------------------------------------

def checkout(request):
    cart = _get_or_create_cart(request)
    if not cart.items.exists():
        messages.warning(request, 'Your cart is empty.')
        return redirect('cart_detail')

    if request.method == 'POST':
        # Collect shipping details
        shipping_name = request.POST.get('shipping_name', '')
        shipping_address = request.POST.get('shipping_address', '')
        shipping_city = request.POST.get('shipping_city', '')
        shipping_zip = request.POST.get('shipping_zip', '')

        amount_cents = int(cart.total() * 100)

        try:
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency='usd',
                automatic_payment_methods={'enabled': True},
                metadata={
                    'cart_id': cart.id,
                    'user_id': request.user.id if request.user.is_authenticated else 'guest',
                },
            )
        except stripe.error.StripeError as e:
            messages.error(request, f'Payment error: {e.user_message}')
            return redirect('checkout')

        # Create order
        order = Order.objects.create(
            user=request.user if request.user.is_authenticated else None,
            total_amount=cart.total(),
            status='pending',
            stripe_payment_intent_id=intent.id,
            shipping_name=shipping_name,
            shipping_address=shipping_address,
            shipping_city=shipping_city,
            shipping_zip=shipping_zip,
        )
        for ci in cart.items.all():
            OrderItem.objects.create(
                order=order,
                product=ci.product,
                size=ci.size,
                quantity=ci.quantity,
                price=ci.product.price,
            )

        # Store in session for success page
        request.session['pending_order_id'] = order.id
        request.session['stripe_client_secret'] = intent.client_secret

        return render(request, 'checkout.html', {
            'cart': cart,
            'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY,
            'client_secret': intent.client_secret,
            'order': order,
            'shipping_name': shipping_name,
            'shipping_address': shipping_address,
            'shipping_city': shipping_city,
            'shipping_zip': shipping_zip,
            'step': 'payment',
        })

    return render(request, 'checkout.html', {
        'cart': cart,
        'step': 'address',
    })


def checkout_success(request):
    order_id = request.session.pop('pending_order_id', None)
    order = None
    if order_id:
        order = Order.objects.filter(id=order_id).first()
        if order:
            order.status = 'paid'
            order.save()
            # Clear cart
            cart = _get_or_create_cart(request)
            cart.items.all().delete()
    return render(request, 'success.html', {'order': order})


def checkout_cancel(request):
    return render(request, 'cancel.html')


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def register(request):
    if request.user.is_authenticated:
        return redirect('landing')
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')
        if password1 != password2:
            messages.error(request, 'Passwords do not match.')
        elif User.objects.filter(username=username).exists():
            messages.error(request, 'Username already taken.')
        else:
            user = User.objects.create_user(username=username, email=email, password=password1)
            login(request, user)
            messages.success(request, f'Welcome, {username}!')
            return redirect('landing')
    return render(request, 'register.html')


def login_view(request):
    if request.user.is_authenticated:
        return redirect('landing')
    if request.method == 'POST':
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            next_url = request.GET.get('next', 'landing')
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid username or password.')
    return render(request, 'login.html')


def logout_view(request):
    logout(request)
    return redirect('landing')


@login_required
def account(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'account.html', {'orders': orders})