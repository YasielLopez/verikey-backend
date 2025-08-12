from datetime import datetime, timezone, date
import json
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password = db.Column(db.String(128), nullable=False)
    
    screen_name = db.Column(db.String(80), unique=True, nullable=False, index=True)
    last_screen_name_change = db.Column(db.DateTime, nullable=True)
    
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)   
    date_of_birth = db.Column(db.Date, nullable=False) 
    
    is_verified = db.Column(db.Boolean, default=False, index=True)
    verified_first_name = db.Column(db.String(80), nullable=True)
    verified_last_name = db.Column(db.String(80), nullable=True)
    verified_date_of_birth = db.Column(db.Date, nullable=True)
    verified_at = db.Column(db.DateTime, nullable=True)
    verification_level = db.Column(db.String(20), nullable=True)
    verification_method = db.Column(db.String(80), nullable=True)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    last_login = db.Column(db.DateTime, nullable=True)
    profile_image_url = db.Column(db.String(500), nullable=True)
    
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    deleted_at = db.Column(db.DateTime, nullable=True)
    deletion_reason = db.Column(db.String(255), nullable=True)
    
    sent_requests = db.relationship('Request', foreign_keys='Request.requester_id', 
        backref='requester', cascade='all, delete-orphan')
    received_requests = db.relationship('Request', foreign_keys='Request.target_user_id', 
        backref='target_user', cascade='all, delete-orphan')
    created_keys = db.relationship('ShareableKey', foreign_keys='ShareableKey.creator_id',
        backref='creator', cascade='all, delete-orphan')
    received_keys = db.relationship('ShareableKey', foreign_keys='ShareableKey.recipient_user_id',
        backref='recipient', cascade='all, delete-orphan')
    kyc_verifications = db.relationship('KYCVerification', backref='user', cascade='all, delete-orphan')
    
    __table_args__ = (
        db.Index('idx_user_email_active', 'email', 'is_active'),
        db.Index('idx_user_screen_name_active', 'screen_name', 'is_active'),
    )
    
    def __setattr__(self, name, value):
        protected_fields = ['first_name', 'last_name', 'date_of_birth']
        
        if name in protected_fields:
            if hasattr(self, '_sa_instance_state') and self._sa_instance_state.has_identity:
                if not getattr(self, '_allow_verification_update', False):
                    current_value = getattr(self, name, None)
                    if current_value is not None and current_value != value:
                        raise ValueError(
                            f"Cannot modify {name} after account creation. "
                            f"This field can only be updated through the verification process."
                        )
        
        super().__setattr__(name, value)
    
    def update_verified_info(self, first_name=None, last_name=None, date_of_birth=None,
                           verification_level=None, verification_method=None):
        self._allow_verification_update = True
        
        try:
            if first_name is not None:
                self.verified_first_name = first_name
            if last_name is not None:
                self.verified_last_name = last_name
            if date_of_birth is not None:
                self.verified_date_of_birth = date_of_birth
            
            self.is_verified = True
            self.verified_at = datetime.now(timezone.utc)
            
            if verification_level:
                self.verification_level = verification_level
            if verification_method:
                self.verification_method = verification_method
        finally:
            self._allow_verification_update = False
    
    def update_screen_name(self, new_screen_name):
        if not self.can_change_screen_name():
            raise ValueError("Screen name can only be changed once every 6 months")
        
        self.screen_name = new_screen_name
        self.last_screen_name_change = datetime.now(timezone.utc)
    
    @property
    def age(self):
        if self.is_verified and self.verified_date_of_birth:
            dob = self.verified_date_of_birth
        else:
            dob = self.date_of_birth
            
        if not dob:
            return None
            
        today = date.today()
        age = today.year - dob.year
        if today.month < dob.month or (today.month == dob.month and today.day < dob.day):
            age -= 1
        return age
    
    @property
    def display_first_name(self):
        if self.is_verified and self.verified_first_name:
            return self.verified_first_name
        return self.first_name
    
    @property
    def display_last_name(self):
        if self.is_verified and self.verified_last_name:
            return self.verified_last_name
        return self.last_name
    
    @property
    def display_full_name(self):
        return f"{self.display_first_name} {self.display_last_name}"
    
    def can_change_screen_name(self):
        if not self.last_screen_name_change:
            return True
        
        months_since_change = (datetime.now(timezone.utc) - self.last_screen_name_change).days / 30
        return months_since_change >= 6
    
    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'screen_name': self.screen_name,
            'first_name': self.display_first_name,
            'last_name': self.display_last_name,
            'full_name': self.display_full_name,
            'age': self.age,
            'date_of_birth': self.date_of_birth.isoformat() if self.date_of_birth else None,
            'is_verified': self.is_verified,
            'verified_first_name': self.verified_first_name,
            'verified_last_name': self.verified_last_name,
            'verified_date_of_birth': self.verified_date_of_birth.isoformat() if self.verified_date_of_birth else None,
            'verified_at': self.verified_at.isoformat() if self.verified_at else None,
            'verification_level': self.verification_level,
            'verification_method': self.verification_method,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'profile_image_url': self.profile_image_url,
            'can_change_screen_name': self.can_change_screen_name(),
            'last_screen_name_change': self.last_screen_name_change.isoformat() if self.last_screen_name_change else None,
            'profile_completed': True
        }
    
    @classmethod
    def get_active(cls, user_id):
        return cls.query.filter_by(id=user_id, is_active=True).first()
    
    @classmethod
    def find_by_email(cls, email):
        return cls.query.filter_by(email=email, is_active=True).first()
    
    @classmethod
    def find_by_screen_name(cls, screen_name):
        return cls.query.filter_by(screen_name=screen_name, is_active=True).first()


