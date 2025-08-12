from flask import Blueprint, request, jsonify, current_app
from verikey.models import db
from verikey.models import User, ShareableKey
from verikey.decorators import token_required
from datetime import datetime
import uuid
import json

keys_bp = Blueprint('keys', __name__)

def validate_title(title: str) -> tuple[bool, str]:
    if not title or not title.strip():
        return False, "Title is required"
    
    title = title.strip()
    
    MIN_LENGTH = 3
    MAX_LENGTH = 30
    
    if len(title) < MIN_LENGTH:
        return False, f"Title must be at least {MIN_LENGTH} characters"
    
    if len(title) > MAX_LENGTH:
        return False, f"Title must be no more than {MAX_LENGTH} characters"
    
    words = title.split()
    if len(words) == 1 and len(title) > 20:
        return False, "Title appears to be a single long word. Please use a descriptive title"
    
    MAX_WORD_LENGTH = 15
    for word in words:
        if len(word) > MAX_WORD_LENGTH:
            return False, f"Individual words in title cannot exceed {MAX_WORD_LENGTH} characters"
    
    if not any(c.isalpha() for c in title):
        return False, "Title must contain at least some letters"
    
    return True, ""

@keys_bp.route('/keys', methods=['GET'])
@token_required
def get_all_keys(current_user_id):
    try:
        sent_keys = ShareableKey.query.filter_by(creator_id=current_user_id).order_by(ShareableKey.created_at.desc()).all()
        
        received_keys = ShareableKey.query.filter_by(recipient_user_id=current_user_id).order_by(ShareableKey.created_at.desc()).all()
        
        keys_to_update = []
        for key in sent_keys + received_keys:
            if key.status == 'active' and key.views_used >= key.views_allowed:
                key.status = 'viewed_out'
                keys_to_update.append(key.id)
        
        if keys_to_update:
            db.session.commit()
            current_app.logger.info(f"🔄 Auto-revoked {len(keys_to_update)} keys due to exhausted views")
        
        sent_keys_ui = []
        for key in sent_keys:
            recipient = User.query.get(key.recipient_user_id) if key.recipient_user_id else None
            
            if key.is_shareable_link:
                recipient_name = 'Shareable Link'
            elif recipient and recipient.screen_name:
                recipient_name = f"@{recipient.screen_name}"
            elif recipient and recipient.first_name:
                recipient_name = f"{recipient.first_name} {recipient.last_name or ''}".strip()
            elif key.recipient_email:
                recipient_name = key.recipient_email
            else:
                recipient_name = 'Unknown'
            
            sent_date = 'Unknown'
            if key.created_at:
                try:
                    sent_date = key.created_at.strftime('%m/%d/%Y at %I:%M %p')
                except:
                    sent_date = key.created_at.isoformat()
            
            sent_keys_ui.append({
                'id': key.id,
                'label': key.label or 'Untitled Key',
                'title': key.label or 'Untitled Key',
                'type': 'sent',
                'status': key.status,
                'sentTo': recipient_name,
                'sharedWith': recipient_name,
                'recipient_email': key.recipient_email,
                'views': f"{key.views_used}/{key.views_allowed}" if key.views_allowed != 999 else "Unlimited",
                'views_used': key.views_used,
                'views_allowed': key.views_allowed,
                'viewsRemaining': max(0, key.views_allowed - key.views_used),
                'sentOn': sent_date,
                'created_at': key.created_at.isoformat() if key.created_at else None,
                'lastViewed': key.last_viewed_at.strftime('%m/%d/%Y at %I:%M %p') if key.last_viewed_at else 'Not Viewed',
                'informationTypes': key.get_information_types(),
                'notes': key.notes,
                'user_data': key.get_user_data(),
                'hasNoViewsLeft': key.status == 'viewed_out',
                'badgeText': 'Viewed out' if key.status == 'viewed_out' else None,
                'recipient': {
                    'id': recipient.id if recipient else None,
                    'screen_name': recipient.screen_name if recipient else None,
                    'email': recipient.email if recipient else key.recipient_email,
                }
            })
        
        received_keys_ui = []
        for key in received_keys:
            creator = User.query.get(key.creator_id)
            
            if creator and creator.screen_name:
                creator_name = f"@{creator.screen_name}"
            elif creator and creator.first_name:
                creator_name = f"{creator.first_name} {creator.last_name or ''}".strip()
            elif creator:
                creator_name = creator.email
            else:
                creator_name = 'Unknown'
            
            received_date = 'Unknown'
            if key.created_at:
                try:
                    received_date = key.created_at.strftime('%m/%d/%Y at %I:%M %p')
                except:
                    received_date = key.created_at.isoformat()
            
            is_new = key.views_used == 0 and key.status == 'active'
            has_no_views_left = key.status == 'viewed_out'
            
            badge_text = None
            if is_new:
                badge_text = 'NEW'
            elif has_no_views_left:
                badge_text = 'No views left'
            
            received_keys_ui.append({
                'id': key.id,
                'label': key.label or 'Untitled Key',
                'title': key.label or 'Untitled Key',
                'type': 'received',
                'status': key.status,
                'from': creator_name,
                'views': f"{key.views_used}/{key.views_allowed}" if key.views_allowed != 999 else "Unlimited",
                'views_used': key.views_used,
                'views_allowed': key.views_allowed,
                'viewsRemaining': max(0, key.views_allowed - key.views_used),
                'receivedOn': received_date,
                'created_at': key.created_at.isoformat() if key.created_at else None,
                'informationTypes': key.get_information_types(),
                'notes': key.notes,
                'user_data': key.get_user_data(),
                'isNew': is_new,
                'hasNoViewsLeft': has_no_views_left,
                'badgeText': badge_text,
                'creator': {
                    'id': creator.id if creator else None,
                    'screen_name': creator.screen_name if creator else None,
                    'email': creator.email if creator else None,
                }
            })
        
        current_app.logger.info(f"✅ Retrieved {len(sent_keys)} sent and {len(received_keys)} received keys for user {current_user_id}")
        
        return {
            'keys': sent_keys_ui,
            'sent_keys': sent_keys_ui,
            'received_keys': received_keys_ui,
            'new_keys_count': sum(1 for key in received_keys_ui if key['isNew'])
        }, 200
        
    except Exception as e:
        current_app.logger.error(f"❌ Failed to get keys for user {current_user_id}: {str(e)}")
        return {'error': 'Failed to get keys'}, 500

