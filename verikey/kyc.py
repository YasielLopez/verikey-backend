from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
import uuid
import json
import base64
import io
from verikey.models import db, User, KYCVerification
from verikey.decorators import token_required
from verikey.services.s3_service import s3_service

kyc_bp = Blueprint('kyc', __name__)

def process_image_upload(image_data):
    try:
        if not image_data:
            return None
        
        if isinstance(image_data, str) and image_data.startswith('data:image'):
            image_data = image_data.split(',')[1]
            
        return base64.b64decode(image_data)
        
        if isinstance(image_data, bytes):
            return image_data
            
        return base64.b64decode(image_data)
    except Exception as e:
        current_app.logger.error(f"Image processing failed: {str(e)}")
        return None

@kyc_bp.route('/kyc/verify', methods=['POST'])
@token_required
def submit_kyc_verification(current_user_id):
    try:
        if not request.is_json:
            return {'error': 'Request must be JSON'}, 400
            
        data = request.get_json()
        if not data:
            return {'error': 'No data provided'}, 400
            
        required_fields = ['document_type', 'manual_data']
        for field in required_fields:
            if field not in data:
                return {'error': f'{field} is required'}, 400
                
        user = User.query.get(current_user_id)
        if not user:
            return {'error': 'User not found'}, 404
            
        existing_verification = KYCVerification.query.filter_by(
            user_id=current_user_id
        ).filter(KYCVerification.status.in_(['pending', 'processing', 'approved', 'needs_review'])).first()
        
        if existing_verification:
            return {'error': f'You already have a {existing_verification.status} verification'}, 409
            
        verification_id = str(uuid.uuid4())
        kyc_verification = KYCVerification(
            user_id=current_user_id,
            verification_id=verification_id,
            document_type=data['document_type'],
            status='needs_review'
        )
        
        kyc_verification.set_manual_data(data['manual_data'])
        
        image_urls = {}
        
        if 'id_front_image' in data and data['id_front_image']:
            processed = process_image_upload(data['id_front_image'])
            if processed:
                url = s3_service.upload_verification_photo(processed, f"kyc_{verification_id}_front", 8760)
                if url:
                    kyc_verification.id_front_url = url
                    image_urls['id_front'] = url
                    
        if 'id_back_image' in data and data['id_back_image']:
            processed = process_image_upload(data['id_back_image'])
            if processed:
                url = s3_service.upload_verification_photo(processed, f"kyc_{verification_id}_back", 8760)
                if url:
                    kyc_verification.id_back_url = url
                    image_urls['id_back'] = url
                    
        if 'verification_selfie' in data and data['verification_selfie']:
            processed = process_image_upload(data['verification_selfie'])
            if processed:
                url = s3_service.upload_verification_photo(processed, f"kyc_{verification_id}_selfie", 8760)
                if url:
                    kyc_verification.selfie_url = url
                    image_urls['selfie'] = url
                    
        db.session.add(kyc_verification)
        db.session.commit()
        
        return {
            'message': 'KYC verification submitted successfully. Your submission will be reviewed.',
            'verification': kyc_verification.to_dict(),
            'images_uploaded': list(image_urls.keys())
        }, 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"KYC submission failed: {str(e)}")
        return {'error': 'Failed to process verification'}, 500

@kyc_bp.route('/kyc/status', methods=['GET'])
@token_required
def get_kyc_status(current_user_id):
    try:
        user = User.query.get(current_user_id)
        if not user:
            return {'error': 'User not found'}, 404
            
        latest = KYCVerification.query.filter_by(user_id=current_user_id)\
            .order_by(KYCVerification.created_at.desc()).first()
            
        if not latest:
            return {
                'verified': False,
                'status': 'not_started',
                'message': 'No verification submitted yet'
            }, 200
            
        return {
            'verified': user.is_verified,
            'verification': latest.to_dict(),
            'can_retry': latest.status == 'rejected',
            'next_steps': get_next_steps(latest.status)
        }, 200
        
    except Exception as e:
        current_app.logger.error(f"KYC status check failed: {str(e)}")
        return {'error': 'Failed to retrieve verification status'}, 500

@kyc_bp.route('/kyc/retry', methods=['POST'])
@token_required
def retry_kyc_verification(current_user_id):
    try:
        latest = KYCVerification.query.filter_by(user_id=current_user_id)\
            .order_by(KYCVerification.created_at.desc()).first()
            
        if not latest:
            return {'error': 'No previous verification found'}, 404
            
        if latest.status != 'rejected':
            return {'error': f'Cannot retry a {latest.status} verification'}, 400
            
        latest.status = 'superseded'
        db.session.commit()
        
        return {
            'message': 'You can now submit a new verification',
            'previous_verification': latest.to_dict()
        }, 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"KYC retry failed: {str(e)}")
        return {'error': 'Failed to process retry'}, 500

def get_next_steps(status):
    if status == 'pending':
        return "Your verification is in the queue for processing."
    elif status == 'processing':
        return "Your verification is currently being processed."
    elif status == 'needs_review':
        return "Your verification requires manual review."
    elif status == 'approved':
        return "Your identity has been successfully verified!"
    elif status == 'rejected':
        return "Your verification was rejected. You can retry with clearer photos."
    else:
        return "Unknown status."
    
