#!/usr/bin/env python3
"""Utility functions for the web application"""
import hashlib
from datetime import datetime


def hash_password(password: str) -> str:
    """Hash a password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()


def format_timestamp(dt: datetime = None) -> str:
    """Format datetime to ISO string"""
    if dt is None:
        dt = datetime.utcnow()
    return dt.isoformat()


def validate_email(email: str) -> bool:
    """Basic email validation"""
    return '@' in email and '.' in email.split('@')[1]


def sanitize_input(text: str) -> str:
    """Remove potentially dangerous characters"""
    return text.replace('<', '').replace('>', '').strip()
