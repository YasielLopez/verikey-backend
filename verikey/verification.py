from flask import Blueprint, request, jsonify, current_app
from werkzeug.exceptions import BadRequest
import re
from verikey import db
from verikey.models import User, Request, Verification
from verikey.auth import token_required

# Create blueprint
verification_bp = Blueprint('verification', __name__)

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_coordinates(latitude, longitude):
    """Validate latitude and longitude values"""
    try:
        lat = float(latitude)
        lng = float(longitude)
        return (-90 <= lat <= 90) and (-180 <= lng <= 180)
    except (ValueError, TypeError):
        return False

@verification_bp.route('/requests', methods=['POST'])
@token_required
def create_request(current_user_id):
    """Create a new verification request (JWT protected)"""
    try:
        # Validate request has JSON data
        if not request.is_json:
            current_app.logger.warning(f"Request creation attempt without JSON data by user {current_user_id}")
            return {'error': 'Request must be JSON'}, 400
        
        data = request.get_json()
        
        # Validate required fields
        if not data:
            return {'error': 'No data provided'}, 400
        
        # Note: requester_id comes from JWT token, not request body
        target_email = data.get('target_email', '').strip().lower()
        
        if not target_email:
            current_app.logger.warning(f"Request creation with missing target_email by user {current_user_id}")
            return {'error': 'Target email is required'}, 400
        
        # Validate email format
        if not validate_email(target_email):
            current_app.logger.warning(f"Request creation with invalid email: {target_email} by user {current_user_id}")
            return {'error': 'Invalid email format'}, 400
        
        # Get current user info
        requester = User.query.get(current_user_id)
        if not requester:
            current_app.logger.error(f"Token valid but user {current_user_id} not found in create_request")
            return {'error': 'User not found'}, 404
        
        # Check if requester is requesting from themselves
        if requester.email == target_email:
            current_app.logger.warning(f"User {requester.email} tried to request verification from themselves")
            return {'error': 'Cannot request verification from yourself'}, 400
        
        # Check for duplicate pending requests
        existing_request = Request.query.filter_by(
            requester_id=current_user_id,
            target_email=target_email,
            status='pending'
        ).first()
        
        if existing_request:
            current_app.logger.warning(f"Duplicate request attempted: user {current_user_id} to {target_email}")
            return {'error': 'You already have a pending request to this email'}, 409
        
        # Create new request (requester_id comes from JWT token)
        new_request = Request(
            requester_id=current_user_id,
            target_email=target_email,
            status='pending'
        )
        db.session.add(new_request)
        db.session.commit()
        
        current_app.logger.info(f"✅ New verification request created: ID {new_request.id}, from user {current_user_id} to {target_email}")
        
        return {
            'message': 'Verification request created successfully',
            'request': {
                'id': new_request.id,
                'target_email': new_request.target_email,
                'status': new_request.status,
                'created_at': new_request.created_at.isoformat()
            }
        }, 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Request creation failed for user {current_user_id}: {str(e)}")
        return {'error': 'Failed to create verification request. Please try again.'}, 500

@verification_bp.route('/requests', methods=['GET'])
@token_required
def list_requests(current_user_id):
    """List user's sent and received verification requests (JWT protected)"""
    try:
        # Get current user info
        user = User.query.get(current_user_id)
        if not user:
            current_app.logger.error(f"Token valid but user {current_user_id} not found in list_requests")
            return {'error': 'User not found'}, 404
        
        # Get sent requests (requests this user made)
        sent_requests = Request.query.filter_by(requester_id=current_user_id).order_by(Request.created_at.desc()).all()
        sent_list = [{
            'id': req.id,
            'target_email': req.target_email,
            'status': req.status,
            'created_at': req.created_at.isoformat(),
            'type': 'sent'
        } for req in sent_requests]
        
        # Get received requests (requests sent to this user's email)
        received_requests = Request.query.filter_by(target_email=user.email).order_by(Request.created_at.desc()).all()
        received_list = []
        
        for req in received_requests:
            requester = User.query.get(req.requester_id)
            received_list.append({
                'id': req.id,
                'requester_email': requester.email if requester else 'Unknown',
                'requester_id': req.requester_id,
                'status': req.status,
                'created_at': req.created_at.isoformat(),
                'type': 'received'
            })
        
        current_app.logger.info(f"Request list retrieved for user {current_user_id}: {len(sent_list)} sent, {len(received_list)} received")
        
        return {
            'sent_requests': sent_list,
            'received_requests': received_list
        }
        
    except Exception as e:
        current_app.logger.error(f"Failed to list requests for user {current_user_id}: {str(e)}")
        return {'error': 'Failed to retrieve requests. Please try again.'}, 500

