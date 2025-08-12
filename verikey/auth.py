import email
from flask import Blueprint, request, jsonify, current_app
from werkzeug.exceptions import BadRequest
from functools import wraps
import bcrypt
import jwt
import re
from datetime import datetime, timedelta, timezone, date
from verikey.models import db
from verikey.models import User
from verikey.decorators import token_required

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password):
    if len(password) < 6:
        return False, "Password must be at least 6 characters long"
    return True, "Valid"

def validate_screen_name(screen_name):
    if not screen_name:
        return False, "Screen name is required"
    
    clean_name = screen_name.lstrip('@').lower()
    
    if len(clean_name) < 3 or len(clean_name) > 30:
        return False, "Screen name must be between 3 and 30 characters"
    
    username_regex = re.compile(r'^[a-zA-Z0-9_.]+$')
    if not username_regex.match(clean_name):
        return False, "Screen name can only contain letters, numbers, underscores, and dots"
    
    return True, clean_name

def generate_jwt_token(user_id):
    try:
        payload = {
            'user_id': user_id,
            'exp': datetime.now(timezone.utc) + timedelta(hours=current_app.config['JWT_EXPIRATION_HOURS']),
            'iat': datetime.now(timezone.utc)
        }
        token = jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')
        return token
    except Exception as e:
        current_app.logger.error(f"JWT token generation failed: {str(e)}")
        return None

@auth_bp.route('/signup', methods=['POST'])
def signup():
    try:
        if not request.is_json:
            current_app.logger.warning("Signup attempt without JSON data")
            return {'error': 'Request must be JSON'}, 400
        
        data = request.get_json()
        
        if not data:
            return {'error': 'No data provided'}, 400
        
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        screen_name = data.get('screen_name', '').strip()
        date_of_birth_str = data.get('date_of_birth', '')
        
        errors = []
        
        if not email:
            errors.append('Email is required')
        elif not validate_email(email):
            errors.append('Invalid email format')
        
        if not password:
            errors.append('Password is required')
        else:
            is_valid, message = validate_password(password)
            if not is_valid:
                errors.append(message)
        
        if not first_name:
            errors.append('First name is required')
        elif len(first_name) < 2 or len(first_name) > 50:
            errors.append('First name must be between 2 and 50 characters')
        
        if not last_name:
            errors.append('Last name is required')
        elif len(last_name) < 2 or len(last_name) > 50:
            errors.append('Last name must be between 2 and 50 characters')
        
        if not screen_name:
            errors.append('Username is required')
        else:
            is_valid, clean_screen_name = validate_screen_name(screen_name)
            if not is_valid:
                errors.append(clean_screen_name)
            else:
                screen_name = clean_screen_name
        
        date_of_birth = None
        age = None
        if not date_of_birth_str:
            errors.append('Date of birth is required')
        else:
            try:
                month, day, year = date_of_birth_str.split('/')
                date_of_birth = date(int(year), int(month), int(day))
                
                today = date.today()
                age = today.year - date_of_birth.year
                if today.month < date_of_birth.month or (today.month == date_of_birth.month and today.day < date_of_birth.day):
                    age -= 1
                
                if age < 18:
                    errors.append('You must be at least 18 years old to use Verikey')
                elif age > 120:
                    errors.append('Please enter a valid date of birth')
                    
            except (ValueError, TypeError):
                errors.append('Invalid date of birth format. Please use MM/DD/YYYY')
        
        if errors:
            current_app.logger.warning(f"Signup validation failed: {errors}")
            return {'error': 'Validation failed', 'errors': errors}, 400
        
        db.session.begin()
        try:
            existing_email = User.query.filter_by(email=email, is_active=True).first()
            if existing_email:
                db.session.rollback()
                current_app.logger.warning(f"Signup attempt with existing email: {email}")
                return {'error': 'An account with this email already exists'}, 409
            
            existing_screen_name = User.query.filter_by(screen_name=screen_name, is_active=True).first()
            if existing_screen_name:
                db.session.rollback()
                current_app.logger.warning(f"Signup attempt with existing screen_name: {screen_name}")
                return {'error': 'This username is already taken. Please choose another.'}, 409
            
            try:
                password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Password hashing failed: {str(e)}")
                return {'error': 'Password processing failed'}, 500
            
            new_user = User(
                email=email,
                password=password_hash,
                first_name=first_name,
                last_name=last_name,
                screen_name=screen_name,
                date_of_birth=date_of_birth
            )
            
            db.session.add(new_user)
            db.session.commit()
            
            token = generate_jwt_token(new_user.id)
            if not token:
                current_app.logger.error(f"User {new_user.id} created but token generation failed")
                return {'error': 'Account created but login failed. Please try logging in.'}, 500
            
            current_app.logger.info(f"✅ New user created with complete profile: {new_user.id} ({email}, @{screen_name})")
            
            return {
                'message': 'Account created successfully',
                'token': token,
                'user': new_user.to_dict()
            }, 201
            
        except Exception as e:
            db.session.rollback()
            raise e
            
    except Exception as e:
        current_app.logger.error(f"Signup failed: {str(e)}")
        return {'error': 'Account creation failed. Please try again.'}, 500

