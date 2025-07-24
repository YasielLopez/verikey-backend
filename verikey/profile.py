from flask import Blueprint, request, jsonify, current_app
import re
import base64
import uuid
import os
from datetime import datetime
from verikey import db
from verikey.models import User
from verikey.auth import token_required

# Create blueprint
profile_bp = Blueprint('profile', __name__, url_prefix='/api')

def validate_screen_name(screen_name):
    """Validate screen name format"""
    if not screen_name:
        return False, "Screen name is required"
    
    # Remove @ if user included it
    if screen_name.startswith('@'):
        screen_name = screen_name[1:]
    
    # Check length
    if len(screen_name) < 3 or len(screen_name) > 30:
        return False, "Screen name must be between 3 and 30 characters"
    
    # Check format: alphanumeric + underscore + dot, no spaces
    if not re.match(r'^[a-zA-Z0-9_.]+$', screen_name):
        return False, "Screen name can only contain letters, numbers, underscores, and dots"
    
    # Can't start or end with special characters
    if screen_name.startswith(('.', '_')) or screen_name.endswith(('.', '_')):
        return False, "Screen name cannot start or end with dots or underscores"
    
    return True, screen_name

def validate_name(name, field_name):
    """Validate first/last name"""
    if not name:
        return False, f"{field_name} is required"
    
    name = name.strip()
    if len(name) < 1 or len(name) > 50:
        return False, f"{field_name} must be between 1 and 50 characters"
    
    # Allow letters, spaces, hyphens, apostrophes
    if not re.match(r"^[a-zA-Z\s\-']+$", name):
        return False, f"{field_name} can only contain letters, spaces, hyphens, and apostrophes"
    
    return True, name

def save_profile_image(image_data, user_id):
    """
    Save profile image (placeholder implementation)
    For MVP: accept base64 or URL
    Later: implement proper file upload to S3
    """
    try:
        if not image_data:
            return None
        
        # If it's already a URL, return as-is
        if image_data.startswith(('http://', 'https://')):
            return image_data
        
        # If it's base64, save it (placeholder - in production, upload to S3)
        if image_data.startswith('data:image/'):
            # For now, just generate a placeholder URL
            # In production, decode base64 and upload to S3
            filename = f"profile_{user_id}_{uuid.uuid4().hex[:8]}.jpg"
            placeholder_url = f"https://placeholder.api/profiles/{filename}"
            
            current_app.logger.info(f"Profile image saved (placeholder): {placeholder_url}")
            return placeholder_url
        
        # If it's some other format, treat as URL
        return image_data
        
    except Exception as e:
        current_app.logger.error(f"Profile image save failed: {str(e)}")
        return None

@profile_bp.route('/profile', methods=['GET'])
@token_required
def get_profile(current_user_id):
    """Get current user's profile information"""
    try:
        user = User.query.get(current_user_id)
        if not user:
            return {'error': 'User not found'}, 404
        
        current_app.logger.info(f"Profile retrieved for user {current_user_id}")
        
        return {
            'profile': user.to_dict(),
            'message': 'Profile retrieved successfully'
        }, 200
        
    except Exception as e:
        current_app.logger.error(f"Failed to get profile for user {current_user_id}: {str(e)}")
        return {'error': 'Failed to retrieve profile'}, 500

@profile_bp.route('/profile', methods=['POST'])
@token_required
def create_profile(current_user_id):
    """Create or update user profile"""
    try:
        # Validate request has JSON data
        if not request.is_json:
            return {'error': 'Request must be JSON'}, 400
        
        data = request.get_json()
        if not data:
            return {'error': 'No data provided'}, 400
        
        user = User.query.get(current_user_id)
        if not user:
            return {'error': 'User not found'}, 404
        
        # Validate required fields
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        screen_name = data.get('screen_name', '').strip()
        profile_image = data.get('profile_image')  # Optional
        
        # Validate first name
        is_valid, first_name_or_error = validate_name(first_name, "First name")
        if not is_valid:
            return {'error': first_name_or_error}, 400
        
        # Validate last name
        is_valid, last_name_or_error = validate_name(last_name, "Last name")
        if not is_valid:
            return {'error': last_name_or_error}, 400
        
        # Validate screen name
        is_valid, screen_name_or_error = validate_screen_name(screen_name)
        if not is_valid:
            return {'error': screen_name_or_error}, 400
        screen_name = screen_name_or_error
        
        # Check if screen name is already taken (by another user)
        existing_user = User.query.filter_by(screen_name=screen_name).first()
        if existing_user and existing_user.id != current_user_id:
            return {'error': 'Screen name already taken'}, 409
        
        # Handle profile image
        profile_image_url = None
        if profile_image:
            profile_image_url = save_profile_image(profile_image, current_user_id)
            if not profile_image_url:
                return {'error': 'Failed to process profile image'}, 400
        
        # Update user profile
        user.first_name = first_name
        user.last_name = last_name
        user.screen_name = screen_name
        user.profile_updated_at = datetime.utcnow()
        user.profile_completed = True
        
        if profile_image_url:
            user.profile_image_url = profile_image_url
        
        db.session.commit()
        
        current_app.logger.info(f"✅ Profile created/updated for user {current_user_id}: @{screen_name}")
        
        return {
            'message': 'Profile updated successfully',
            'profile': user.to_dict()
        }, 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Profile creation failed for user {current_user_id}: {str(e)}")
        return {'error': 'Failed to create profile. Please try again.'}, 500

@profile_bp.route('/profile', methods=['PUT'])
@token_required
def update_profile(current_user_id):
    """Update existing profile (same as POST for simplicity)"""
    return create_profile(current_user_id)

@profile_bp.route('/profile/check-screen-name', methods=['POST'])
@token_required
def check_screen_name_availability(current_user_id):
    """Check if a screen name is available"""
    try:
        if not request.is_json:
            return {'error': 'Request must be JSON'}, 400
        
        data = request.get_json()
        screen_name = data.get('screen_name', '').strip()
        
        if not screen_name:
            return {'error': 'Screen name is required'}, 400
        
        # Validate format
        is_valid, screen_name_or_error = validate_screen_name(screen_name)
        if not is_valid:
            return {
                'available': False,
                'error': screen_name_or_error
            }, 200
        
        screen_name = screen_name_or_error
        
        # Check availability
        existing_user = User.query.filter_by(screen_name=screen_name).first()
        is_available = not existing_user or existing_user.id == current_user_id
        
        return {
            'available': is_available,
            'screen_name': screen_name,
            'message': 'Screen name is available' if is_available else 'Screen name is already taken'
        }, 200
        
    except Exception as e:
        current_app.logger.error(f"Screen name check failed: {str(e)}")
        return {'error': 'Failed to check screen name availability'}, 500

@profile_bp.route('/profile/image', methods=['POST'])
@token_required
def update_profile_image(current_user_id):
    """Update just the profile image"""
    try:
        if not request.is_json:
            return {'error': 'Request must be JSON'}, 400
        
        data = request.get_json()
        profile_image = data.get('profile_image')
        
        if not profile_image:
            return {'error': 'Profile image data is required'}, 400
        
        user = User.query.get(current_user_id)
        if not user:
            return {'error': 'User not found'}, 404
        
        # Save the image
        image_url = save_profile_image(profile_image, current_user_id)
        if not image_url:
            return {'error': 'Failed to process profile image'}, 400
        
        # Update user
        user.profile_image_url = image_url
        user.profile_updated_at = datetime.utcnow()
        db.session.commit()
        
        current_app.logger.info(f"✅ Profile image updated for user {current_user_id}")
        
        return {
            'message': 'Profile image updated successfully',
            'profile_image_url': image_url
        }, 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Profile image update failed for user {current_user_id}: {str(e)}")
        return {'error': 'Failed to update profile image'}, 500