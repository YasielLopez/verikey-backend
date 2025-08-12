import os
import re
import boto3
from botocore.exceptions import ClientError
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self):
        self.aws_region = os.getenv('AWS_REGION', 'us-east-2')
        try:
            self.ses_client = boto3.client(
                'ses',
                region_name=self.aws_region,
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
            )
        except Exception as e:
            logger.warning(f"Failed to initialize SES client: {e}")
            self.ses_client = None
        
        self.app_base_url = os.getenv('APP_BASE_URL', 'http://127.0.0.1:5000')
        self.from_email = os.getenv('FROM_EMAIL', 'noreply@verikey.app')

    def identify_recipient_type(self, recipient: str) -> str:
        if '@' in recipient:
            return 'email'
        else:
            return 'unknown'

    async def send_verification_request(self, 
                                      recipient: str, 
                                      requester_name: str,
                                      request_label: str,
                                      information_types: list,
                                      request_id: Optional[int] = None,
                                      shareable_url: Optional[str] = None) -> Dict[str, Any]:
        
        if '@' in recipient:
            return await self._send_ses_email_request(
                recipient, requester_name, request_label, 
                information_types, request_id, shareable_url
            )
        else:
            return {"status": "failed", "error": "Unsupported recipient type"}

    async def _send_ses_email_request(self, email: str, requester_name: str, 
                                    request_label: str, information_types: list,
                                    request_id: Optional[int] = None,
                                    shareable_url: Optional[str] = None) -> Dict[str, Any]:
        if not self.ses_client:
            logger.warning("SES not configured, skipping email")
            return {"status": "skipped", "reason": "ses_service_not_configured"}

        try:
            if shareable_url:
                action_url = shareable_url
                action_text = "Respond to Request"
            else:
                action_url = f"{self.app_base_url}/respond/{request_id}"
                action_text = "Open VeriKey App"

            info_list = ", ".join(information_types)
            
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>VeriKey Verification Request</title>
            </head>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: #b5ead7; padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                    <h1 style="margin: 0; color: #1f2937; font-size: 28px;">🔐 VeriKey Request</h1>
                </div>
                
                <div style="background: white; padding: 40px; border: 1px solid #e5e7eb; border-radius: 0 0 10px 10px;">
                    <h2 style="color: #1f2937; margin-bottom: 20px;">Verification Request: {request_label}</h2>
                    
                    <p style="font-size: 18px; color: #374151; margin-bottom: 25px;">
                        <strong>{requester_name}</strong> has requested verification of your:
                    </p>
                    
                    <div style="background: #f3f4f6; padding: 20px; border-radius: 8px; margin: 25px 0;">
                        <ul style="margin: 0; padding-left: 25px; color: #1f2937;">
                            {"".join(f"<li style='margin-bottom: 8px;'>{info_type.replace('_', ' ').title()}</li>" for info_type in information_types)}
                        </ul>
                    </div>
                    
                    <p style="color: #6b7280; margin-bottom: 30px;">
                        This request is secure and your information will only be shared with {requester_name}.
                    </p>
                    
                    <div style="text-align: center; margin: 40px 0;">
                        <a href="{action_url}" 
                           style="background: #FFD66B; color: #1f2937; padding: 16px 32px; 
                                  text-decoration: none; border-radius: 25px; font-weight: bold;
                                  display: inline-block; font-size: 18px;">
                            {action_text}
                        </a>
                    </div>
                    
                    <div style="border-top: 1px solid #e5e7eb; padding-top: 25px; margin-top: 40px;">
                        <p style="font-size: 14px; color: #9ca3af; text-align: center; margin: 0;">
                            This request was sent through VeriKey, a secure identity verification platform.<br>
                            If you did not expect this request, you can safely ignore this email.
                        </p>
                    </div>
                </div>
            </body>
            </html>
            """

            response = self.ses_client.send_email(
                Source=self.from_email,
                Destination={'ToAddresses': [email]},
                Message={
                    'Subject': {
                        'Data': f'Verification Request: {request_label}',
                        'Charset': 'UTF-8'
                    },
                    'Body': {
                        'Html': {
                            'Data': html_content,
                            'Charset': 'UTF-8'
                        }
                    }
                }
            )

            logger.info(f"SES email sent successfully to {email}")
            
            return {
                "status": "sent",
                "method": "ses_email",
                "recipient": email,
                "message_id": response['MessageId']
            }

        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            logger.error(f"SES error sending to {email}: {error_code} - {error_message}")
            return {"status": "failed", "method": "ses_email", "error": f"SES error: {error_code}"}
        except Exception as e:
            logger.error(f"Unexpected error sending SES email to {email}: {str(e)}")
            return {"status": "failed", "method": "ses_email", "error": str(e)}

    async def send_verification_response_notification(self, *args, **kwargs):
        return {"status": "not_implemented"}
    
    async def send_verification_denial_notification(self, *args, **kwargs):
        return {"status": "not_implemented"}

notification_service = NotificationService()