@auth_bp.route('/check-username', methods=['POST'])
def check_username():
    try:
        data = request.get_json()
        screen_name = data.get('screen_name', '').strip()
        
        if not screen_name:
            return {'available': False, 'error': 'Username is required'}, 400
        
        is_valid, clean_screen_name = validate_screen_name(screen_name)
        if not is_valid:
            return {'available': False, 'error': clean_screen_name}, 400
        
        existing = User.query.filter_by(screen_name=clean_screen_name, is_active=True).first()
        
        if existing:
            return {'available': False, 'error': 'Username already taken'}, 200
        
        return {'available': True, 'screen_name': clean_screen_name}, 200
        
    except Exception as e:
        current_app.logger.error(f"Username check failed: {str(e)}")
        return {'error': 'Failed to check username'}, 500

@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        if not request.is_json:
            current_app.logger.warning("Login attempt without JSON data")
            return {'error': 'Request must be JSON'}, 400
        
        data = request.get_json()
        
        if not data:
            return {'error': 'No data provided'}, 400
        
        login_identifier = data.get('email', '').strip()
        password = data.get('password', '')
        
        if not login_identifier or not password:
            current_app.logger.warning(f"Login attempt with missing fields: identifier={bool(login_identifier)}, password={bool(password)}")
            return {'error': 'Email/username and password are required'}, 400
        
        if login_identifier.startswith('@'):
            screen_name = login_identifier[1:].lower()
            user = User.query.filter_by(
                screen_name=screen_name,
                is_active=True
            ).first()
            current_app.logger.info(f"Login attempt with username: @{screen_name}")
        elif validate_email(login_identifier):
            email = login_identifier.lower()
            user = User.query.filter_by(
                email=email,
                is_active=True
            ).first()
            current_app.logger.info(f"Login attempt with email: {email}")
        else:
            lower_identifier = login_identifier.lower()
            user = User.query.filter(
                db.and_(
                    db.or_(
                        User.email == lower_identifier,
                        User.screen_name == lower_identifier
                    ),
                    User.is_active == True
                )
            ).first()
            current_app.logger.info(f"Login attempt with identifier: {lower_identifier}")
        
        if not user:
            current_app.logger.warning(f"Login attempt for inactive/deleted account: {login_identifier}")
            return {'error': 'Invalid email/username or password'}, 401
        
        try:
            if bcrypt.checkpw(password.encode('utf-8'), user.password.encode('utf-8')):
                token = generate_jwt_token(user.id)
                if not token:
                    current_app.logger.error(f"Login successful but token generation failed for user {user.id}")
                    return {'error': 'Login processing failed. Please try again.'}, 500
                
                user.last_login = datetime.now(timezone.utc)
                db.session.commit()
                
                current_app.logger.info(f"✅ Successful login: user {user.id} ({user.email})")
                
                return {
                    'message': 'Login successful',
                    'token': token,
                    'user': user.to_dict()
                }, 200
            else:
                current_app.logger.warning(f"Login attempt with wrong password for: {login_identifier}")
                return {'error': 'Invalid email/username or password'}, 401
        except Exception as e:
            current_app.logger.error(f"Password verification error: {str(e)}")
            return {'error': 'Login processing failed. Please try again.'}, 500
            
    except Exception as e:
        current_app.logger.error(f"Login error: {str(e)}")
        return {'error': 'Login failed. Please try again.'}, 500

