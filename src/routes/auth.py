from flask import Blueprint, request, jsonify, current_app
from src.models.user import db, User
from functools import wraps
import jwt
from datetime import datetime

auth_bp = Blueprint('auth', __name__)

def token_required(f):
    """Decorator to require valid JWT token"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Get token from Authorization header
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(" ")[1]  # Bearer <token>
            except IndexError:
                return jsonify({'error': 'Invalid token format'}), 401
        
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        
        try:
            current_user = User.verify_jwt_token(token, current_app.config['SECRET_KEY'])
            if not current_user:
                return jsonify({'error': 'Token is invalid or expired'}), 401
        except Exception as e:
            return jsonify({'error': 'Token verification failed'}), 401
        
        return f(current_user, *args, **kwargs)
    
    return decorated

def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated(current_user, *args, **kwargs):
        if not current_user.is_admin():
            return jsonify({'error': 'Admin access required'}), 403
        return f(current_user, *args, **kwargs)
    
    return decorated

@auth_bp.route('/login', methods=['POST'])
def login():
    """User login endpoint"""
    try:
        data = request.get_json()
        
        if not data or not data.get('email') or not data.get('password'):
            return jsonify({'error': 'Email and password are required'}), 400
        
        email = data['email'].lower().strip()
        password = data['password']
        
        # Find user by email
        user = User.query.filter_by(email=email).first()
        
        if not user:
            return jsonify({'error': 'Invalid email or password'}), 401
        
        # Check if account is locked
        if user.is_account_locked():
            return jsonify({
                'error': 'Account is temporarily locked due to multiple failed login attempts',
                'locked_until': user.account_locked_until.isoformat() if user.account_locked_until else None
            }), 423
        
        # Check if account is active
        if not user.is_active:
            return jsonify({'error': 'Account is deactivated'}), 401
        
        # Verify password
        if not user.check_password(password):
            user.increment_failed_login()
            db.session.commit()
            
            return jsonify({'error': 'Invalid email or password'}), 401
        
        # Successful login
        user.reset_failed_login()
        db.session.commit()
        
        # Generate JWT tokens
        access_token = user.generate_jwt_token(current_app.config['SECRET_KEY'], expires_in=3600)  # 1 hour
        refresh_token = user.generate_jwt_token(current_app.config['SECRET_KEY'], expires_in=86400)  # 24 hours
        
        return jsonify({
            'message': 'Login successful',
            'user': user.to_dict(),
            'access_token': access_token,
            'refresh_token': refresh_token,
            'expires_in': 3600
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Login failed', 'details': str(e)}), 500

@auth_bp.route('/refresh', methods=['POST'])
def refresh_token():
    """Refresh access token using refresh token"""
    try:
        data = request.get_json()
        
        if not data or not data.get('refresh_token'):
            return jsonify({'error': 'Refresh token is required'}), 400
        
        refresh_token = data['refresh_token']
        
        # Verify refresh token
        user = User.verify_jwt_token(refresh_token, current_app.config['SECRET_KEY'])
        
        if not user:
            return jsonify({'error': 'Invalid or expired refresh token'}), 401
        
        # Generate new access token
        access_token = user.generate_jwt_token(current_app.config['SECRET_KEY'], expires_in=3600)
        
        return jsonify({
            'access_token': access_token,
            'expires_in': 3600
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Token refresh failed', 'details': str(e)}), 500

@auth_bp.route('/logout', methods=['POST'])
@token_required
def logout(current_user):
    """User logout endpoint"""
    # In a production system, you would typically blacklist the token
    # For now, we'll just return a success message
    return jsonify({'message': 'Logout successful'}), 200

@auth_bp.route('/profile', methods=['GET'])
@token_required
def get_profile(current_user):
    """Get current user profile"""
    return jsonify({
        'user': current_user.to_dict()
    }), 200

@auth_bp.route('/profile', methods=['PUT'])
@token_required
def update_profile(current_user):
    """Update current user profile"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Update allowed fields
        if 'first_name' in data:
            current_user.first_name = data['first_name'].strip()
        
        if 'last_name' in data:
            current_user.last_name = data['last_name'].strip()
        
        # Email update requires additional verification in production
        if 'email' in data and current_user.is_admin():
            new_email = data['email'].lower().strip()
            existing_user = User.query.filter_by(email=new_email).first()
            if existing_user and existing_user.id != current_user.id:
                return jsonify({'error': 'Email already exists'}), 400
            current_user.email = new_email
        
        db.session.commit()
        
        return jsonify({
            'message': 'Profile updated successfully',
            'user': current_user.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Profile update failed', 'details': str(e)}), 500

@auth_bp.route('/change-password', methods=['POST'])
@token_required
def change_password(current_user):
    """Change user password"""
    try:
        data = request.get_json()
        
        if not data or not data.get('current_password') or not data.get('new_password'):
            return jsonify({'error': 'Current password and new password are required'}), 400
        
        current_password = data['current_password']
        new_password = data['new_password']
        
        # Verify current password
        if not current_user.check_password(current_password):
            return jsonify({'error': 'Current password is incorrect'}), 400
        
        # Validate new password strength (basic validation)
        if len(new_password) < 8:
            return jsonify({'error': 'New password must be at least 8 characters long'}), 400
        
        # Update password
        current_user.set_password(new_password)
        db.session.commit()
        
        return jsonify({'message': 'Password changed successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Password change failed', 'details': str(e)}), 500

@auth_bp.route('/verify-token', methods=['POST'])
def verify_token():
    """Verify if a token is valid"""
    try:
        data = request.get_json()
        
        if not data or not data.get('token'):
            return jsonify({'error': 'Token is required'}), 400
        
        token = data['token']
        user = User.verify_jwt_token(token, current_app.config['SECRET_KEY'])
        
        if user:
            return jsonify({
                'valid': True,
                'user': user.to_dict()
            }), 200
        else:
            return jsonify({'valid': False}), 200
            
    except Exception as e:
        return jsonify({'error': 'Token verification failed', 'details': str(e)}), 500