@keys_bp.route('/keys', methods=['POST'])
@token_required
def create_shareable_key(current_user_id):
    try:
        data = request.get_json()
        current_app.logger.info(f"🚀 Creating key with data: {data}")
        
        if not data.get('label'):
            return {'error': 'Title is required'}, 400
        
        is_valid, error_message = validate_title(data.get('label', ''))
        if not is_valid:
            return {'error': error_message}, 400
        
        cleaned_title = data['label'].strip()
        
        if not data.get('recipient_email') and not data.get('is_shareable_link'):
            return {'error': 'Recipient email is required'}, 400
        
        if not data.get('information_types'):
            return {'error': 'Information types are required'}, 400
        
        recipient_user = None
        if data.get('recipient_email'):
            recipient_email = data['recipient_email'].strip()
            recipient_user = User.query.filter_by(email=recipient_email, is_active=True).first()
        
        current_user = User.query.get(current_user_id)
        if not current_user:
            return {'error': 'User not found'}, 404
        
        views_allowed = data.get('views_allowed', 2)
        if views_allowed <= 0:
            views_allowed = 2
        
        new_key = ShareableKey(
            key_uuid=str(uuid.uuid4()),
            creator_id=current_user_id,
            recipient_email=recipient_user.email if recipient_user else data.get('recipient_email'),
            recipient_user_id=recipient_user.id if recipient_user else None,
            label=cleaned_title,
            views_allowed=views_allowed,
            is_shareable_link=data.get('is_shareable_link', False),
            notes=data.get('notes', ''),
            status='active'
        )
        
        if isinstance(data['information_types'], list):
            new_key.set_information_types(data['information_types'])
        else:
            return {'error': 'Information types must be a list'}, 400
        
        user_data = {}
        information_types = data['information_types']
        
        for info_type in information_types:
            if info_type == 'fullname':
                user_data['fullname'] = current_user.display_full_name
                user_data['is_verified'] = current_user.is_verified
                
            elif info_type == 'firstname':
                user_data['firstname'] = current_user.display_first_name
                user_data['is_verified'] = current_user.is_verified
                
            elif info_type == 'age':
                user_data['age'] = str(current_user.age) if current_user.age else "Age not available"
                user_data['is_verified'] = current_user.is_verified
                
            elif info_type == 'location':
                if 'location_data' in data:
                    location_data = data['location_data']
                    user_data['location'] = {
                        'cityDisplay': location_data.get('cityDisplay', 'Location captured'),
                    }
                elif 'user_data' in data and 'location' in data['user_data']:
                    location_data = data['user_data']['location']
                    user_data['location'] = {
                        'cityDisplay': location_data.get('cityDisplay', 'Location captured'),
                    }
                else:
                    user_data['location'] = {
                        'cityDisplay': 'Location not captured'
                    }
                    
            elif info_type == 'selfie':
                if 'selfie_data' in data:
                    user_data['selfie'] = {
                        'status': 'captured',
                        'image_data': data['selfie_data'],
                        'captured_at': datetime.utcnow().isoformat()
                    }
                elif 'user_data' in data and 'selfie' in data['user_data']:
                    user_data['selfie'] = data['user_data']['selfie']
                else:
                    user_data['selfie'] = {
                        'status': 'not_captured',
                        'image_data': None
                    }
                    
            elif info_type == 'photo':
                if 'photo_data' in data:
                    user_data['photo'] = {
                        'status': 'captured',
                        'image_data': data['photo_data'],
                        'captured_at': datetime.utcnow().isoformat()
                    }
                elif 'user_data' in data and 'photo' in data['user_data']:
                    user_data['photo'] = data['user_data']['photo']
                else:
                    user_data['photo'] = {
                        'status': 'not_captured',
                        'image_data': None
                    }
        
        if current_user.is_verified:
            user_data['verification_badge'] = {
                'verified': True,
                'verified_at': current_user.verified_at.isoformat() if current_user.verified_at else None,
                'verification_level': current_user.verification_level,
                'message': 'This information has been verified via government ID'
            }
        
        new_key.set_user_data(user_data)
        
        db.session.add(new_key)
        db.session.commit()
        
        current_app.logger.info(f"✅ Created shareable key: {new_key.key_uuid} (ID: {new_key.id})")
        current_app.logger.info(f"📊 Key includes: {', '.join(information_types)}")
        
        return {
            'message': 'Shareable key created successfully',
            'key_id': new_key.id,
            'key_uuid': new_key.key_uuid,
            'key': new_key.to_dict()
        }, 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ Failed to create key: {str(e)}")
        return {'error': 'Failed to create key'}, 500

