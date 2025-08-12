from datetime import datetime
from typing import Dict, List, Any, Optional
from verikey.models import User, ShareableKey, Request

class VerificationDataExtractor:
    
    @staticmethod
    def build_verification_data(
        user: User,
        information_types: List[str],
        submission_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        extractors = {
            'fullname': lambda: VerificationDataExtractor._extract_fullname(user),
            'firstname': lambda: VerificationDataExtractor._extract_firstname(user),
            'age': lambda: VerificationDataExtractor._extract_age(user),
            'location': lambda: VerificationDataExtractor._extract_location(submission_data),
            'selfie': lambda: VerificationDataExtractor._extract_image(submission_data, 'selfie'),
            'photo': lambda: VerificationDataExtractor._extract_image(submission_data, 'photo')
        }
        
        result = {}
        for info_type in information_types:
            if info_type in extractors:
                result[info_type] = extractors[info_type]()
        
        return result
    
    @staticmethod
    def _extract_fullname(user: User) -> str:
        if user.is_verified and user.verified_first_name and user.verified_last_name:
            return f"{user.verified_first_name} {user.verified_last_name}"
        elif user.first_name and user.last_name:
            return f"{user.first_name} {user.last_name}"
        elif user.first_name:
            return user.first_name
        return "Name not available"
    
    @staticmethod
    def _extract_firstname(user: User) -> str:
        if user.is_verified and user.verified_first_name:
            return user.verified_first_name
        return user.first_name or "First name not available"
    
    @staticmethod
    def _extract_age(user: User) -> str:
        if user.age:
            return str(user.age)
        elif user.verified_date_of_birth:
            today = datetime.now().date()
            age = today.year - user.verified_date_of_birth.year
            if today.month < user.verified_date_of_birth.month or \
               (today.month == user.verified_date_of_birth.month and 
                today.day < user.verified_date_of_birth.day):
                age -= 1
            return str(age)
        return "Age not provided"
    
    @staticmethod
    def _extract_location(submission_data: Dict[str, Any]) -> Dict[str, Any]:
        location_sources = [
            submission_data.get('location_data'),
            submission_data.get('user_data', {}).get('location'),
        ]
        
        for location_data in location_sources:
            if location_data and isinstance(location_data, dict):
                return {
                    'cityDisplay': location_data.get('cityDisplay', 'Location captured'),
                    'captured': True,
                }
        
        return {
            'cityDisplay': 'Location not captured',
            'captured': False
        }
    
    @staticmethod
    def _extract_image(submission_data: Dict[str, Any], image_type: str) -> Dict[str, Any]:
        image_key = f'{image_type}_data'
        if image_key in submission_data and submission_data[image_key]:
            return {
                'status': 'captured',
                'image_data': submission_data[image_key],
                'captured_at': datetime.utcnow().isoformat()
            }
        
        user_data = submission_data.get('user_data', {})
        if image_type in user_data and user_data[image_type]:
            image_data = user_data[image_type]
            if isinstance(image_data, dict):
                return image_data
            else:
                return {
                    'status': 'captured',
                    'image_data': image_data,
                    'captured_at': datetime.utcnow().isoformat()
                }
        
        return {
            'status': 'not_captured',
            'image_data': None
        }


class KeyStatusManager:
    
    @staticmethod
    def should_be_active(key: ShareableKey) -> bool:
        return (
            key.status != 'revoked' and 
            key.views_used < key.views_allowed
        )
    
    @staticmethod
    def update_status_if_needed(key: ShareableKey) -> bool:
        original_status = key.status
        
        if key.status == 'revoked':
            return False
        
        if key.views_used >= key.views_allowed:
            key.status = 'viewed_out'
        elif key.status == 'viewed_out' and key.views_used < key.views_allowed:
            key.status = 'active'
        
        return key.status != original_status
    
    @staticmethod
    def categorize_keys(keys: List[ShareableKey]) -> Dict[str, List[ShareableKey]]:
        active = []
        old = []
        
        for key in keys:
            KeyStatusManager.update_status_if_needed(key)
            
            if key.status == 'active':
                active.append(key)
            else:
                old.append(key)
        
        return {'active': active, 'old': old}


class RequestValidator:
    
    @staticmethod
    def validate_request_data(data: Dict[str, Any], mode: str = 'create') -> tuple[bool, str]:
        if not data.get('label'):
            return False, 'Label is required'
        
        if mode == 'create':
            if not data.get('target_email') and not data.get('is_shareable_link'):
                return False, 'Recipient is required'
        
        if not data.get('information_types'):
            return False, 'Information types are required'
        
        valid_types = {'fullname', 'firstname', 'age', 'location', 'selfie', 'photo'}
        info_types = data.get('information_types', [])
        
        if not isinstance(info_types, list):
            return False, 'Information types must be a list'
        
        if not all(t in valid_types for t in info_types):
            return False, 'Invalid information type'
        
        if 'fullname' in info_types and 'firstname' in info_types:
            return False, 'Cannot request both fullname and firstname'
        
        return True, ''
    
    @staticmethod
    def sanitize_request_data(data: Dict[str, Any]) -> Dict[str, Any]:
        sanitized = data.copy()
        
        if 'location_data' in sanitized:
            location = sanitized['location_data']
            if isinstance(location, dict):
                sanitized['location_data'] = {
                    'cityDisplay': location.get('cityDisplay', 'Location requested')
                }
        
        return sanitized