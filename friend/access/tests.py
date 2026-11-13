from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse

from .models import (
    Resource, AccessGroup, AccessGrant, AccessRequest,
    NetworkResourceDetail,
)

User = get_user_model()


class ModelTests(TestCase):
    """Тесты моделей."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            last_name='Тестовый',
            first_name='Иван',
        )
        self.resource = Resource.objects.create(
            name='Test Resource',
            type=Resource.Type.NETWORK,
        )
        self.group = AccessGroup.objects.create(name='Test Group')

    def test_resource_str(self):
        self.assertEqual(str(self.resource), 'Сетевой ресурс: Test Resource')

    def test_group_str(self):
        self.assertEqual(str(self.group), 'Test Group')

    def test_access_grant_str(self):
        grant = AccessGrant.objects.create(
            grant_type='user',
            user=self.user,
            resource=self.resource,
            level=AccessGrant.Level.READ,
        )
        expected = 'Тестовый Иван → Test Resource (Чтение)'
        self.assertEqual(str(grant), expected)

    def test_access_request_str(self):
        request = AccessRequest.objects.create(
            requester=self.user,
            resource=self.resource,
            level=AccessGrant.Level.READ,
        )
        expected = 'Тестовый Иван → Test Resource (Новая)'
        self.assertEqual(str(request), expected)


class ViewTests(TestCase):
    """Тесты представлений."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            last_name='Тестовый',
            first_name='Иван',
        )
        self.client.login(username='testuser', password='testpass123')

    def test_resource_list_view(self):
        url = reverse('access:resource_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'access/resource_list.html')

    def test_group_list_view(self):
        url = reverse('access:group_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'access/group_list.html')

    def test_grant_list_view(self):
        url = reverse('access:grant_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'access/grant_list.html')

    def test_request_list_view(self):
        url = reverse('access:request_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'access/request_list.html')

    def test_resource_create_view_get(self):
        url = reverse('access:resource_create')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'access/resource_form.html')

    def test_unauthorized_redirect(self):
        self.client.logout()
        url = reverse('access:resource_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)
