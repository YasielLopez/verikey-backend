import boto3
import uuid
import os
import base64
import io
from datetime import datetime, timedelta
from flask import current_app
from PIL import Image

class S3Service:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION')
        )
        self.bucket_name = os.getenv('AWS_S3_BUCKET')
    
    def upload_verification_photo(self, image_data, request_id, expiry_hours=24):
        try:
            if isinstance(image_data, str):
                if image_data.startswith('data:image'):
                    image_data = image_data.split(',')[1]
                
                image_bytes = base64.b64decode(image_data)
            else:
                image_bytes = image_data
            
            image_bytes = self._optimize_image(image_bytes)
            
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            filename = f"verification_{request_id}_{timestamp}_{uuid.uuid4().hex[:8]}.jpg"
            
            expires_at = datetime.utcnow() + timedelta(hours=expiry_hours)
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=filename,
                Body=image_bytes,
                ContentType='image/jpeg',
                Metadata={
                    'request_id': str(request_id),
                    'expires_hours': str(expiry_hours),
                    'expires_at': expires_at.isoformat(),
                    'uploaded_at': datetime.utcnow().isoformat(),
                    'purpose': 'verification_photo'
                }
            )
            
            photo_url = f"https://{self.bucket_name}.s3.{os.getenv('AWS_REGION')}.amazonaws.com/{filename}"
            
            current_app.logger.info(f"✅ Photo uploaded successfully: {filename}")
            return photo_url
            
        except Exception as e:
            current_app.logger.error(f"❌ S3 upload failed: {str(e)}")
            return None
    
    def _optimize_image(self, image_bytes, max_size=(800, 800), quality=85):
        try:
            img = Image.open(io.BytesIO(image_bytes))
            
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=quality, optimize=True)
            
            return output.getvalue()
            
        except Exception as e:
            current_app.logger.warning(f"Image optimization failed: {str(e)}, using original")
            return image_bytes
    
    def delete_photo(self, photo_url):
        try:
            filename = photo_url.split('/')[-1]
            
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=filename
            )
            
            current_app.logger.info(f"✅ Photo deleted: {filename}")
            return True
            
        except Exception as e:
            current_app.logger.error(f"❌ S3 delete failed: {str(e)}")
            return False
    
    def get_presigned_url(self, photo_url, expiration=3600):
        try:
            filename = photo_url.split('/')[-1]
            
            presigned_url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': filename},
                ExpiresIn=expiration
            )
            
            return presigned_url
            
        except Exception as e:
            current_app.logger.error(f"❌ Presigned URL generation failed: {str(e)}")
            return None
    
    def test_connection(self):
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                MaxKeys=1
            )
            
            current_app.logger.info("✅ S3 connection test successful")
            return True
            
        except Exception as e:
            current_app.logger.error(f"❌ S3 connection test failed: {str(e)}")
            return False

s3_service = S3Service()