@verification_bp.route('/verifications', methods=['POST'])
@token_required
def create_verification(current_user_id):
    """Submit a verification response (photo + location) - JWT protected"""
    try:
        # Validate request has JSON data
        if not request.is_json:
            current_app.logger.warning(f"Verification creation attempt without JSON data by user {current_user_id}")
            return {'error': 'Request must be JSON'}, 400
        
        data = request.get_json()
        
        # Validate required fields
        if not data:
            return {'error': 'No data provided'}, 400
        
        required_fields = ['request_id', 'photo_url', 'latitude', 'longitude']
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            current_app.logger.warning(f"Verification creation with missing fields: {missing_fields} by user {current_user_id}")
            return {'error': f'Missing required fields: {", ".join(missing_fields)}'}, 400
        
        request_id = data.get('request_id')
        photo_url = data.get('photo_url').strip()
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        
        # Validate coordinates
        if not validate_coordinates(latitude, longitude):
            current_app.logger.warning(f"Verification creation with invalid coordinates: lat={latitude}, lng={longitude} by user {current_user_id}")
            return {'error': 'Invalid latitude or longitude values'}, 400
        
        # Validate photo URL (basic check)
        if len(photo_url) < 10:  # Very basic validation
            current_app.logger.warning(f"Verification creation with invalid photo URL: {photo_url} by user {current_user_id}")
            return {'error': 'Invalid photo URL'}, 400
        
        # Check if request exists and is still pending
        verification_request = Request.query.get(request_id)
        if not verification_request:
            current_app.logger.warning(f"Verification creation for non-existent request: {request_id} by user {current_user_id}")
            return {'error': 'Verification request not found'}, 404
        
        # Check if this user is the target of the request
        current_user = User.query.get(current_user_id)
        if not current_user or current_user.email != verification_request.target_email:
            current_app.logger.warning(f"User {current_user_id} tried to respond to request {request_id} not meant for them")
            return {'error': 'You can only respond to requests sent to your email'}, 403
        
        if verification_request.status != 'pending':
            current_app.logger.warning(f"Verification creation for non-pending request {request_id}: status={verification_request.status} by user {current_user_id}")
            return {'error': f'Request has already been {verification_request.status}'}, 400
        
        # Check if verification already exists for this request
        existing_verification = Verification.query.filter_by(request_id=request_id).first()
        if existing_verification:
            current_app.logger.warning(f"Duplicate verification attempted for request {request_id} by user {current_user_id}")
            return {'error': 'Verification already exists for this request'}, 409
        
        # Create verification
        new_verification = Verification(
            request_id=request_id,
            photo_url=photo_url,
            latitude=float(latitude),
            longitude=float(longitude)
        )
        db.session.add(new_verification)
        
        # Update request status
        verification_request.status = 'completed'
        
        db.session.commit()
        
        current_app.logger.info(f"✅ Verification created: ID {new_verification.id} for request {request_id} by user {current_user_id}")
        
        return {
            'message': 'Verification submitted successfully',
            'verification': {
                'id': new_verification.id,
                'request_id': new_verification.request_id,
                'photo_url': new_verification.photo_url,
                'latitude': float(new_verification.latitude),
                'longitude': float(new_verification.longitude),
                'created_at': new_verification.created_at.isoformat()
            }
        }, 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Verification creation failed for user {current_user_id}: {str(e)}")
        return {'error': 'Failed to submit verification. Please try again.'}, 500

@verification_bp.route('/verifications/<int:request_id>', methods=['GET'])
@token_required
def get_verification(current_user_id, request_id):
    """Get verification details for a specific request (JWT protected)"""
    try:
        # Get the verification for this request
        verification = Verification.query.filter_by(request_id=request_id).first()
        if not verification:
            current_app.logger.warning(f"Verification lookup for non-existent verification: request_id={request_id} by user {current_user_id}")
            return {'error': 'Verification not found'}, 404
        
        # Get the original request details
        original_request = Request.query.get(request_id)
        if not original_request:
            current_app.logger.error(f"Verification exists but request doesn't: request_id={request_id}")
            return {'error': 'Request not found'}, 404
        
        # Check if current user has permission to view this verification
        current_user = User.query.get(current_user_id)
        if not current_user:
            return {'error': 'User not found'}, 404
        
        # User can view if they are either:
        # 1. The requester (who asked for verification)
        # 2. The target (who provided verification)
        can_view = (
            original_request.requester_id == current_user_id or  # User requested this
            original_request.target_email == current_user.email   # User was asked to verify
        )
        
        if not can_view:
            current_app.logger.warning(f"User {current_user_id} tried to view verification {request_id} without permission")
            return {'error': 'You do not have permission to view this verification'}, 403
        
        # Get requester details
        requester = User.query.get(original_request.requester_id)
        
        current_app.logger.info(f"Verification details retrieved: verification_id={verification.id}, request_id={request_id} by user {current_user_id}")
        
        return {
            'verification': {
                'id': verification.id,
                'photo_url': verification.photo_url,
                'latitude': float(verification.latitude),
                'longitude': float(verification.longitude),
                'created_at': verification.created_at.isoformat()
            },
            'request': {
                'id': original_request.id,
                'requester_email': requester.email if requester else 'Unknown',
                'target_email': original_request.target_email,
                'status': original_request.status,
                'created_at': original_request.created_at.isoformat()
            }
        }
        
    except Exception as e:
        current_app.logger.error(f"Failed to retrieve verification for request {request_id} by user {current_user_id}: {str(e)}")
        return {'error': 'Failed to retrieve verification. Please try again.'}, 500