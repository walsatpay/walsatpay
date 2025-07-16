from flask import Blueprint, jsonify, request
from src.models.user import User, UserRole, db
from src.routes.auth import token_required, admin_required

user_bp = Blueprint('user', __name__)

@user_bp.route('/', methods=['GET'])
@token_required
@admin_required
def get_users(current_user):
    """Get all users (admin only)"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        search = request.args.get('search', '').strip()
        role = request.args.get('role', '').strip()
        is_active = request.args.get('active', 'true').lower() == 'true'
        
        # Build query
        query = User.query.filter_by(is_active=is_active)
        
        # Apply role filter
        if role and role in [r.value for r in UserRole]:
            query = query.filter_by(role=UserRole(role))
        
        # Apply search filter
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                db.or_(
                    User.first_name.ilike(search_term),
                    User.last_name.ilike(search_term),
                    User.email.ilike(search_term)
                )
            )
        
        # Order by creation date (newest first)
        query = query.order_by(User.created_at.desc())
        
        # Paginate results
        pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        users = [user.to_dict() for user in pagination.items]
        
        return jsonify({
            'users': users,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': pagination.total,
                'pages': pagination.pages,
                'has_next': pagination.has_next,
                'has_prev': pagination.has_prev
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to retrieve users', 'details': str(e)}), 500

@user_bp.route('/', methods=['POST'])
@token_required
@admin_required
def create_user(current_user):
    """Create a new user (admin only)"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        required_fields = ['email', 'password', 'first_name', 'last_name']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=data['email'].lower().strip()).first()
        if existing_user:
            return jsonify({'error': 'User with this email already exists'}), 400
        
        # Validate role
        role = data.get('role', 'staff')
        if role not in [r.value for r in UserRole]:
            return jsonify({'error': 'Invalid role'}), 400
        
        # Create new user
        user = User(
            email=data['email'].lower().strip(),
            first_name=data['first_name'].strip(),
            last_name=data['last_name'].strip(),
            role=UserRole(role)
        )
        
        user.set_password(data['password'])
        
        db.session.add(user)
        db.session.commit()
        
        return jsonify({
            'message': 'User created successfully',
            'user': user.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to create user', 'details': str(e)}), 500

@user_bp.route('/<int:user_id>', methods=['GET'])
@token_required
@admin_required
def get_user(current_user, user_id):
    """Get a specific user by ID (admin only)"""
    try:
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        include_sensitive = request.args.get('include_sensitive', 'false').lower() == 'true'
        
        return jsonify({
            'user': user.to_dict(include_sensitive=include_sensitive)
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to retrieve user', 'details': str(e)}), 500

@user_bp.route('/<int:user_id>', methods=['PUT'])
@token_required
@admin_required
def update_user(current_user, user_id):
    """Update a user (admin only)"""
    try:
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Update basic fields
        if 'first_name' in data:
            user.first_name = data['first_name'].strip()
        
        if 'last_name' in data:
            user.last_name = data['last_name'].strip()
        
        # Update email (check for duplicates)
        if 'email' in data:
            new_email = data['email'].lower().strip()
            if new_email != user.email:
                existing_user = User.query.filter_by(email=new_email).first()
                if existing_user:
                    return jsonify({'error': 'User with this email already exists'}), 400
                user.email = new_email
        
        # Update role
        if 'role' in data:
            role = data['role']
            if role not in [r.value for r in UserRole]:
                return jsonify({'error': 'Invalid role'}), 400
            user.role = UserRole(role)
        
        # Update active status
        if 'is_active' in data:
            user.is_active = data['is_active']
        
        # Update password if provided
        if 'password' in data and data['password']:
            user.set_password(data['password'])
        
        # Unlock account if requested
        if data.get('unlock_account'):
            user.unlock_account()
        
        db.session.commit()
        
        return jsonify({
            'message': 'User updated successfully',
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to update user', 'details': str(e)}), 500

@user_bp.route('/<int:user_id>', methods=['DELETE'])
@token_required
@admin_required
def delete_user(current_user, user_id):
    """Soft delete a user (deactivate) (admin only)"""
    try:
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Prevent self-deletion
        if user.id == current_user.id:
            return jsonify({'error': 'Cannot delete your own account'}), 400
        
        # Soft delete (deactivate)
        user.is_active = False
        db.session.commit()
        
        return jsonify({'message': 'User deactivated successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to delete user', 'details': str(e)}), 500

