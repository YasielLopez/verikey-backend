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
            current_user_id = data['user_id']
            
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
        
        return f(current_user_id, *args, **kwargs)
    
    return decorated