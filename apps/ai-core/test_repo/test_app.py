"""
Test suite for the web application
"""
import unittest
from app import app


class TestApp(unittest.TestCase):
    
    def setUp(self):
        self.client = app.test_client()
    
    def test_health_check(self):
        response = self.client.get('/api/health')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['status'], 'ok')
    
    def test_get_users_empty(self):
        response = self.client.get('/api/users')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['users'], [])
    
    def test_create_user_invalid_email(self):
        response = self.client.post('/api/users', json={
            'email': 'invalid',
            'password': 'secret'
        })
        self.assertEqual(response.status_code, 400)


if __name__ == '__main__':
    unittest.main()
