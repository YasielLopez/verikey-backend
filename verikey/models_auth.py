from datetime import datetime, timezone, timedelta
from verikey.models import db
import secrets

class RefreshToken(db.Model):
    __tablename__ = 'refresh_tokens'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    token = db.Column(db.String(256), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    revoked = db.Column(db.Boolean, default=False)
    device_info = db.Column(db.String(256), nullable=True)  # Optional: track device/browser
    
    __table_args__ = (
        db.Index('idx_refresh_token_user', 'user_id', 'revoked'),
        db.Index('idx_refresh_token_expires', 'expires_at', 'revoked'),
    )
    
    @classmethod
    def generate_token(cls):
        """Generate a secure random token"""
        return secrets.token_urlsafe(32)
    
    @classmethod
    def create_token(cls, user_id, device_info=None, expires_in_seconds=None):
        """Create a new refresh token for a user"""
        if expires_in_seconds is None:
            expires_in_seconds = 604800  # 7 days default
            
        token_string = cls.generate_token()
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)
        
        refresh_token = cls(
            user_id=user_id,
            token=token_string,
            expires_at=expires_at,
            device_info=device_info
        )
        
        db.session.add(refresh_token)
        db.session.commit()
        
        return token_string
    
    @classmethod
    def verify_token(cls, token_string):
        """Verify a refresh token and return the associated user_id"""
        refresh_token = cls.query.filter_by(
            token=token_string,
            revoked=False
        ).first()
        
        if not refresh_token:
            return None
            
        if refresh_token.expires_at < datetime.now(timezone.utc):
            # Token is expired
            refresh_token.revoked = True
            db.session.commit()
            return None
            
        return refresh_token.user_id
    
    @classmethod
    def revoke_token(cls, token_string):
        """Revoke a specific refresh token"""
        refresh_token = cls.query.filter_by(token=token_string).first()
        if refresh_token:
            refresh_token.revoked = True
            db.session.commit()
            return True
        return False
    
    @classmethod
    def revoke_all_user_tokens(cls, user_id):
        """Revoke all refresh tokens for a user"""
        cls.query.filter_by(user_id=user_id).update({'revoked': True})
        db.session.commit()
    
    @classmethod
    def cleanup_expired_tokens(cls):
        """Remove expired and revoked tokens (run periodically)"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)
        cls.query.filter(
            db.or_(
                cls.expires_at < datetime.now(timezone.utc),
                db.and_(cls.revoked == True, cls.created_at < cutoff_date)
            )
        ).delete()
        db.session.commit()