from flask import Blueprint, request, jsonify
from src.models.user import db
from src.models.customer import Customer, CustomerType
from src.routes.auth import token_required
from sqlalchemy import or_

customer_bp = Blueprint('customer', __name__)

@customer_bp.route('/', methods=['GET'])
@token_required
def get_customers(current_user):
    """Get all customers with optional filtering and pagination"""
    try:
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        search = request.args.get('search', '').strip()
        customer_type = request.args.get('type', '').strip()
        is_active = request.args.get('active', 'true').lower() == 'true'
        
        # Build query
        query = Customer.query.filter_by(is_active=is_active)
        
        # Apply customer type filter
        if customer_type and customer_type in [t.value for t in CustomerType]:
            query = query.filter_by(customer_type=CustomerType(customer_type))
        
        # Apply search filter
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    Customer.first_name.ilike(search_term),
                    Customer.last_name.ilike(search_term),
                    Customer.organization_name.ilike(search_term),
                    Customer.primary_email.ilike(search_term)
                )
            )
        
        # Order by creation date (newest first)
        query = query.order_by(Customer.created_at.desc())
        
        # Paginate results
        pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        customers = [customer.to_dict() for customer in pagination.items]
        
        return jsonify({
            'customers': customers,
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
        return jsonify({'error': 'Failed to retrieve customers', 'details': str(e)}), 500

@customer_bp.route('/<int:customer_id>', methods=['GET'])
@token_required
def get_customer(current_user, customer_id):
    """Get a specific customer by ID"""
    try:
        customer = Customer.query.get(customer_id)
        
        if not customer:
            return jsonify({'error': 'Customer not found'}), 404
        
        include_history = request.args.get('include_history', 'false').lower() == 'true'
        
        return jsonify({
            'customer': customer.to_dict(include_history=include_history)
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to retrieve customer', 'details': str(e)}), 500

@customer_bp.route('/', methods=['POST'])
@token_required
def create_customer(current_user):
    """Create a new customer"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        if not data.get('primary_email'):
            return jsonify({'error': 'Primary email is required'}), 400
        
        customer_type = data.get('customer_type', 'individual')
        if customer_type not in [t.value for t in CustomerType]:
            return jsonify({'error': 'Invalid customer type'}), 400
        
        # Check for duplicate email
        existing_customer = Customer.query.filter_by(
            primary_email=data['primary_email'].lower().strip()
        ).first()
        
        if existing_customer:
            return jsonify({'error': 'Customer with this email already exists'}), 400
        
        # Validate customer type specific requirements
        if customer_type == 'individual':
            if not data.get('first_name') or not data.get('last_name'):
                return jsonify({'error': 'First name and last name are required for individual customers'}), 400
        elif customer_type == 'organization':
            if not data.get('organization_name'):
                return jsonify({'error': 'Organization name is required for organization customers'}), 400
        
        # Create new customer
        customer = Customer(
            customer_type=CustomerType(customer_type),
            primary_email=data['primary_email'].lower().strip()
        )
        
        # Set customer type specific fields
        if customer_type == 'individual':
            customer.first_name = data.get('first_name', '').strip()
            customer.last_name = data.get('last_name', '').strip()
        else:
            customer.organization_name = data.get('organization_name', '').strip()
            customer.organization_type = data.get('organization_type', '').strip()
            customer.tax_id = data.get('tax_id', '').strip()
            customer.registration_number = data.get('registration_number', '').strip()
        
        # Set optional fields
        customer.secondary_email = data.get('secondary_email', '').strip() or None
        customer.phone_primary = data.get('phone_primary', '').strip() or None
        customer.phone_secondary = data.get('phone_secondary', '').strip() or None
        customer.website = data.get('website', '').strip() or None
        
        # Address information
        customer.address_line1 = data.get('address_line1', '').strip() or None
        customer.address_line2 = data.get('address_line2', '').strip() or None
        customer.city = data.get('city', '').strip() or None
        customer.state_province = data.get('state_province', '').strip() or None
        customer.postal_code = data.get('postal_code', '').strip() or None
        customer.country = data.get('country', '').strip() or None
        
        # Billing address (if different)
        customer.billing_address_line1 = data.get('billing_address_line1', '').strip() or None
        customer.billing_address_line2 = data.get('billing_address_line2', '').strip() or None
        customer.billing_city = data.get('billing_city', '').strip() or None
        customer.billing_state_province = data.get('billing_state_province', '').strip() or None
        customer.billing_postal_code = data.get('billing_postal_code', '').strip() or None
        customer.billing_country = data.get('billing_country', '').strip() or None
        
        # Preferences
        customer.preferred_currency = data.get('preferred_currency', 'USD')
        customer.preferred_language = data.get('preferred_language', 'en')
        customer.payment_terms = data.get('payment_terms', 30)
        
        # Communication preferences
        customer.email_notifications = data.get('email_notifications', True)
        customer.sms_notifications = data.get('sms_notifications', False)
        customer.whatsapp_notifications = data.get('whatsapp_notifications', False)
        
        # Notes
        customer.notes = data.get('notes', '').strip() or None
        
        db.session.add(customer)
        db.session.commit()
        
        return jsonify({
            'message': 'Customer created successfully',
            'customer': customer.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to create customer', 'details': str(e)}), 500

@customer_bp.route('/<int:customer_id>', methods=['PUT'])
@token_required
def update_customer(current_user, customer_id):
    """Update an existing customer"""
    try:
        customer = Customer.query.get(customer_id)
        
        if not customer:
            return jsonify({'error': 'Customer not found'}), 404
        
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Check for duplicate email (if email is being changed)
        if 'primary_email' in data:
            new_email = data['primary_email'].lower().strip()
            if new_email != customer.primary_email:
                existing_customer = Customer.query.filter_by(primary_email=new_email).first()
                if existing_customer:
                    return jsonify({'error': 'Customer with this email already exists'}), 400
                customer.primary_email = new_email
        
        # Update customer type specific fields
        if customer.customer_type == CustomerType.INDIVIDUAL:
            if 'first_name' in data:
                customer.first_name = data['first_name'].strip()
            if 'last_name' in data:
                customer.last_name = data['last_name'].strip()
        else:
            if 'organization_name' in data:
                customer.organization_name = data['organization_name'].strip()
            if 'organization_type' in data:
                customer.organization_type = data['organization_type'].strip()
            if 'tax_id' in data:
                customer.tax_id = data['tax_id'].strip() or None
            if 'registration_number' in data:
                customer.registration_number = data['registration_number'].strip() or None
        
        # Update contact information
        if 'secondary_email' in data:
            customer.secondary_email = data['secondary_email'].strip() or None
        if 'phone_primary' in data:
            customer.phone_primary = data['phone_primary'].strip() or None
        if 'phone_secondary' in data:
            customer.phone_secondary = data['phone_secondary'].strip() or None
        if 'website' in data:
            customer.website = data['website'].strip() or None
        
        # Update address information
        address_fields = [
            'address_line1', 'address_line2', 'city', 'state_province', 
            'postal_code', 'country', 'billing_address_line1', 'billing_address_line2',
            'billing_city', 'billing_state_province', 'billing_postal_code', 'billing_country'
        ]
        
        for field in address_fields:
            if field in data:
                setattr(customer, field, data[field].strip() or None)
        
        # Update preferences
        if 'preferred_currency' in data:
            customer.preferred_currency = data['preferred_currency']
        if 'preferred_language' in data:
            customer.preferred_language = data['preferred_language']
        if 'payment_terms' in data:
            customer.payment_terms = data['payment_terms']
        
        # Update communication preferences
        if 'email_notifications' in data:
            customer.email_notifications = data['email_notifications']
        if 'sms_notifications' in data:
            customer.sms_notifications = data['sms_notifications']
        if 'whatsapp_notifications' in data:
            customer.whatsapp_notifications = data['whatsapp_notifications']
        
        # Update notes
        if 'notes' in data:
            customer.notes = data['notes'].strip() or None
        
        # Update status
        if 'is_active' in data:
            customer.is_active = data['is_active']
        
        db.session.commit()
        
        return jsonify({
            'message': 'Customer updated successfully',
            'customer': customer.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to update customer', 'details': str(e)}), 500

@customer_bp.route('/<int:customer_id>', methods=['DELETE'])
@token_required
def delete_customer(current_user, customer_id):
    """Soft delete a customer (deactivate)"""
    try:
        customer = Customer.query.get(customer_id)
        
        if not customer:
            return jsonify({'error': 'Customer not found'}), 404
        
        # Check if customer has active invoices
        from src.models.invoice import Invoice, InvoiceStatus
        active_invoices = Invoice.query.filter_by(customer_id=customer_id).filter(
            Invoice.status.in_([InvoiceStatus.DRAFT, InvoiceStatus.SENT])
        ).count()
        
        if active_invoices > 0:
            return jsonify({
                'error': 'Cannot delete customer with active invoices',
                'active_invoices': active_invoices
            }), 400
        
        # Soft delete (deactivate)
        customer.is_active = False
        db.session.commit()
        
        return jsonify({'message': 'Customer deactivated successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to delete customer', 'details': str(e)}), 500

@customer_bp.route('/search', methods=['GET'])
@token_required
def search_customers(current_user):
    """Search customers by various criteria"""
    try:
        query = request.args.get('q', '').strip()
        customer_type = request.args.get('type', '').strip()
        limit = min(request.args.get('limit', 10, type=int), 50)
        
        if not query:
            return jsonify({'customers': []}), 200
        
        # Use the Customer.search class method
        search_query = Customer.search(
            query=query,
            customer_type=CustomerType(customer_type) if customer_type and customer_type in [t.value for t in CustomerType] else None
        )
        
        customers = search_query.limit(limit).all()
        
        return jsonify({
            'customers': [customer.to_dict() for customer in customers]
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Search failed', 'details': str(e)}), 500