@auth_bp.route('/verify', methods=['GET'])
@token_required
def verify_token(current_user_id):
    try:
        user = User.query.filter_by(id=current_user_id, is_active=True).first()
        
        if not user:
            return {'error': 'User not found or inactive'}, 404
        
        current_app.logger.info(f"Token verification successful for user {current_user_id}")
        
        return {
            'message': 'Token is valid',
            'user': user.to_dict()
        }, 200
        
    except Exception as e:
        current_app.logger.error(f"Token verification failed for user {current_user_id}: {str(e)}")
        return {'error': 'Token verification failed'}, 500

@auth_bp.route('/logout', methods=['POST'])
@token_required
def logout(current_user_id):
    try:
        current_app.logger.info(f"User {current_user_id} logged out")
        return {'message': 'Logout successful'}, 200
    except Exception as e:
        current_app.logger.error(f"Logout error for user {current_user_id}: {str(e)}")
        return {'error': 'Logout failed'}, 500

@auth_bp.route('/refresh', methods=['POST'])
def refresh_token():
    try:
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(' ')[1]
            except IndexError:
                current_app.logger.warning("Invalid Authorization header format for refresh")
                return {'error': 'Invalid authorization header format'}, 401
        
        if not token:
            current_app.logger.warning("Refresh attempt without token")
            return {'error': 'Token is required for refresh'}, 401
        
        try:
            data = jwt.decode(
                token,
                current_app.config['SECRET_KEY'],
                algorithms=['HS256'],
                options={"verify_exp": False}
            )
            current_user_id = data['user_id']
            
            current_user = User.query.filter_by(id=current_user_id, is_active=True).first()
            if not current_user:
                current_app.logger.warning(f"Refresh token valid but user {current_user_id} no longer exists or is inactive")
                return {'error': 'User no longer exists or is inactive'}, 401
            
            new_token = generate_jwt_token(current_user.id)
            if not new_token:
                current_app.logger.error(f"Failed to generate new token during refresh for user {current_user_id}")
                return {'error': 'Token refresh failed'}, 500
            
            current_app.logger.info(f"✅ Token refreshed successfully for user {current_user_id}")
            
            return {
                'message': 'Token refreshed successfully',
                'token': new_token,
                'user': current_user.to_dict()
            }, 200
            
        except jwt.InvalidTokenError as e:
            current_app.logger.warning(f"Invalid token for refresh: {str(e)}")
            return {'error': 'Invalid token for refresh'}, 401
        except Exception as e:
            current_app.logger.error(f"Token refresh validation error: {str(e)}")
            return {'error': 'Token refresh validation failed'}, 401
            
    except Exception as e:
        current_app.logger.error(f"Token refresh error: {str(e)}")
        return {'error': 'Token refresh failed'}, 500

@auth_bp.route('/users', methods=['GET'])
@token_required
def list_users(current_user_id):
    try:
        users = User.query.filter_by(is_active=True).all()
        user_list = [{
            'id': user.id,
            'email': user.email,
            'screen_name': user.screen_name,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'age': user.age,
            'created_at': user.created_at.isoformat()
        } for user in users]
        
        current_app.logger.info(f"User list requested by user {current_user_id}, returning {len(user_list)} active users")
        
        return {'users': user_list}, 200
        
    except Exception as e:
        current_app.logger.error(f"Failed to list users: {str(e)}")
        return {'error': 'Failed to retrieve users'}, 500