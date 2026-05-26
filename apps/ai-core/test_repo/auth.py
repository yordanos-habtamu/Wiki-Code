#!/usr/bin/env python3
"""Authentication module with JWT support"""
import jwt
from datetime import datetime, timedelta
from utils import hash_password


class AuthService:
    """Handle user authentication and token management"""
    
    SECRET_KEY = "your-secret-key-here"
    TOKEN_EXPIRY_HOURS = 24
    
    def __init__(self):
        self.blacklisted_tokens = set()
    
    def generate_token(self, user_id: str, email: str) -> str:
        """Generate JWT token for authenticated user"""
        payload = {
            'user_id': user_id,
            'email': email,
            'exp': datetime.utcnow() + timedelta(hours=self.TOKEN_EXPIRY_HOURS),
            'iat': datetime.utcnow()
        }
        
        token = jwt.encode(payload, self.SECRET_KEY, algorithm='HS256')
        return token
    
    def verify_token(self, token: str) -> dict:
        """Verify and decode JWT token"""
        if token in self.blacklisted_tokens:
            raise ValueError("Token has been revoked")
        
        try:
            payload = jwt.decode(token, self.SECRET_KEY, algorithms=['HS256'])
            return payload
        except jwt.ExpiredSignatureError:
            raise ValueError("Token has expired")
        except jwt.InvalidTokenError:
            raise ValueError("Invalid token")
    
    def revoke_token(self, token: str):
        """Blacklist a token"""
        self.blacklisted_tokens.add(token)
    
    def authenticate_user(self, email: str, password: str, users_db: list) -> dict:
        """Authenticate user with email and password"""
        for user in users_db:
            if user['email'] == email:
                if user['password_hash'] == hash_password(password):
                    return {
                        'user_id': user.get('id', 'unknown'),
                        'email': user['email']
                    }
        raise ValueError("Invalid credentials")
