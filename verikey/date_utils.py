from datetime import datetime, timezone
from typing import Optional, Dict, Any

class DateFormatter:
    
    DISPLAY_FORMAT = '%m/%d/%Y at %I:%M %p'
    
    @staticmethod
    def format_datetime(dt: Optional[datetime]) -> Dict[str, Optional[str]]:

        if not dt:
            return {
                'iso': None,
                'display': 'Unknown',
                'relative': 'Unknown'
            }
        
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        
        return {
            'iso': dt.isoformat(),
            'display': dt.strftime(DateFormatter.DISPLAY_FORMAT),
            'relative': DateFormatter.get_relative_time(dt)
        }
    
    @staticmethod
    def get_relative_time(dt: datetime) -> str:
        if not dt:
            return 'Unknown'
        
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        
        now = datetime.now(timezone.utc)
        diff = now - dt
        
        seconds = diff.total_seconds()
        
        if seconds < 60:
            return 'Just now'
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f'{minutes} minute{"s" if minutes != 1 else ""} ago'
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f'{hours} hour{"s" if hours != 1 else ""} ago'
        elif seconds < 604800:
            days = int(seconds / 86400)
            if days == 1:
                return 'Yesterday'
            return f'{days} days ago'
        else:
            return dt.strftime('%b %d, %Y')
    
    @staticmethod
    def parse_date_string(date_str: str) -> Optional[datetime]:
        if not date_str:
            return None
        
        formats = [
            '%Y-%m-%dT%H:%M:%S.%fZ',
            '%Y-%m-%dT%H:%M:%S%z',
            '%Y-%m-%d %H:%M:%S',
            '%m/%d/%Y',
            '%Y-%m-%d'
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
        
        return None


def enhance_model_serialization():

    from verikey.models import User, ShareableKey, Request, KYCVerification
    
    def user_to_dict_enhanced(self):
        base_dict = self.to_dict()
        
        base_dict['created_at_formatted'] = DateFormatter.format_datetime(self.created_at)
        base_dict['last_login_formatted'] = DateFormatter.format_datetime(self.last_login)
        base_dict['verified_at_formatted'] = DateFormatter.format_datetime(self.verified_at)
        
        return base_dict
    
    User.to_dict_enhanced = user_to_dict_enhanced
    
    def key_to_dict_enhanced(self, include_user_data=False):
        base_dict = self.to_dict(include_user_data)
        
        base_dict['created_at_formatted'] = DateFormatter.format_datetime(self.created_at)
        base_dict['last_viewed_at_formatted'] = DateFormatter.format_datetime(self.last_viewed_at)
        
        base_dict['is_expired'] = self.views_used >= self.views_allowed
        base_dict['is_active'] = self.status == 'active' and not base_dict['is_expired']
        
        return base_dict
    
    ShareableKey.to_dict_enhanced = key_to_dict_enhanced
    
    def request_to_dict_enhanced(self):
        base_dict = {
            'id': self.id,
            'label': self.label,
            'status': self.status,
            'notes': self.notes,
            'information_types': self.get_information_types(),
            'requester_id': self.requester_id,
            'target_user_id': self.target_user_id,
            'target_email': self.target_email
        }
        
        base_dict['created_at_formatted'] = DateFormatter.format_datetime(self.created_at)
        base_dict['response_at_formatted'] = DateFormatter.format_datetime(self.response_at)
        
        return base_dict
    
    Request.to_dict_enhanced = request_to_dict_enhanced


@keys_bp.route('/keys', methods=['GET'])
@token_required
def get_all_keys_enhanced(current_user_id):
    try:
        
        sent_keys_ui = []
        for key in sent_keys:
            key_dict = key.to_dict_enhanced()
            
            recipient = User.query.get(key.recipient_user_id) if key.recipient_user_id else None
            key_dict['recipient'] = {
                'name': format_recipient_name(recipient, key),
                'avatar': recipient.profile_image_url if recipient else None
            }
            
            sent_keys_ui.append(key_dict)
        
        
        return {
            'sent_keys': sent_keys_ui,
            'received_keys': received_keys_ui,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }, 200
        
    except Exception as e: