from .models import Cart


def cart_count(request):
    """Inject cart_count and cart_total into every template context."""
    count = 0
    total = '0.00'
    try:
        if request.user.is_authenticated:
            cart = Cart.objects.filter(user=request.user).first()
        else:
            session_key = request.session.session_key
            cart = Cart.objects.filter(session_key=session_key, user=None).first() if session_key else None

        if cart:
            count = cart.item_count()
            total = '{:.2f}'.format(cart.total())
    except Exception:
        pass
    return {'cart_count': count, 'cart_total': total}
