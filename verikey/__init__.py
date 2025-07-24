from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from dotenv import load_dotenv
import os
import bcrypt

# Load environment variables
load_dotenv()

# Initialize SQLAlchemy
db = SQLAlchemy()

def init_app():
    app = Flask(__name__)
    CORS(app)
    
    # Database configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize database with app
    db.init_app(app)
    
    # Import models AFTER db is initialized
    from verikey.models import User, Request, Verification
    
    # Create tables
    with app.app_context():
        db.create_all()

    @app.route('/')
    def home():
        return {'message': 'Verikey API is running'}

    @app.route('/signup', methods=['POST'])
    def signup():
        try:
            # Get data from request
            data = request.get_json()
            
            if not data or not data.get('email') or not data.get('password'):
                return {'error': 'Email and password are required'}, 400
            
            email = data['email'].lower().strip()
            password = data['password']
            
            # Check if user already exists
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                return {'error': 'User with this email already exists'}, 400
            
            # Hash password
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            # Create new user
            new_user = User(email=email, password_hash=password_hash)
            db.session.add(new_user)
            db.session.commit()
            
            return {'message': 'User created successfully', 'user_id': new_user.id}, 201
            
        except Exception as e:
            db.session.rollback()
            return {'error': f'Signup failed: {str(e)}'}, 500
        
    @app.route('/login', methods=['POST'])
    def login():
        try:
            # Get data from request
            data = request.get_json()
            
            if not data or not data.get('email') or not data.get('password'):
                return {'error': 'Email and password are required'}, 400
            
            email = data['email'].lower().strip()
            password = data['password']
            
            # Find user by email
            user = User.query.filter_by(email=email).first()
            if not user:
                return {'error': 'Invalid email or password'}, 401
            
            # Check password
            if bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
                return {
                    'message': 'Login successful',
                    'user': {
                        'id': user.id,
                        'email': user.email
                    }
                }, 200
            else:
                return {'error': 'Invalid email or password'}, 401
                
        except Exception as e:
            return {'error': f'Login failed: {str(e)}'}, 500

    @app.route('/test-db')
    def test_db():
        try:
            with db.engine.connect() as connection:
                result = connection.execute(text('SELECT 1'))
                return {'message': 'Database connection successful!', 'status': 'connected'}
        except Exception as e:
            return {'message': 'Database connection failed', 'error': str(e)}, 500

    @app.route('/users')
    def list_users():
        try:
            users = User.query.all()
            user_list = [{'id': user.id, 'email': user.email, 'created_at': user.created_at.isoformat()} for user in users]
            return {'users': user_list}
        except Exception as e:
            return {'error': str(e)}, 500    
    

    return app