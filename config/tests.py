from unittest.mock import patch

from django.db import DatabaseError
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory

from authentication.throttles import AuthAddressThrottle


class DeploymentTests(TestCase):
    def test_health_checks_database(self):
        self.assertEqual(self.client.get('/health/').json(), {'status': 'ok'})
        with patch('config.health.connection.cursor', side_effect=DatabaseError('private connection details')):
            response = self.client.get('/health/')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {'status': 'unavailable'})
        self.assertNotContains(response, 'private connection details', status_code=503)

    def test_proxy_address_requires_trusted_configuration(self):
        request = APIRequestFactory().post('/', {}, HTTP_X_FORWARDED_FOR='198.51.100.10', REMOTE_ADDR='172.20.0.5')
        throttle = AuthAddressThrottle()
        with override_settings(TRUST_PROXY_ADDRESS=False):
            self.assertIn('172.20.0.5', throttle.get_cache_key(request, None))
        with override_settings(TRUST_PROXY_ADDRESS=True):
            self.assertIn('198.51.100.10', throttle.get_cache_key(request, None))
            request.META['HTTP_X_FORWARDED_FOR'] = '198.51.100.10, 192.0.2.1'
            self.assertIn('172.20.0.5', throttle.get_cache_key(request, None))
