from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class LoginRedirectTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='shopper', password='test-password')

    def test_login_redirects_to_safe_next_url(self):
        response = self.client.post(
            f"{reverse('login')}?next=/account/",
            {'username': self.user.username, 'password': 'test-password'},
        )

        self.assertRedirects(response, '/account/', fetch_redirect_response=False)

    def test_login_rejects_external_next_url(self):
        response = self.client.post(
            f"{reverse('login')}?next=https://malicious.example",
            {'username': self.user.username, 'password': 'test-password'},
        )

        self.assertRedirects(response, reverse('landing'), fetch_redirect_response=False)
