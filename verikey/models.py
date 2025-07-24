from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from verikey import db

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # NEW: Profile fields
    first_name = db.Column(db.String(50), nullable=True)
    last_name = db.Column(db.String(50), nullable=True)
    screen_name = db.Column(db.String(30), unique=True, nullable=True)  # @username style
    profile_image_url = db.Column(db.String(500), nullable=True)
    profile_completed = db.Column(db.Boolean, default=False)  # Track if profile is set up
    profile_updated_at = db.Column(db.DateTime, nullable=True)
    
    def __repr__(self):
        return f'<User {self.email}>'
    
    def to_dict(self, include_sensitive=False):
        """Convert user to dictionary for API responses"""
        user_dict = {
            'id': self.id,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'screen_name': self.screen_name,
            'profile_image_url': self.profile_image_url,
            'profile_completed': self.profile_completed,
            'created_at': self.created_at.isoformat(),
            'profile_updated_at': self.profile_updated_at.isoformat() if self.profile_updated_at else None
        }
        
        if include_sensitive:
            user_dict['password_hash'] = self.password_hash
            
        return user_dict

class Request(db.Model):
    __tablename__ = 'requests'
    
    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    target_email = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, completed, denied
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    requester = db.relationship('User', backref='sent_requests', foreign_keys=[requester_id])
    
    def __repr__(self):
        return f'<Request {self.id}: {self.requester_id} -> {self.target_email}>'

class Verification(db.Model):
    __tablename__ = 'verifications'
    
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey('requests.id'), nullable=False)
    photo_url = db.Column(db.String(500), nullable=False)
    latitude = db.Column(db.Numeric(10, 8), nullable=False)
    longitude = db.Column(db.Numeric(11, 8), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    request = db.relationship('Request', backref='verification')
    
    def __repr__(self):
        return f'<Verification {self.id} for Request {self.request_id}>'