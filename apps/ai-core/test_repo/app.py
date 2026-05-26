#!/usr/bin/env python3
"""Sample web application for testing Git Extraction Engine"""
from flask import Flask, jsonify, request
from utils import hash_password, validate_email, sanitize_input

app = Flask(__name__)

# In-memory user storage
users_db = []

@app.route('/api/users', methods=['GET', 'POST'])
def get_users():
    if request.method == 'POST':
        data = request.json
        email = sanitize_input(data.get('email', ''))
        
        if not validate_email(email):
            return jsonify({"error": "Invalid email"}), 400
        
        user = {
            "email": email,
            "password_hash": hash_password(data.get('password', '')),
            "created_at": datetime.utcnow().isoformat()
        }
        users_db.append(user)
        return jsonify(user), 201
    
    return jsonify({"users": users_db})

@app.route('/api/health')
def health_check():
    return jsonify({"status": "ok", "users_count": len(users_db)})

if __name__ == '__main__':
    app.run(debug=True)
