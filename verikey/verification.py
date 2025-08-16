from flask import Blueprint, request, jsonify, current_app
from werkzeug.exceptions import BadRequest
import re
import uuid
from verikey.models import db
from verikey.models import User, Request, ShareableKey
from verikey.decorators import token_required
from datetime import datetime
import json

verification_bp = Blueprint('verification', __name__)

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

@verification_bp.route('/requests', methods=['GET'])
@token_required
def get_requests(current_user_id):
    """Get all requests - Rate limited"""
    # Apply rate limiting
    if hasattr(current_app, 'limiter'):
        limiter = current_app.limiter
        limited = limiter.limit("60 per minute")(lambda: None)
        try:
            limited()
        except:
            return {'error': 'Rate limit exceeded', 'message': '60 requests per minute allowed'}, 429
    
    try:
        current_user = User.query.get(current_user_id)
        if not current_user:
            return {'error': 'User not found'}, 404
        
        sent_requests = Request.query.filter_by(
            requester_id=current_user_id
        ).order_by(Request.created_at.desc()).all()
        
        received_requests = Request.query.filter_by(
            target_email=current_user.email
        ).order_by(Request.created_at.desc()).all()
        
        sent_requests_ui = []
        for req in sent_requests:
            if req.status == 'completed':
                continue
            
            target_user = User.query.get(req.target_user_id) if req.target_user_id else None
            
            if target_user and target_user.screen_name:
                target_name = f"@{target_user.screen_name}"
            elif target_user and target_user.first_name:
                target_name = f"{target_user.first_name} {target_user.last_name or ''}".strip()
            elif req.target_email and not req.target_email.startswith('shareable-'):
                target_name = req.target_email
            elif req.target_email and req.target_email.startswith('shareable-'):
                target_name = 'Shareable Link'
            else:
                target_name = 'Unknown'
            
            sent_requests_ui.append({
                'id': req.id,
                'title': req.label,
                'status': req.status,
                'sentTo': target_name,
                'sentOn': req.created_at.isoformat() if req.created_at else 'Unknown',
                'informationTypes': req.get_information_types(),
                'notes': req.notes or '',
                'type': 'sent'
            })
        
        received_requests_ui = []
        for req in received_requests:
            if req.status == 'completed':
                continue
            
            requester = User.query.get(req.requester_id)
            
            if requester and requester.screen_name:
                requester_name = f"@{requester.screen_name}"
            elif requester and requester.first_name:
                requester_name = f"{requester.first_name} {requester.last_name or ''}".strip()
            elif requester:
                requester_name = requester.email
            else:
                requester_name = 'Unknown'
            
            received_requests_ui.append({
                'id': req.id,
                'title': req.label,
                'status': req.status,
                'from': requester_name,
                'receivedOn': req.created_at.isoformat() if req.created_at else 'Unknown',
                'informationTypes': req.get_information_types(),
                'notes': req.notes or '',
                'type': 'received'
            })
        
        current_app.logger.info(f"✅ Retrieved {len(received_requests_ui)} received and {len(sent_requests_ui)} sent requests for user {current_user_id}")
        
        return {
            'received': received_requests_ui,
            'sent': sent_requests_ui,
            'received_requests': received_requests_ui,
            'sent_requests': sent_requests_ui
        }, 200
        
    except Exception as e:
        current_app.logger.error(f"❌ Failed to get requests for user {current_user_id}: {str(e)}")
        return {'error': 'Failed to get requests'}, 500

