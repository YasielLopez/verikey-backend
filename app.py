from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
import os
import logging
from datetime import datetime, timezone
import traceback

load_dotenv()

# Create Flask app
app = Flask(__name__)

CORS(app, origins=[
    "http://localhost:3000",
    "http://localhost:19000",
    "http://10.0.0.176:19000",
    "exp://10.0.0.176:19000",
], supports_credentials=True)

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['JWT_EXPIRATION_HOURS'] = 24

# Initialize database
from verikey.models import db
db.init_app(app)

# Import and create tables
with app.app_context():
    try:
        from verikey.models import User, Request, ShareableKey, KYCVerification
        db.create_all()
        print("✅ Database tables created")
    except Exception as e:
        print(f"❌ Database error: {e}")
        traceback.print_exc()

# Register blueprints
try:
    from verikey.auth import auth_bp
    from verikey.verification import verification_bp
    from verikey.profile import profile_bp
    from verikey.keys import keys_bp
    from verikey.kyc import kyc_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(verification_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(keys_bp)
    app.register_blueprint(kyc_bp)
    
    print("✅ All blueprints registered")
except Exception as e:
    print(f"❌ Blueprint error: {e}")
    traceback.print_exc()

@app.route('/users/lookup', methods=['POST'])
def lookup_user():
    """Look up a user by email or username"""
    from flask import request, jsonify
    from verikey.models import User, db
    from verikey.decorators import token_required
    import jwt
    
    token = None
    if 'Authorization' in request.headers:
        auth_header = request.headers['Authorization']
        try:
            token = auth_header.split(' ')[1]
        except IndexError:
            return jsonify({'error': 'Invalid authorization header format'}), 401
    
    if not token:
        return jsonify({'error': 'Authentication token is required'}), 401
    
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        current_user_id = data['user_id']
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'Token has expired'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'error': 'Invalid token'}), 401
    
    # Get request data
    request_data = request.get_json()
    identifier = request_data.get('identifier', '').strip()
    
    if not identifier:
        return jsonify({'error': 'Identifier is required'}), 400
    
    print(f"🔍 Looking up user: {identifier}")
    
    # Look up user
    user = None
    if identifier.startswith('@'):
        # Username lookup
        clean_identifier = identifier[1:].lower()
        user = User.query.filter(
            db.and_(
                User.id != current_user_id,
                User.screen_name == clean_identifier,
                User.is_active == True
            )
        ).first()
    else:
        # Email lookup
        user = User.query.filter(
            db.and_(
                User.id != current_user_id,
                User.email == identifier.lower(),
                User.is_active == True
            )
        ).first()
    
    if not user:
        print(f"❌ User not found: {identifier}")
        return jsonify({'error': 'User not found'}), 404
    
    print(f"✅ Found user: {user.screen_name or user.email}")
    
    return jsonify({
        'user': {
            'id': user.id,
            'email': user.email,
            'screen_name': user.screen_name,
            'display_name': f"@{user.screen_name}" if user.screen_name else user.email,
            'profile_image_url': user.profile_image_url,
            'is_verified': user.is_verified or False
        }
    }), 200

@app.route('/')
def home():
    return jsonify({'message': 'Verikey API is running', 'status': 'healthy'})

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    print("🚀 Starting Verikey API...")
    app.run(debug=True, host='0.0.0.0', port=5000)