from flask import Blueprint, request, jsonify, current_app
from verikey.models import db
from verikey.models import User, ShareableKey, Request, KYCVerification
from verikey.decorators import token_required
from datetime import datetime, timezone, timedelta
import bcrypt
import uuid
import re

profile_bp = Blueprint('profile', __name__)

@profile_bp.route('/profile', methods=['GET'])
@token_required
def get_profile(current_user_id):
    try:
        user = User.query.get(current_user_id)
        if not user:
            return {'error': 'User not found'}, 404
        
        return {
            'profile': user.to_dict()
        }, 200
    except Exception as e:
        current_app.logger.error(f"Get profile failed for user {current_user_id}: {str(e)}")
        return {'error': 'Failed to get profile'}, 500

@profile_bp.route('/profile', methods=['POST'])
@token_required
def update_profile(current_user_id):
    try:
        user = User.query.get(current_user_id)
        if not user:
            return {'error': 'User not found'}, 404
        
        data = request.get_json()
        
        immutable_fields = ['first_name', 'last_name', 'date_of_birth', 'age']
        attempted_changes = []
        
        for field in immutable_fields:
            if field in data:
                attempted_changes.append(field)
        
        if attempted_changes and not user.is_verified:
            current_app.logger.warning(f"User {current_user_id} attempted to change immutable fields: {attempted_changes}")
            return {
                'error': f"Cannot change {', '.join(attempted_changes)}. These fields can only be updated through identity verification.",
                'attempted_fields': attempted_changes
            }, 403
        
        if 'email' in data:
            new_email = data['email'].strip().lower() if data['email'] else None
            if new_email and new_email != user.email:
                existing = User.query.filter(
                    User.email == new_email,
                    User.id != current_user_id,
                    User.is_active == True
                ).first()
                if existing:
                    return {'error': 'Email already taken'}, 400
                
                email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                if not re.match(email_pattern, new_email):
                    return {'error': 'Invalid email format'}, 400
                
                user.email = new_email
        
        if 'screen_name' in data:
            new_screen_name = data['screen_name'].strip() if data['screen_name'] else None
            if new_screen_name:
                new_screen_name = new_screen_name.lstrip('@').lower()
                
                if new_screen_name != user.screen_name:
                    if not user.can_change_screen_name():
                        return {
                            'error': 'You can only change your username once every 6 months',
                            'last_change': user.last_screen_name_change.isoformat() if user.last_screen_name_change else None,
                            'next_available': (user.last_screen_name_change + timedelta(days=180)).isoformat() if user.last_screen_name_change else None
                        }, 403
                    
                    existing = User.query.filter(
                        User.screen_name == new_screen_name,
                        User.id != current_user_id,
                        User.is_active == True
                    ).first()
                    if existing:
                        return {'error': 'Username already taken'}, 400
                    
                    if len(new_screen_name) < 3 or len(new_screen_name) > 30:
                        return {'error': 'Username must be between 3 and 30 characters'}, 400
                    
                    username_regex = re.compile(r'^[a-zA-Z0-9_.]+$')
                    if not username_regex.match(new_screen_name):
                        return {'error': 'Username can only contain letters, numbers, underscores, and dots'}, 400
                    
                    user.screen_name = new_screen_name
                    user.last_screen_name_change = datetime.now(timezone.utc)
                    current_app.logger.info(f"User {current_user_id} changed screen name to @{new_screen_name}")
        
        if 'profile_image_url' in data:
            user.profile_image_url = data['profile_image_url']
        
        if 'bio' in data:
            user.bio = data['bio'].strip() if data['bio'] else None
        
        db.session.commit()
        current_app.logger.info(f"✅ Profile updated for user {current_user_id}")
        
        return {
            'message': 'Profile updated successfully',
            'profile': user.to_dict()
        }, 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Profile update failed for user {current_user_id}: {str(e)}")
        return {'error': 'Failed to update profile'}, 500

@profile_bp.route('/profile/photo', methods=['POST'])
@token_required
def update_profile_photo(current_user_id):
    try:
        user = User.query.get(current_user_id)
        if not user:
            return {'error': 'User not found'}, 404
        
        data = request.get_json()
        
        if 'profile_photo_url' in data:
            photo_data = data['profile_photo_url']
            
            if photo_data and photo_data.startswith('data:image'):
                if len(photo_data) > 100000:
                    return {'error': 'Photo too large. Please use a smaller image.'}, 400
                
                user.profile_image_url = photo_data
            else:
                user.profile_image_url = photo_data
            
            db.session.commit()
            current_app.logger.info(f"✅ Profile photo updated for user {current_user_id}")
            
            return {
                'message': 'Profile photo updated successfully',
                'profile_image_url': user.profile_image_url
            }, 200
        
        return {'error': 'No photo data provided'}, 400
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Profile photo update failed: {str(e)}")
        return {'error': 'Failed to update profile photo'}, 500

@profile_bp.route('/profile/check-screen-name', methods=['POST'])
@token_required
def check_screen_name(current_user_id):
    try:
        data = request.get_json()
        screen_name = data.get('screen_name', '').strip().lstrip('@').lower()
        
        if not screen_name:
            return {'available': False, 'reason': 'Screen name cannot be empty'}, 400
        
        current_user = User.query.get(current_user_id)
        if current_user and current_user.screen_name == screen_name:
            return {'available': True, 'current': True}, 200
        
        existing = User.query.filter(
            User.screen_name == screen_name,
            User.id != current_user_id,
            User.is_active == True
        ).first()
        
        if existing:
            return {'available': False, 'reason': 'Screen name already taken'}, 200
        
        return {'available': True}, 200
        
    except Exception as e:
        current_app.logger.error(f"Screen name check failed: {str(e)}")
        return {'error': 'Failed to check screen name'}, 500