@keys_bp.route('/verifications', methods=['POST'])
@token_required  
def submit_verification_response(current_user_id):
    try:
        data = request.get_json()
        request_id = data.get('request_id')
        
        if not request_id:
            return {'error': 'Request ID is required'}, 400
        
        from verikey.models import Request
        verification_request = Request.query.get(request_id)
        
        if not verification_request:
            return {'error': 'Request not found'}, 404
        
        current_user = User.query.get(current_user_id)
        if not current_user:
            return {'error': 'User not found'}, 404
        
        if current_user.email != verification_request.target_email:
            return {'error': 'You can only respond to requests sent to you'}, 403
        
        new_key = ShareableKey(
            key_uuid=str(uuid.uuid4()),
            creator_id=current_user_id,
            recipient_email=verification_request.requester.email,
            recipient_user_id=verification_request.requester_id,
            label=f"Response to: {verification_request.label}",
            views_allowed=2,
            is_shareable_link=False,
            notes=f"Verification response for request: {verification_request.label}",
            status='active'
        )
        
        new_key.set_information_types(verification_request.get_information_types())
        
        user_data = {}
        information_types = verification_request.get_information_types()
        
        for info_type in information_types:
            if info_type == 'fullname':
                user_data['fullname'] = current_user.display_full_name
                user_data['is_verified'] = current_user.is_verified
                
            elif info_type == 'firstname':
                user_data['firstname'] = current_user.display_first_name
                user_data['is_verified'] = current_user.is_verified
                
            elif info_type == 'age':
                user_data['age'] = str(current_user.age) if current_user.age else "Age not provided"
                user_data['is_verified'] = current_user.is_verified
                
            elif info_type == 'location':
                if 'latitude' in data and 'longitude' in data:
                    user_data['location'] = {
                        'cityDisplay': data.get('cityDisplay', 'Location captured')
                    }
                else:
                    user_data['location'] = {
                        'cityDisplay': 'Location not captured'
                    }
                    
            elif info_type in ['selfie', 'photo']:
                if 'photo_base64' in data:
                    user_data[info_type] = {
                        'status': 'captured',
                        'image_data': data['photo_base64'],
                        'captured_at': datetime.utcnow().isoformat()
                    }
                else:
                    user_data[info_type] = {
                        'status': 'not_captured',
                        'image_data': None
                    }
        
        if current_user.is_verified:
            user_data['verification_badge'] = {
                'verified': True,
                'message': 'This information has been verified via government ID'
            }
        
        new_key.set_user_data(user_data)
        
        db.session.add(new_key)
        
        verification_request.status = 'completed'
        verification_request.response_at = datetime.utcnow()
        
        db.session.commit()
        
        current_app.logger.info(f"✅ Verification response submitted: Request {request_id} by user {current_user_id}")
        
        return {
            'message': 'Verification response submitted successfully',
            'key_id': new_key.id,
            'key_uuid': new_key.key_uuid
        }, 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ Failed to submit verification response: {str(e)}")
        return {'error': 'Failed to submit verification response'}, 500

