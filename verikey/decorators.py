from functools import wraps
from flask import request, current_app
import jwt
from verikey.models import User

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(' ')[1]
            except IndexError:
                current_app.logger.warning("Invalid Authorization header format")
                return {'error': 'Invalid authorization header format. Use: Bearer <token>'}, 401
        
        if not token:
            current_app.logger.warning("Access attempt without token")
            return {'error': 'Authentication token is required'}, 401
        
        try:
            data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            
            # Check token type (should be access token)
            if data.get('type') != 'access':
                current_app.logger.warning("Attempt to use non-access token for authentication")
                return {'error': 'Invalid token type'}, 401
            
            current_user_id = data['user_id']
            
            current_user = User.query.get(current_user_id)
            if not current_user:
                current_app.logger.warning(f"Token valid but user {current_user_id} no longer exists")
                return {'error': 'User no longer exists'}, 401
            
            if not current_user.is_active:
                current_app.logger.warning(f"Token valid but user {current_user_id} is inactive")
                return {'error': 'User account is inactive'}, 401
            
            current_app.logger.debug(f"Authenticated request from user {current_user_id}")
            
        except jwt.ExpiredSignatureError:
            current_app.logger.warning("Access attempt with expired token")
            return {'error': 'Token has expired. Please refresh your token.'}, 401
        except jwt.InvalidTokenError as e:
            current_app.logger.warning(f"Access attempt with invalid token: {str(e)}")
            return {'error': 'Invalid token. Please login again.'}, 401
        except Exception as e:
            current_app.logger.error(f"Token validation error: {str(e)}")
            return {'error': 'Token validation failed'}, 401
        
        return f(current_user_id, *args, **kwargs)
    
    return decorated

def csrf_required(f):
    """Decorator to require CSRF token for specific endpoints"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_app.config.get('WTF_CSRF_ENABLED', True):
            from flask_wtf.csrf import validate_csrf
            try:
                # Check for CSRF token in headers or form data
                csrf_token = request.headers.get('X-CSRF-Token') or \
                           request.form.get('csrf_token') or \
                           (request.json and request.json.get('csrf_token'))
                
                if not csrf_token:
                    return {'error': 'CSRF token is missing'}, 400
                
                validate_csrf(csrf_token)
            except Exception as e:
                current_app.logger.warning(f"CSRF validation failed: {str(e)}")
                return {'error': 'Invalid CSRF token'}, 400
        
        return f(*args, **kwargs)
    
    return decorated