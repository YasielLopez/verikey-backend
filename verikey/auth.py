from flask import Blueprint, request, jsonify, current_app
from werkzeug.exceptions import BadRequest
from functools import wraps
import bcrypt
import jwt
import re
from datetime import datetime, timedelta
from verikey import db
from verikey.models import User

# Create blueprint
auth_bp = Blueprint('auth', __name__)

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password):
    """Validate password strength"""
    if len(password) < 6:
        return False, "Password must be at least 6 characters long"
    return True, "Valid"

def generate_jwt_token(user_id):
    """Generate JWT token for user"""
    try:
        payload = {
            'user_id': user_id,
            'exp': datetime.utcnow() + timedelta(hours=current_app.config['JWT_EXPIRATION_HOURS']),
            'iat': datetime.utcnow()
        }
        token = jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')
        return token
    except Exception as e:
        current_app.logger.error(f"JWT token generation failed: {str(e)}")
        return None

def token_required(f):
    """Decorator to require JWT token for protected routes"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Get token from Authorization header
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                # Expected format: "Bearer <token>"
                token = auth_header.split(' ')[1]
            except IndexError:
                current_app.logger.warning("Invalid Authorization header format")
                return {'error': 'Invalid authorization header format. Use: Bearer <token>'}, 401
        
        if not token:
            current_app.logger.warning("Access attempt without token")
            return {'error': 'Authentication token is required'}, 401
        
        try:
            # Decode JWT token
            data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user_id = data['user_id']
            
            # Verify user still exists
            current_user = User.query.get(current_user_id)
            if not current_user:
                current_app.logger.warning(f"Token valid but user {current_user_id} no longer exists")
                return {'error': 'User no longer exists'}, 401
            
            current_app.logger.debug(f"Authenticated request from user {current_user_id}")
            
        except jwt.ExpiredSignatureError:
            current_app.logger.warning("Access attempt with expired token")
            return {'error': 'Token has expired. Please login again.'}, 401
        except jwt.InvalidTokenError as e:
            current_app.logger.warning(f"Access attempt with invalid token: {str(e)}")
            return {'error': 'Invalid token. Please login again.'}, 401
        except Exception as e:
            current_app.logger.error(f"Token validation error: {str(e)}")
            return {'error': 'Token validation failed'}, 401
        
        # Pass current_user_id as first argument to the protected function
        return f(current_user_id, *args, **kwargs)
    
    return decorated

@auth_bp.route('/signup', methods=['POST'])
def signup():
    """Create a new user account"""
    try:
        # Validate request has JSON data
        if not request.is_json:
            current_app.logger.warning("Signup attempt without JSON data")
            return {'error': 'Request must be JSON'}, 400
        
        data = request.get_json()
        
        # Validate required fields
        if not data:
            return {'error': 'No data provided'}, 400
        
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        if not email or not password:
            current_app.logger.warning(f"Signup attempt with missing fields: email={bool(email)}, password={bool(password)}")
            return {'error': 'Email and password are required'}, 400
        
        # Validate email format
        if not validate_email(email):
            current_app.logger.warning(f"Signup attempt with invalid email: {email}")
            return {'error': 'Invalid email format'}, 400
        
        # Validate password strength
        is_valid, message = validate_password(password)
        if not is_valid:
            current_app.logger.warning(f"Signup attempt with weak password for email: {email}")
            return {'error': message}, 400
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            current_app.logger.warning(f"Signup attempt with existing email: {email}")
            return {'error': 'User with this email already exists'}, 409
        
        # Hash password
        try:
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        except Exception as e:
            current_app.logger.error(f"Password hashing failed: {str(e)}")
            return {'error': 'Password processing failed'}, 500
        
        # Create new user
        new_user = User(email=email, password_hash=password_hash)
        db.session.add(new_user)
        db.session.commit()
        
        # Generate JWT token for immediate login
        token = generate_jwt_token(new_user.id)
        if not token:
            # User created but token generation failed
            current_app.logger.error(f"User {new_user.id} created but token generation failed")
            return {'error': 'Account created but login failed. Please try logging in.'}, 201
        
        current_app.logger.info(f"✅ New user created and logged in: {email} (ID: {new_user.id})")
        
        return {
            'message': 'Account created successfully',
            'user': new_user.to_dict(),
            'token': token,
            'expires_in': f"{current_app.config['JWT_EXPIRATION_HOURS']} hours"
        }, 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Signup failed for email {email if 'email' in locals() else 'unknown'}: {str(e)}")
        return {'error': 'Account creation failed. Please try again.'}, 500

@auth_bp.route('/login', methods=['POST'])
def login():
    """Authenticate user login and return JWT token"""
    try:
        # Validate request has JSON data
        if not request.is_json:
            current_app.logger.warning("Login attempt without JSON data")
            return {'error': 'Request must be JSON'}, 400
        
        data = request.get_json()
        
        # Validate required fields
        if not data:
            return {'error': 'No data provided'}, 400
        
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        if not email or not password:
            current_app.logger.warning(f"Login attempt with missing fields: email={bool(email)}, password={bool(password)}")
            return {'error': 'Email and password are required'}, 400
        
        # Validate email format
        if not validate_email(email):
            current_app.logger.warning(f"Login attempt with invalid email: {email}")
            return {'error': 'Invalid email format'}, 400
        
        # Find user by email
        user = User.query.filter_by(email=email).first()
        if not user:
            current_app.logger.warning(f"Login attempt with non-existent email: {email}")
            return {'error': 'Invalid email or password'}, 401
        
        # Check password
        try:
            if bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
                # Generate JWT token
                token = generate_jwt_token(user.id)
                if not token:
                    current_app.logger.error(f"Login successful but token generation failed for user {user.id}")
                    return {'error': 'Login processing failed. Please try again.'}, 500
                
                current_app.logger.info(f"✅ Successful login with token: {email} (ID: {user.id})")
                
                return {
                    'message': 'Login successful',
                    'user': user.to_dict(),
                    'token': token,
                    'expires_in': f"{current_app.config['JWT_EXPIRATION_HOURS']} hours"
                }, 200
            else:
                current_app.logger.warning(f"Login attempt with wrong password: {email}")
                return {'error': 'Invalid email or password'}, 401
        except Exception as e:
            current_app.logger.error(f"Password verification failed for {email}: {str(e)}")
            return {'error': 'Authentication failed'}, 500
            
    except Exception as e:
        current_app.logger.error(f"Login failed for email {email if 'email' in locals() else 'unknown'}: {str(e)}")
        return {'error': 'Login failed. Please try again.'}, 500

@auth_bp.route('/verify-token', methods=['GET'])
@token_required
def verify_token(current_user_id):
    """Verify if a token is still valid and return user info"""
    try:
        user = User.query.get(current_user_id)
        if not user:
            return {'error': 'User not found'}, 404
        
        current_app.logger.info(f"Token verification successful for user {current_user_id}")
        
        return {
            'message': 'Token is valid',
            'user': user.to_dict()
        }, 200
        
    except Exception as e:
        current_app.logger.error(f"Token verification failed for user {current_user_id}: {str(e)}")
        return {'error': 'Token verification failed'}, 500

@auth_bp.route('/users', methods=['GET'])
@token_required
def list_users(current_user_id):
    """Debug route to list all users (protected, remove in production)"""
    try:
        users = User.query.all()
        user_list = [{
            'id': user.id, 
            'email': user.email, 
            'created_at': user.created_at.isoformat()
        } for user in users]
        
        current_app.logger.info(f"User list requested by user {current_user_id}, returning {len(user_list)} users")
        return {'users': user_list}
        
    except Exception as e:
        current_app.logger.error(f"Failed to list users: {str(e)}")
        return {'error': 'Failed to retrieve users'}, 500