@keys_bp.route('/keys/<int:key_id>/details', methods=['GET'])
@token_required
def get_key_details(current_user_id, key_id):
    try:
        key = ShareableKey.query.filter(
            db.and_(
                ShareableKey.id == key_id,
                db.or_(
                    ShareableKey.creator_id == current_user_id,
                    ShareableKey.recipient_user_id == current_user_id
                )
            )
        ).first()
        
        if not key:
            return {'error': 'Key not found or access denied'}, 404
        
        if (key.recipient_user_id == current_user_id and 
            key.status == 'viewed_out' and 
            key.views_used >= key.views_allowed):
            return {
                'key_details': {
                    'id': key.id,
                    'label': key.label,
                    'status': 'viewed_out',
                    'views_used': key.views_used,
                    'views_allowed': key.views_allowed,
                    'error': 'You have exhausted all allowed views for this key'
                }
            }, 403
        
        if key.recipient_user_id == current_user_id and key.status == 'active':
            key.views_used += 1
            key.last_viewed_at = datetime.utcnow()
            
            if key.views_used >= key.views_allowed:
                key.status = 'viewed_out'
                current_app.logger.info(f"🔄 Key {key_id} moved to viewed_out status")
            
            db.session.commit()
            current_app.logger.info(f"👁 View counted for key {key_id}: {key.views_used}/{key.views_allowed}")
        
        creator = User.query.get(key.creator_id)
        recipient = User.query.get(key.recipient_user_id) if key.recipient_user_id else None
        
        user_data = key.get_user_data()
        if user_data and 'location' in user_data and isinstance(user_data['location'], dict):
            user_data['location'] = {
                'cityDisplay': user_data['location'].get('cityDisplay', 'Location shared')
            }
        
        key_details = {
            'id': key.id,
            'key_uuid': key.key_uuid,
            'label': key.label,
            'status': key.status,
            'information_types': key.get_information_types(),
            'user_data': user_data,
            'views_used': key.views_used,
            'views_allowed': key.views_allowed,
            'views_remaining': max(0, key.views_allowed - key.views_used),
            'is_shareable_link': key.is_shareable_link,
            'notes': key.notes,
            'created_at': key.created_at.isoformat() if key.created_at else None,
            'last_viewed_at': key.last_viewed_at.isoformat() if key.last_viewed_at else None,
            'creator': {
                'id': creator.id,
                'name': f"{creator.first_name} {creator.last_name}" if creator.first_name else creator.email,
                'email': creator.email,
                'screen_name': creator.screen_name
            } if creator else None,
            'recipient': {
                'id': recipient.id if recipient else None,
                'name': f"{recipient.first_name} {recipient.last_name}" if recipient and recipient.first_name else key.recipient_email,
                'email': key.recipient_email,
                'screen_name': recipient.screen_name if recipient else None
            }
        }
        
        return {
            'key_details': key_details
        }, 200
        
    except Exception as e:
        current_app.logger.error(f"❌ Failed to get key details for key {key_id}: {str(e)}")
        return {'error': 'Failed to get key details'}, 500

