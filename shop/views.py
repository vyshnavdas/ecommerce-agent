from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.views.decorators.http import require_POST
import stripe

from .models import Product, Cart, CartItem, Order, OrderItem, Review

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
    reviews = product.reviews.all().order_by('-created_at')
    avg_rating = 0.0
    if reviews.exists():
        avg_rating = sum(r.rating for r in reviews) / reviews.count()
    return render(request, 'product_detail.html', {
        'product': product,
        'reviews': reviews,
        'avg_rating': round(avg_rating, 1),
        'avg_rating_int': int(round(avg_rating)),
        'rating_range': range(1, 6),
    })


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
        # 1. Collect shipping details from local form
        shipping_name = request.POST.get('shipping_name', '').strip()
        shipping_address = request.POST.get('shipping_address', '').strip()
        shipping_city = request.POST.get('shipping_city', '').strip()
        shipping_zip = request.POST.get('shipping_zip', '').strip()

        if not (shipping_name and shipping_address and shipping_city and shipping_zip):
            messages.error(request, 'Please fill in all shipping details.')
            return render(request, 'checkout.html', {'cart': cart, 'step': 'address'})

        # 2. Create pending Order in DB
        order = Order.objects.create(
            user=request.user if request.user.is_authenticated else None,
            total_amount=cart.total(),
            status='pending',
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

        # Store pending order ID in session
        request.session['pending_order_id'] = order.id

        # 3. Build line items for Stripe Checkout
        line_items = []
        for item in cart.items.all():
            line_items.append({
                'price_data': {
                    'currency': 'inr',
                    'product_data': {
                        'name': f"{item.product.name} ({item.size})" if item.size else item.product.name,
                    },
                    'unit_amount': int(item.product.price * 100),
                },
                'quantity': item.quantity,
            })

        try:
            # 4. Create Stripe Checkout Session
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=line_items,
                mode='payment',
                success_url=request.build_absolute_uri(reverse('checkout_success')) + '?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=request.build_absolute_uri(reverse('checkout_cancel')),
                metadata={
                    'order_id': order.id,
                }
            )
            
            # Save Stripe session/intent ID on order
            order.stripe_payment_intent_id = session.id
            order.save()
            
            return redirect(session.url, code=303)
        except Exception as e:
            # Roll back order if Stripe session creation fails
            order.delete()
            messages.error(request, f"Stripe Checkout error: {str(e)}")
            return render(request, 'checkout.html', {'cart': cart, 'step': 'address'})

    # GET request: render the shipping address form
    return render(request, 'checkout.html', {
        'cart': cart,
        'step': 'address',
    })


def checkout_success(request):
    session_id = request.GET.get('session_id')
    if not session_id:
        return redirect('landing')

    try:
        session = stripe.checkout.Session.retrieve(session_id)
        metadata = getattr(session, 'metadata', {})
        if hasattr(metadata, 'to_dict'):
            metadata = metadata.to_dict()
        order_id = metadata.get('order_id')
        
        if not order_id:
            return redirect('landing')
            
        order = get_object_or_404(Order, id=order_id)
        
        # Verify payment status
        if session.payment_status == 'paid' or session.status == 'complete':
            order.status = 'paid'
            order.save()
            
            # Clear cart
            cart = _get_or_create_cart(request)
            cart.items.all().delete()
            
        return render(request, 'success.html', {'order': order})
    except Exception as e:
        messages.error(request, f"Error completing checkout: {str(e)}")
        return redirect('cart_detail')


def checkout_cancel(request):
    order_id = request.session.pop('pending_order_id', None)
    if order_id:
        Order.objects.filter(id=order_id, status='pending').delete()
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


@login_required
@require_POST
def add_review(request, pk):
    product = get_object_or_404(Product, pk=pk)
    rating = request.POST.get('rating')
    comment = request.POST.get('comment', '').strip()

    if not rating:
        messages.error(request, 'Please provide a rating.')
        return redirect('product_detail', pk=pk)

    try:
        rating = int(rating)
        if rating < 1 or rating > 5:
            raise ValueError()
    except ValueError:
        messages.error(request, 'Invalid rating.')
        return redirect('product_detail', pk=pk)

    if not comment:
        messages.error(request, 'Please write a comment.')
        return redirect('product_detail', pk=pk)

    Review.objects.create(
        product=product,
        user=request.user,
        rating=rating,
        comment=comment
    )
    messages.success(request, 'Review submitted successfully!')
    return redirect('product_detail', pk=pk)