@verification_bp.route('/requests', methods=['POST'])
@token_required
def create_request(current_user_id):
    """Create request - Rate limited"""
    # Apply rate limiting
    if hasattr(current_app, 'limiter'):
        limiter = current_app.limiter
        limited = limiter.limit("30 per hour")(lambda: None)
        try:
            limited()
        except:
            return {'error': 'Rate limit exceeded', 'message': '30 requests per hour allowed'}, 429
    
    try:
        data = request.get_json()
        current_app.logger.info(f"🚀 Creating request with data: {data}")
        
        if not data.get('label'):
            return {'error': 'Title is required'}, 400
        
        is_valid, error_message = validate_title(data.get('label', ''))
        if not is_valid:
            return {'error': error_message}, 400
        
        cleaned_title = data['label'].strip()
        
        if not data.get('target_email'):
            return {'error': 'Target email is required'}, 400
        
        if not data.get('information_types'):
            return {'error': 'Information types are required'}, 400
        
        target_user = None
        target_identifier = data['target_email'].strip()
        
        target_user = User.query.filter_by(email=target_identifier).first()
        if not target_user:
            clean_identifier = target_identifier.lstrip('@').lower()
            target_user = User.query.filter_by(screen_name=clean_identifier).first()
        
        new_request = Request(
            label=cleaned_title,
            requester_id=current_user_id,
            target_email=target_user.email if target_user else target_identifier,
            target_user_id=target_user.id if target_user else None,
            notes=data.get('notes', ''),
            status='pending'
        )
        
        if isinstance(data['information_types'], list):
            new_request.set_information_types(data['information_types'])
        else:
            return {'error': 'Information types must be a list'}, 400
        
        db.session.add(new_request)
        db.session.commit()
        
        current_app.logger.info(f"✅ Created verification request: {new_request.id} from user {current_user_id} to {new_request.target_email}")
        current_app.logger.info(f"🎯 Target user ID: {new_request.target_user_id}")
        
        return {
            'message': 'Verification request created successfully',
            'request_id': new_request.id,
            'request': {
                'id': new_request.id,
                'label': new_request.label,
                'target_email': new_request.target_email,
                'target_user_id': new_request.target_user_id,
                'status': new_request.status,
                'created_at': new_request.created_at.isoformat()
            }
        }, 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ Failed to create request: {str(e)}")
        return {'error': 'Failed to create request'}, 500

@verification_bp.route('/requests/<int:request_id>', methods=['DELETE'])
@token_required
def delete_request(current_user_id, request_id):
    """Delete request - Rate limited"""
    # Apply rate limiting
    if hasattr(current_app, 'limiter'):
        limiter = current_app.limiter
        limited = limiter.limit("30 per hour")(lambda: None)
        try:
            limited()
        except:
            return {'error': 'Rate limit exceeded', 'message': '30 operations per hour allowed'}, 429
    
    try:
        verification_request = Request.query.get(request_id)
        
        if not verification_request:
            return {'error': 'Request not found'}, 404
        
        current_user = User.query.get(current_user_id)
        if not current_user:
            return {'error': 'User not found'}, 404
        
        is_requester = verification_request.requester_id == current_user_id
        is_target = current_user.email == verification_request.target_email
        
        if not (is_requester or is_target):
            return {'error': 'You can only delete your own requests or requests sent to you'}, 403
        
        if is_requester:
            if verification_request.status == 'completed':
                existing_key = ShareableKey.query.filter_by(
                    creator_id=verification_request.target_user_id,
                    recipient_user_id=verification_request.requester_id,
                    notes=db.func.concat('Verification response for request: ', verification_request.label)
                ).first()
                
                if existing_key:
                    return {'error': 'This completed request has been turned into a key. Check your received keys.'}, 400
            
            if verification_request.status not in ['pending', 'denied', 'cancelled', 'completed']:
                return {'error': f'Cannot delete a {verification_request.status} request'}, 400
        
        db.session.delete(verification_request)
        db.session.commit()
        
        current_app.logger.info(f"✅ Request deleted: ID {request_id} by user {current_user_id}")
        
        return {
            'message': 'Request deleted successfully'
        }, 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to delete request {request_id}: {str(e)}")
        return {'error': 'Failed to delete request'}, 500

