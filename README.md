# Verikey - Secure Identity Verification App

## Description

Verikey is a secure identity-sharing application designed to help people safely verify one another without giving up control of their private information. Whether you're meeting someone from a dating app, conducting a marketplace transaction, or working with clients, Verikey allows you to share verified details—like your name, age, location, and photos. 

### Key Features

- **🆔 Identity Verification**: Verify your identity using government-issued ID.
- **🔑 Temporary Access Keys**: Share information through secure, temporary "verikeys" with limited viewing permissions
- **📍 Location Verification**: Share city-level location to confirm proximity without revealing exact coordinates
- **📸 Secure Photo Sharing**: In-app photos with screenshot protection and no download capability
- **🔄 Mutual Verification**: Request verification from others and respond to requests
- **🛡️ Privacy-First Design**: Full control over what information is shared and for how long

## Tech Stack

### Backend
- **Framework**: Flask (Python)
- **Database**: PostgreSQL
- **Authentication**: JWT tokens with bcrypt password hashing
- **Cloud Services**: AWS S3 for photo storage, AWS SES for email notifications
- **ORM**: SQLAlchemy

### Frontend (Mobile)
- React Native (Expo)
- AsyncStorage for local data
- React Navigation

## Dependencies

### Python Backend Requirements
```
bcrypt==4.3.0
boto3==1.39.14
Flask==3.1.1
flask-cors==6.0.1
Flask-SQLAlchemy==3.1.1
Flask-Migrate==4.0.5
marshmallow==3.20.1
pillow==11.3.0
psycopg2-binary==2.9.10
PyJWT==2.8.0
python-dotenv==1.1.1
requests==2.32.4
SQLAlchemy==2.0.41
pytesseract==0.3.10
opencv-python==4.8.1.78
face-recognition==1.3.0
```

### Additional Services
- PostgreSQL database
- AWS S3 bucket for photo storage
- AWS SES for email notifications
- Twilio for SMS notifications (optional)

## Installation & Setup

### Prerequisites
- Python 3.8 or higher
- PostgreSQL 12 or higher
- Node.js 16+ and npm (for frontend)
- AWS account with S3 and SES configured
- Git

### Backend Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/YasielLopez/verikey-backend.git
   cd verikey
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   
   Create a `.env` file in the root directory with the following variables:
   ```env
   # Database
   DATABASE_URL=postgresql://username:password@localhost/verikey_db
   
   # Flask
   FLASK_ENV=development
   SECRET_KEY=your-secret-key-here
   
   # AWS Configuration
   AWS_ACCESS_KEY_ID=your-aws-access-key
   AWS_SECRET_ACCESS_KEY=your-aws-secret-key
   AWS_S3_BUCKET=your-s3-bucket-name
   AWS_REGION=us-east-2
   
   # Email service
   FROM_EMAIL=noreply@yourdomain.com
   
   # SMS service (optional)
   TWILIO_ACCOUNT_SID=your-twilio-sid
   TWILIO_AUTH_TOKEN=your-twilio-token
   TWILIO_PHONE_NUMBER=+1234567890
   
   # App settings
   APP_BASE_URL=http://127.0.0.1:5000
   BASE_URL=http://127.0.0.1:5000
   TESTING_MODE=false
   USE_SOFT_DELETE=true
   ```

5. **Set up the database**
   ```bash
   # Create PostgreSQL database
   createdb verikey_db
   
   # Run the Flask app to create tables
   python app.py
   ```

6. **Run the backend server**
   ```bash
   python app.py
   ```
   The API will be available at `http://127.0.0.1:5000`

### Frontend Setup (Mobile App)

1. **Navigate to frontend directory**
   ```bash
   cd frontend  # or wherever your React Native code is located
   ```

2. **Install dependencies**
   ```bash
   npm install
   # or
   yarn install
   ```

3. **Configure API endpoint**
   Update the API URL in your frontend configuration to point to your backend server.

4. **Run the mobile app**
   ```bash
   # For iOS
   npm run ios
   
   # For Android
   npm run android
   
   # For Expo
   expo start
   ```

### AWS Configuration

1. **S3 Bucket Setup**
   - Create an S3 bucket in your AWS account
   - Configure bucket permissions for photo uploads
   - Update the bucket name in your `.env` file

2. **SES Setup**
   - Verify your domain or email address in AWS SES
   - Move out of sandbox mode for production use
   - Update SES configuration in `.env` file

## API Endpoints

### Authentication
- `POST /auth/signup` - Create new account
- `POST /auth/login` - User login
- `GET /auth/verify` - Verify JWT token
- `POST /auth/logout` - User logout
- `POST /auth/refresh` - Refresh JWT token

### Profile Management
- `GET /profile` - Get user profile
- `POST /profile` - Update profile
- `POST /profile/photo` - Update profile photo
- `POST /profile/delete` - Delete account

### Verification Keys
- `GET /keys` - Get all keys (sent and received)
- `POST /keys` - Create new shareable key
- `GET /keys/<id>/details` - Get key details
- `POST /keys/<id>/revoke` - Revoke a key
- `DELETE /keys/<id>` - Delete a key

### Verification Requests
- `GET /requests` - Get all requests
- `POST /requests` - Create new request
- `PUT /requests/<id>` - Update request
- `DELETE /requests/<id>` - Delete request
- `POST /requests/<id>/deny` - Deny a request

### KYC Verification
- `POST /kyc/verify` - Submit KYC verification
- `GET /kyc/status` - Check verification status
- `POST /kyc/retry` - Retry failed verification

## Testing

Run the test suite:
```bash
python -m pytest tests/
```

## Use Cases

### 1. Online Marketplace Transactions
- Sellers can verify their identity and location to buyers
- Buyers can confirm sellers are legitimate and local
- Both parties maintain privacy while building trust

### 2. Dating App Meetings
- Exchange verified selfies and names before meeting
- Confirm the other person is who they claim to be
- Share location at city level for safety

### 3. Professional Services
- Service providers can verify client identity
- Clients can verify provider credentials
- Maintain professional boundaries while ensuring safety

## Security Features

- **Encrypted Storage**: All sensitive data encrypted at rest
- **Temporary Access**: Keys expire after set number of views
- **Screenshot Protection**: In-app photos cannot be screenshot
- **Revocable Access**: Users can revoke keys at any time
- **City-Level Location**: Never shares exact GPS coordinates
- **JWT Authentication**: Secure token-based authentication
- **Password Hashing**: Bcrypt for secure password storage

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## Future Enhancements

- [ ] Background check integration
- [ ] Verification tiers
- [ ] Mutual verification (reciprocal key exchange)
- [ ] Bulk verification requests

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For questions or support, please contact:
- Email: hello@verikey.app