class Request(db.Model):
    __tablename__ = 'requests'
    
    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    target_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    target_email = db.Column(db.String(120), nullable=False, index=True)
    label = db.Column(db.String(120), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='pending', index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    response_at = db.Column(db.DateTime, nullable=True)
    information_types = db.Column(db.Text, nullable=True)
    
    __table_args__ = (
        db.Index('idx_request_requester_status', 'requester_id', 'status'),
        db.Index('idx_request_target_status', 'target_user_id', 'status'),
    )
    
    def set_information_types(self, info_types):
        self.information_types = json.dumps(info_types)
    
    def get_information_types(self):
        try:
            return json.loads(self.information_types) if self.information_types else []
        except json.JSONDecodeError:
            return []


class ShareableKey(db.Model):
    __tablename__ = 'shareable_keys'
    
    id = db.Column(db.Integer, primary_key=True)
    key_uuid = db.Column(db.String(36), unique=True, nullable=False, index=True)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    recipient_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    recipient_email = db.Column(db.String(120), nullable=True, index=True)
    label = db.Column(db.String(120), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='active', index=True)
    views_allowed = db.Column(db.Integer, default=1)
    views_used = db.Column(db.Integer, default=0)
    is_shareable_link = db.Column(db.Boolean, default=False)
    information_types = db.Column(db.Text, nullable=True)
    user_data = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    last_viewed_at = db.Column(db.DateTime, nullable=True)
    
    __table_args__ = (
        db.Index('idx_key_creator_status', 'creator_id', 'status'),
        db.Index('idx_key_recipient_status', 'recipient_user_id', 'status'),
    )
    
    def set_information_types(self, info_types):
        self.information_types = json.dumps(info_types)
    
    def get_information_types(self):
        try:
            return json.loads(self.information_types) if self.information_types else []
        except json.JSONDecodeError:
            return []
    
    def set_user_data(self, data_dict):
        self.user_data = json.dumps(data_dict)
    
    def get_user_data(self):
        try:
            return json.loads(self.user_data) if self.user_data else {}
        except json.JSONDecodeError:
            return {}
    
    def to_dict(self, include_user_data=False):
        result = {
            'id': self.id,
            'uuid': self.key_uuid,
            'label': self.label,
            'notes': self.notes,
            'status': self.status,
            'views_allowed': self.views_allowed,
            'views_used': self.views_used,
            'is_shareable_link': self.is_shareable_link,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_viewed_at': self.last_viewed_at.isoformat() if self.last_viewed_at else None,
            'information_types': self.get_information_types()
        }
        
        if include_user_data:
            result['user_data'] = self.get_user_data()
        
        return result


class KYCVerification(db.Model):
    __tablename__ = 'kyc_verifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    verification_id = db.Column(db.String(36), unique=True, nullable=False, index=True)
    document_type = db.Column(db.String(50), nullable=False)
    id_front_url = db.Column(db.String(500), nullable=True)
    id_back_url = db.Column(db.String(500), nullable=True)
    selfie_url = db.Column(db.String(500), nullable=True)
    manual_data = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='pending', index=True)
    reviewer_notes = db.Column(db.Text, nullable=True)
    reviewed_by = db.Column(db.Integer, nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), 
                          onupdate=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime, nullable=True)
    
    __table_args__ = (
        db.Index('idx_kyc_user_status', 'user_id', 'status'),
    )
    
    def __repr__(self):
        return f'<KYCVerification {self.verification_id}: {self.status}>'
    
    def get_manual_data(self):
        if self.manual_data:
            try:
                return json.loads(self.manual_data)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_manual_data(self, data_dict):
        self.manual_data = json.dumps(data_dict) if data_dict else None
    
    def to_dict(self, include_sensitive=False):
        result = {
            'id': self.id,
            'verification_id': self.verification_id,
            'document_type': self.document_type,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'manual_data': self.get_manual_data(),
        }
        
        if include_sensitive:
            result.update({
                'id_front_url': self.id_front_url,
                'id_back_url': self.id_back_url,
                'selfie_url': self.selfie_url,
                'reviewer_notes': self.reviewer_notes,
                'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
            })
        
        return result