@verification_bp.route('/requests/<int:request_id>/deny', methods=['POST'])
@token_required
def deny_request(current_user_id, request_id):
    """Deny request - Rate limited"""
    # Apply rate limiting
    if hasattr(current_app, 'limiter'):
        limiter = current_app.limiter
        limited = limiter.limit("30 per hour")(lambda: None)
        try:
            limited()
        except:
            return {'error': 'Rate limit exceeded', 'message': '30 operations per hour allowed'}, 429
    
    try:
        verification_request = Request.query.get(request_id)
        
        if not verification_request:
            return {'error': 'Request not found'}, 404
        
        current_user = User.query.get(current_user_id)
        if not current_user or current_user.email != verification_request.target_email:
            return {'error': 'You can only deny requests sent to you'}, 403
        
        if verification_request.status != 'pending':
            return {'error': f'Cannot deny a {verification_request.status} request'}, 400
        
        verification_request.status = 'denied'
        verification_request.response_at = datetime.utcnow()
        
        db.session.commit()
        
        current_app.logger.info(f"✅ Request denied: ID {request_id} by user {current_user_id}")
        
        return {
            'message': 'Request denied successfully'
        }, 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to deny request {request_id} for user {current_user_id}: {str(e)}")
        return {'error': 'Failed to deny request'}, 500

@verification_bp.route('/requests/<int:request_id>', methods=['PUT'])
@token_required
def update_request(current_user_id, request_id):
    """Update request - Rate limited"""
    # Apply rate limiting
    if hasattr(current_app, 'limiter'):
        limiter = current_app.limiter
        limited = limiter.limit("30 per hour")(lambda: None)
        try:
            limited()
        except:
            return {'error': 'Rate limit exceeded', 'message': '30 operations per hour allowed'}, 429
    
    try:
        data = request.get_json()
        verification_request = Request.query.get(request_id)
        
        if not verification_request:
            return {'error': 'Request not found'}, 404
        
        if verification_request.requester_id != current_user_id:
            return {'error': 'You can only update your own requests'}, 403
        
        if verification_request.status != 'pending':
            return {'error': f'Cannot update a {verification_request.status} request'}, 400
        
        if 'label' in data:
            is_valid, error_message = validate_title(data.get('label', ''))
            if not is_valid:
                return {'error': error_message}, 400
            verification_request.label = data['label'].strip()
        
        if 'notes' in data:
            verification_request.notes = data['notes']
        
        if 'information_types' in data:
            if isinstance(data['information_types'], list):
                verification_request.set_information_types(data['information_types'])
            else:
                return {'error': 'Information types must be a list'}, 400
        
        db.session.commit()
        
        current_app.logger.info(f"✅ Request updated: ID {request_id} by user {current_user_id}")
        
        return {
            'message': 'Request updated successfully'
        }, 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to update request {request_id} for user {current_user_id}: {str(e)}")
        return {'error': 'Failed to update request'}, 500

