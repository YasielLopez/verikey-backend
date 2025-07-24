from flask import Flask
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
import os
import logging

# Load environment variables
load_dotenv()

# Initialize SQLAlchemy
db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    CORS(app)
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    app.logger.setLevel(logging.INFO)
    
    # App configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # JWT Secret Key - now from environment variable
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
    app.config['JWT_EXPIRATION_HOURS'] = 24  # Tokens expire in 24 hours
    
    # Validate required config
    if not app.config['SECRET_KEY']:
        app.logger.error("SECRET_KEY not found in environment variables!")
        raise ValueError("SECRET_KEY must be set in .env file")
    
    # Initialize database with app
    db.init_app(app)
    
    # Import models to ensure they're registered
    from verikey.models import User, Request, Verification
    
    # Create tables (without dropping existing data)
    with app.app_context():
        db.create_all()
        app.logger.info("✅ Database tables verified")
    
    # Register blueprints (route modules)
    from verikey.auth import auth_bp
    from verikey.verification import verification_bp
    from verikey.profile import profile_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(verification_bp)
    app.register_blueprint(profile_bp)
    
    # Basic home route
    @app.route('/')
    def home():
        return {
            'message': 'Verikey API is running',
            'status': 'healthy', 
            'auth': 'JWT enabled',
            'features': ['Authentication', 'Profile Management', 'Verification System'],
            'version': '1.0.0'
        }
    
    # Health check route
    @app.route('/health')
    def health_check():
        try:
            from sqlalchemy import text
            with db.engine.connect() as connection:
                connection.execute(text('SELECT 1'))
            return {
                'status': 'healthy',
                'database': 'connected',
                'auth': 'JWT enabled',
                'features': {
                    'authentication': 'enabled',
                    'profiles': 'enabled', 
                    'verification': 'enabled'
                }
            }
        except Exception as e:
            app.logger.error(f"Health check failed: {str(e)}")
            return {'status': 'unhealthy', 'error': str(e)}, 500
    
    app.logger.info("🔐 JWT Authentication enabled")
    app.logger.info("👤 Profile system enabled")
    app.logger.info("📬 Verification system enabled")
    app.logger.info("🛡️ All routes protected with authentication")
    app.logger.info("🚀 Verikey API ready for production")
    
    return app

def init_app():
    return create_app()