@keys_bp.route('/keys/<int:key_id>/revoke', methods=['POST'])
@token_required
def revoke_key(current_user_id, key_id):
    try:
        key = ShareableKey.query.filter_by(
            id=key_id,
            creator_id=current_user_id
        ).first()
        
        if not key:
            return {'error': 'Key not found or you do not have permission'}, 404
        
        if key.status != 'active':
            return {'error': f'Cannot revoke a {key.status} key'}, 400
        
        key.status = 'revoked'
        db.session.commit()
        
        current_app.logger.info(f"✅ Key revoked: {key.key_uuid} (ID: {key_id})")
        
        return {
            'message': 'Key revoked successfully'
        }, 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ Failed to revoke key {key_id}: {str(e)}")
        return {'error': 'Failed to revoke key'}, 500

@keys_bp.route('/keys/<int:key_id>', methods=['DELETE'])
@token_required
def delete_key(current_user_id, key_id):
    try:
        sent_key = ShareableKey.query.filter_by(
            id=key_id,
            creator_id=current_user_id
        ).first()
        
        if sent_key:
            if sent_key.status == 'active':
                return {'error': 'Cannot delete an active key. Revoke first.'}, 400
            
            db.session.delete(sent_key)
            db.session.commit()
            current_app.logger.info(f"✅ Sent key deleted: {key_id}")
            return {
                'message': 'Key deleted successfully'
            }, 200
        
        received_key = ShareableKey.query.filter_by(
            id=key_id,
            recipient_user_id=current_user_id
        ).first()
        
        if received_key:
            db.session.delete(received_key)
            db.session.commit()
            current_app.logger.info(f"✅ Received key deleted: {key_id}")
            return {
                'message': 'Key deleted successfully'
            }, 200
        
        return {'error': 'Key not found or you do not have permission'}, 404
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ Failed to delete key {key_id}: {str(e)}")
        return {'error': 'Failed to delete key'}, 500

@keys_bp.route('/keys/new-count', methods=['GET'])
@token_required
def get_new_keys_count(current_user_id):
    try:
        new_keys_count = ShareableKey.query.filter_by(
            recipient_user_id=current_user_id,
            status='active',
            views_used=0
        ).count()
        
        return {
            'new_keys_count': new_keys_count
        }, 200
        
    except Exception as e:
        current_app.logger.error(f"❌ Failed to get new keys count: {str(e)}")
        return {'error': 'Failed to get new keys count'}, 500

@keys_bp.route('/keys/<int:key_id>/remove', methods=['POST'])
@token_required
def remove_received_key(current_user_id, key_id):
    try:
        key = ShareableKey.query.filter_by(
            id=key_id,
            recipient_user_id=current_user_id
        ).first()
        
        if not key:
            return {'error': 'Key not found or you do not have permission'}, 404
        
        key.status = 'removed'
        db.session.commit()
        
        current_app.logger.info(f"✅ Key moved to old section: {key_id}")
        
        return {
            'message': 'Key moved to old section successfully'
        }, 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ Failed to remove key {key_id}: {str(e)}")
        return {'error': 'Failed to remove key'}, 500