@verification_bp.route('/verifications', methods=['POST'])
@token_required
def submit_verification(current_user_id):
    """Submit verification - Rate limited"""
    # Apply rate limiting
    if hasattr(current_app, 'limiter'):
        limiter = current_app.limiter
        limited = limiter.limit("30 per hour")(lambda: None)
        try:
            limited()
        except:
            return {'error': 'Rate limit exceeded', 'message': '30 verifications per hour allowed'}, 429
    
    try:
        data = request.get_json()
        current_app.logger.info(f"🚀 Submitting verification response: {data}")
        
        if not data.get('request_id'):
            return {'error': 'Request ID is required'}, 400
        
        request_id = data['request_id']
        verification_request = Request.query.get(request_id)
        
        if not verification_request:
            return {'error': 'Request not found'}, 404
        
        current_user = User.query.get(current_user_id)
        if not current_user or current_user.email != verification_request.target_email:
            return {'error': 'You can only respond to requests sent to you'}, 403
        
        if verification_request.status != 'pending':
            return {'error': f'Cannot respond to a {verification_request.status} request'}, 400
        
        # Handle views_allowed from the request
        views_allowed = data.get('views_allowed', 2)
        if views_allowed <= 0:
            views_allowed = 2
        
        new_key = ShareableKey(
            key_uuid=str(uuid.uuid4()),
            creator_id=current_user_id,
            recipient_email=verification_request.requester.email,
            recipient_user_id=verification_request.requester_id,
            label=f"Response to: {verification_request.label}",
            views_allowed=views_allowed,  # Use the value from the request
            is_shareable_link=False,
            notes=f"Verification response for request: {verification_request.label}",
            status='active'
        )
        
        new_key.set_information_types(verification_request.get_information_types())
        
        user_data = {}
        information_types = verification_request.get_information_types()
        
        # Parse additional_data if it exists
        additional_data = {}
        if 'additional_data' in data and data['additional_data']:
            try:
                additional_data = json.loads(data['additional_data'])
            except json.JSONDecodeError:
                current_app.logger.warning(f"Failed to parse additional_data: {data['additional_data']}")
        
        for info_type in information_types:
            if info_type == 'fullname':
                # Check additional_data first, then fall back to user profile
                if 'fullname' in additional_data:
                    user_data['fullname'] = additional_data['fullname']
                elif current_user.first_name and current_user.last_name:
                    user_data['fullname'] = f"{current_user.first_name} {current_user.last_name}"
                else:
                    user_data['fullname'] = "Name not available"
            
            elif info_type == 'firstname':
                # Check additional_data first, then fall back to user profile
                if 'firstname' in additional_data:
                    user_data['firstname'] = additional_data['firstname']
                else:
                    user_data['firstname'] = current_user.first_name or "First name not available"
            
            elif info_type == 'age':
                # Check additional_data first, then fall back to user profile
                if 'age' in additional_data:
                    user_data['age'] = str(additional_data['age'])
                else:
                    user_data['age'] = str(current_user.age) if current_user.age else "Age not provided"
            
            elif info_type == 'location':
                if 'latitude' in data and 'longitude' in data:
                    user_data['location'] = {
                        'latitude': data['latitude'],
                        'longitude': data['longitude'],
                        'cityDisplay': data.get('location_city_display', 'Location captured')
                    }
                elif 'location_data' in data:
                    user_data['location'] = data['location_data']
                else:
                    user_data['location'] = {
                        'cityDisplay': 'Location not captured',
                        'latitude': None,
                        'longitude': None
                    }
            
            # FIXED: Handle selfie and photo separately
            elif info_type == 'selfie':
                if 'selfie_base64' in data:
                    user_data['selfie'] = {
                        'status': 'captured',
                        'image_data': data['selfie_base64'],
                        'captured_at': datetime.utcnow().isoformat()
                    }
                else:
                    user_data['selfie'] = {
                        'status': 'not_captured',
                        'image_data': None,
                        'captured_at': None
                    }
            
            elif info_type == 'photo':
                if 'photo_base64' in data:
                    user_data['photo'] = {
                        'status': 'captured',
                        'image_data': data['photo_base64'],
                        'captured_at': datetime.utcnow().isoformat()
                    }
                else:
                    user_data['photo'] = {
                        'status': 'not_captured',
                        'image_data': None,
                        'captured_at': None
                    }
        
        new_key.set_user_data(user_data)
        
        db.session.add(new_key)
        
        verification_request.status = 'completed'
        verification_request.response_at = datetime.utcnow()
        
        db.session.commit()
        
        current_app.logger.info(f"✅ Verification response submitted: Request {request_id} by user {current_user_id}")
        current_app.logger.info(f"📊 Response contains data: {list(user_data.keys())}")
        
        return {
            'message': 'Verification response submitted successfully',
            'key_id': new_key.id,
            'key_uuid': new_key.key_uuid
        }, 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ Failed to submit verification response: {str(e)}")
        return {'error': 'Failed to submit verification response'}, 500