@profile_bp.route('/users/search', methods=['GET'])
@token_required
def search_users(current_user_id):
    try:
        query = request.args.get('q', '').strip()
        
        if not query or not query.startswith('@') or len(query) < 3:
            return {'users': []}, 200
        
        clean_query = query[1:].lower()
        
        current_app.logger.info(f"🔍 User search for '@{clean_query}' by user {current_user_id}")
        
        users = User.query.filter(
            db.and_(
                User.id != current_user_id,
                User.screen_name.ilike(f'{clean_query}%')
            )
        ).limit(10).all()
        
        user_results = []
        for user in users:
            if user.screen_name:
                user_results.append({
                    'id': user.id,
                    'screen_name': user.screen_name,
                    'display_name': f"@{user.screen_name}",
                    'profile_image_url': user.profile_image_url,
                    'is_verified': user.is_verified or False
                })
        
        current_app.logger.info(f"🔍 User search returned {len(user_results)} results")
        
        return {'users': user_results}, 200
        
    except Exception as e:
        current_app.logger.error(f"❌ User search failed: {str(e)}")
        return {'error': 'Search failed'}, 500

@profile_bp.route('/users/lookup', methods=['POST'])
@token_required
def lookup_user(current_user_id):
    try:
        data = request.get_json()
        identifier = data.get('identifier', '').strip()
        
        if not identifier:
            return {'error': 'Identifier is required'}, 400
        
        current_app.logger.info(f"🔍 User lookup for '{identifier}' by user {current_user_id}")
        
        user = None
        
        if identifier.startswith('@'):
            clean_identifier = identifier[1:].lower()
            user = User.query.filter(
                db.and_(
                    User.id != current_user_id,
                    User.screen_name == clean_identifier
                )
            ).first()
        else:
            user = User.query.filter(
                db.and_(
                    User.id != current_user_id,
                    db.or_(
                        User.email == identifier.lower(),
                        User.screen_name == identifier.lower()
                    )
                )
            ).first()
        
        if not user:
            current_app.logger.warning(f"🔍 User lookup failed: '{identifier}' not found")
            return {'error': 'User not found'}, 404
        
        result = {
            'user': {
                'id': user.id,
                'email': user.email,
                'screen_name': user.screen_name,
                'display_name': f"@{user.screen_name}" if user.screen_name else user.email,
                'profile_image_url': user.profile_image_url,
                'is_verified': user.is_verified or False
            }
        }
        
        current_app.logger.info(f"✅ User lookup successful: {identifier}")
        
        return result, 200
        
    except Exception as e:
        current_app.logger.error(f"❌ User lookup failed: {str(e)}")
        return {'error': 'Lookup failed'}, 500

@profile_bp.route('/profile/delete', methods=['POST'])
@token_required
def delete_account(current_user_id):
    try:
        data = request.get_json()
        
        password = data.get('password')
        if not password:
            return {'error': 'Password is required to delete account'}, 400
        
        user = User.query.get(current_user_id)
        if not user:
            return {'error': 'User not found'}, 404
        
        if not bcrypt.checkpw(password.encode('utf-8'), user.password.encode('utf-8')):
            current_app.logger.warning(f"Failed delete attempt for user {current_user_id}: wrong password")
            return {'error': 'Invalid password'}, 401
        
        current_app.logger.info(f"⚠️ Account deletion initiated for user {current_user_id}")
        
        if current_app.config.get('USE_SOFT_DELETE', True):
            user.is_active = False
            user.deleted_at = datetime.now(timezone.utc)
            user.deletion_reason = data.get('reason', 'User requested')
            
            user.email = f"deleted_{user.id}_{uuid.uuid4().hex[:8]}@deleted.local"
            user.first_name = None
            user.last_name = None
            user.screen_name = f"deleted_user_{user.id}"
            user.age = None
            user.profile_image_url = None
            
            active_keys = ShareableKey.query.filter_by(
                creator_id=current_user_id,
                status='active'
            ).all()
            
            for key in active_keys:
                key.status = 'revoked'
                key.revoked_reason = 'Account deleted'
            
            pending_requests = Request.query.filter(
                db.and_(
                    db.or_(
                        Request.requester_id == current_user_id,
                        Request.target_user_id == current_user_id
                    ),
                    Request.status == 'pending'
                )
            ).all()
            
            for req in pending_requests:
                req.status = 'cancelled'
                req.cancellation_reason = 'Account deleted'
            
            db.session.commit()
            
            current_app.logger.info(f"✅ User {current_user_id} soft deleted successfully")
            
            return {
                'message': 'Account has been deleted successfully',
                'deleted_at': user.deleted_at.isoformat()
            }, 200
            
        else:
            KYCVerification.query.filter_by(user_id=current_user_id).delete()
            
            ShareableKey.query.filter(
                db.or_(
                    ShareableKey.creator_id == current_user_id,
                    ShareableKey.recipient_user_id == current_user_id
                )
            ).delete()
            
            Request.query.filter(
                db.or_(
                    Request.requester_id == current_user_id,
                    Request.target_user_id == current_user_id
                )
            ).delete()
            
            db.session.delete(user)
            db.session.commit()
            
            current_app.logger.info(f"⚠️ User {current_user_id} hard deleted")
            
            return {
                'message': 'Account has been permanently deleted'
            }, 200
            
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Account deletion failed for user {current_user_id}: {str(e)}")
        return {'error': 'Failed to delete account. Please try again.'}, 500