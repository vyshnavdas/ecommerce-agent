// Stripe Elements integration for checkout
(function () {
  'use strict';

  const stripe = Stripe(STRIPE_PK);
  const elements = stripe.elements();

  const style = {
    base: {
      color: '#2E2E2E',
      fontFamily: "'Inter', sans-serif",
      fontSize: '15px',
      fontSmoothing: 'antialiased',
      '::placeholder': { color: '#B0A898' },
    },
    invalid: { color: '#E05252', iconColor: '#E05252' },
  };

  const card = elements.create('card', { style, hidePostalCode: false });
  card.mount('#card-element');

  card.on('change', function (event) {
    const errEl = document.getElementById('card-errors');
    errEl.textContent = event.error ? event.error.message : '';
  });

  const form = document.getElementById('payment-form');
  const submitBtn = document.getElementById('submit-payment');

  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    submitBtn.disabled = true;
    submitBtn.textContent = 'Processing…';

    const { error, paymentIntent } = await stripe.confirmCardPayment(CLIENT_SECRET, {
      payment_method: {
        card: card,
        billing_details: {
          name: document.getElementById('id_shipping_name').value,
        },
      },
    });

    if (error) {
      document.getElementById('card-errors').textContent = error.message;
      submitBtn.disabled = false;
      submitBtn.textContent = 'Pay Now';
    } else if (paymentIntent.status === 'succeeded') {
      window.location.href = SUCCESS_URL;
    }
  });
})();
