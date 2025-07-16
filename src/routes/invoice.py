from flask import Blueprint, request, jsonify
from src.models.user import db
from src.models.customer import Customer
from src.models.invoice import Invoice, InvoiceLineItem, InvoiceStatus, InvoiceStatusHistory
from src.routes.auth import token_required
from datetime import datetime, timedelta
from sqlalchemy import or_, and_

invoice_bp = Blueprint('invoice', __name__)

@invoice_bp.route('/', methods=['GET'])
@token_required
def get_invoices(current_user):
    """Get all invoices with optional filtering and pagination"""
    try:
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        search = request.args.get('search', '').strip()
        status = request.args.get('status', '').strip()
        customer_id = request.args.get('customer_id', type=int)
        date_from = request.args.get('date_from', '').strip()
        date_to = request.args.get('date_to', '').strip()
        
        # Build query
        query = Invoice.query
        
        # Apply status filter
        if status and status in [s.value for s in InvoiceStatus]:
            query = query.filter_by(status=InvoiceStatus(status))
        
        # Apply customer filter
        if customer_id:
            query = query.filter_by(customer_id=customer_id)
        
        # Apply date range filter
        if date_from:
            try:
                from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
                query = query.filter(Invoice.issue_date >= from_date)
            except ValueError:
                return jsonify({'error': 'Invalid date_from format. Use YYYY-MM-DD'}), 400
        
        if date_to:
            try:
                to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
                query = query.filter(Invoice.issue_date <= to_date)
            except ValueError:
                return jsonify({'error': 'Invalid date_to format. Use YYYY-MM-DD'}), 400
        
        # Apply search filter
        if search:
            search_term = f"%{search}%"
            query = query.join(Customer).filter(
                or_(
                    Invoice.invoice_number.ilike(search_term),
                    Invoice.reference_number.ilike(search_term),
                    Invoice.po_number.ilike(search_term),
                    Customer.first_name.ilike(search_term),
                    Customer.last_name.ilike(search_term),
                    Customer.organization_name.ilike(search_term),
                    Customer.primary_email.ilike(search_term)
                )
            )
        
        # Order by creation date (newest first)
        query = query.order_by(Invoice.created_at.desc())
        
        # Paginate results
        pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        invoices = [invoice.to_dict(include_line_items=False) for invoice in pagination.items]
        
        return jsonify({
            'invoices': invoices,
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
        return jsonify({'error': 'Failed to retrieve invoices', 'details': str(e)}), 500

@invoice_bp.route('/<int:invoice_id>', methods=['GET'])
@token_required
def get_invoice(current_user, invoice_id):
    """Get a specific invoice by ID"""
    try:
        invoice = Invoice.query.get(invoice_id)
        
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404
        
        include_payments = request.args.get('include_payments', 'false').lower() == 'true'
        include_history = request.args.get('include_history', 'false').lower() == 'true'
        
        return jsonify({
            'invoice': invoice.to_dict(
                include_line_items=True,
                include_payments=include_payments,
                include_history=include_history
            )
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to retrieve invoice', 'details': str(e)}), 500

@invoice_bp.route('/', methods=['POST'])
@token_required
def create_invoice(current_user):
    """Create a new invoice"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        if not data.get('customer_id'):
            return jsonify({'error': 'Customer ID is required'}), 400
        
        if not data.get('line_items') or not isinstance(data['line_items'], list):
            return jsonify({'error': 'At least one line item is required'}), 400
        
        # Verify customer exists
        customer = Customer.query.get(data['customer_id'])
        if not customer:
            return jsonify({'error': 'Customer not found'}), 404
        
        # Create new invoice
        invoice = Invoice(
            customer_id=data['customer_id'],
            created_by=current_user.id
        )
        
        # Generate invoice number
        invoice.generate_invoice_number()
        
        # Set dates
        if data.get('issue_date'):
            try:
                invoice.issue_date = datetime.strptime(data['issue_date'], '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'error': 'Invalid issue_date format. Use YYYY-MM-DD'}), 400
        
        if data.get('due_date'):
            try:
                invoice.due_date = datetime.strptime(data['due_date'], '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'error': 'Invalid due_date format. Use YYYY-MM-DD'}), 400
        else:
            # Default due date based on payment terms
            payment_terms = data.get('payment_terms', customer.payment_terms or 30)
            invoice.due_date = invoice.issue_date + timedelta(days=payment_terms)
        
        # Set optional fields
        invoice.reference_number = data.get('reference_number', '').strip() or None
        invoice.po_number = data.get('po_number', '').strip() or None
        invoice.lpo_number = data.get('lpo_number', '').strip() or None
        
        if data.get('delivery_date'):
            try:
                invoice.delivery_date = datetime.strptime(data['delivery_date'], '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'error': 'Invalid delivery_date format. Use YYYY-MM-DD'}), 400
        
        # Set financial fields
        invoice.currency = data.get('currency', customer.preferred_currency or 'USD')
        invoice.tax_rate = data.get('tax_rate', 0)
        invoice.discount_amount = data.get('discount_amount', 0)
        invoice.payment_terms = data.get('payment_terms', customer.payment_terms or 30)
        invoice.payment_instructions = data.get('payment_instructions', '').strip() or None
        
        # Set notes
        invoice.notes = data.get('notes', '').strip() or None
        invoice.internal_notes = data.get('internal_notes', '').strip() or None
        
        # Add to session to get ID
        db.session.add(invoice)
        db.session.flush()
        
        # Create line items
        for item_data in data['line_items']:
            if not item_data.get('description') or not item_data.get('quantity') or not item_data.get('unit_price'):
                return jsonify({'error': 'Each line item must have description, quantity, and unit_price'}), 400
            
            line_item = InvoiceLineItem(
                invoice_id=invoice.id,
                description=item_data['description'].strip(),
                quantity=item_data['quantity'],
                unit_price=item_data['unit_price'],
                unit_of_measure=item_data.get('unit_of_measure', '').strip() or None,
                product_code=item_data.get('product_code', '').strip() or None
            )
            line_item.calculate_total()
            db.session.add(line_item)
        
        # Calculate invoice totals
        db.session.flush()  # Ensure line items are saved
        invoice.calculate_totals()
        
        # Create initial status history
        history = InvoiceStatusHistory(
            invoice_id=invoice.id,
            old_status=InvoiceStatus.DRAFT,
            new_status=InvoiceStatus.DRAFT,
            changed_by=current_user.id,
            notes="Invoice created"
        )
        db.session.add(history)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Invoice created successfully',
            'invoice': invoice.to_dict(include_line_items=True)
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to create invoice', 'details': str(e)}), 500

@invoice_bp.route('/<int:invoice_id>', methods=['PUT'])
@token_required
def update_invoice(current_user, invoice_id):
    """Update an existing invoice"""
    try:
        invoice = Invoice.query.get(invoice_id)
        
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404
        
        # Check if invoice can be edited
        if invoice.status in [InvoiceStatus.PAID, InvoiceStatus.CANCELLED]:
            return jsonify({'error': 'Cannot edit paid or cancelled invoices'}), 400
        
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Update customer if provided
        if 'customer_id' in data:
            customer = Customer.query.get(data['customer_id'])
            if not customer:
                return jsonify({'error': 'Customer not found'}), 404
            invoice.customer_id = data['customer_id']
        
        # Update dates
        if 'issue_date' in data:
            try:
                invoice.issue_date = datetime.strptime(data['issue_date'], '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'error': 'Invalid issue_date format. Use YYYY-MM-DD'}), 400
        
        if 'due_date' in data:
            try:
                invoice.due_date = datetime.strptime(data['due_date'], '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'error': 'Invalid due_date format. Use YYYY-MM-DD'}), 400
        
        if 'delivery_date' in data:
            if data['delivery_date']:
                try:
                    invoice.delivery_date = datetime.strptime(data['delivery_date'], '%Y-%m-%d').date()
                except ValueError:
                    return jsonify({'error': 'Invalid delivery_date format. Use YYYY-MM-DD'}), 400
            else:
                invoice.delivery_date = None
        
        # Update optional fields
        optional_fields = ['reference_number', 'po_number', 'lpo_number', 'payment_instructions', 'notes', 'internal_notes']
        for field in optional_fields:
            if field in data:
                setattr(invoice, field, data[field].strip() or None)
        
        # Update financial fields
        if 'currency' in data:
            invoice.currency = data['currency']
        if 'tax_rate' in data:
            invoice.tax_rate = data['tax_rate']
        if 'discount_amount' in data:
            invoice.discount_amount = data['discount_amount']
        if 'payment_terms' in data:
            invoice.payment_terms = data['payment_terms']
        
        # Update line items if provided
        if 'line_items' in data:
            # Remove existing line items
            InvoiceLineItem.query.filter_by(invoice_id=invoice.id).delete()
            
            # Add new line items
            for item_data in data['line_items']:
                if not item_data.get('description') or not item_data.get('quantity') or not item_data.get('unit_price'):
                    return jsonify({'error': 'Each line item must have description, quantity, and unit_price'}), 400
                
                line_item = InvoiceLineItem(
                    invoice_id=invoice.id,
                    description=item_data['description'].strip(),
                    quantity=item_data['quantity'],
                    unit_price=item_data['unit_price'],
                    unit_of_measure=item_data.get('unit_of_measure', '').strip() or None,
                    product_code=item_data.get('product_code', '').strip() or None
                )
                line_item.calculate_total()
                db.session.add(line_item)
        
        # Recalculate totals
        db.session.flush()
        invoice.calculate_totals()
        
        db.session.commit()
        
        return jsonify({
            'message': 'Invoice updated successfully',
            'invoice': invoice.to_dict(include_line_items=True)
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to update invoice', 'details': str(e)}), 500

@invoice_bp.route('/<int:invoice_id>/status', methods=['PUT'])
@token_required
def update_invoice_status(current_user, invoice_id):
    """Update invoice status"""
    try:
        invoice = Invoice.query.get(invoice_id)
        
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404
        
        data = request.get_json()
        
        if not data or not data.get('status'):
            return jsonify({'error': 'Status is required'}), 400
        
        new_status = data['status']
        if new_status not in [s.value for s in InvoiceStatus]:
            return jsonify({'error': 'Invalid status'}), 400
        
        new_status_enum = InvoiceStatus(new_status)
        notes = data.get('notes', '').strip() or None
        
        # Validate status transition
        current_status = invoice.status
        valid_transitions = {
            InvoiceStatus.DRAFT: [InvoiceStatus.SENT, InvoiceStatus.CANCELLED],
            InvoiceStatus.SENT: [InvoiceStatus.PAID, InvoiceStatus.OVERDUE, InvoiceStatus.CANCELLED],
            InvoiceStatus.OVERDUE: [InvoiceStatus.PAID, InvoiceStatus.CANCELLED],
            InvoiceStatus.PAID: [],  # Paid invoices cannot change status
            InvoiceStatus.CANCELLED: [InvoiceStatus.DRAFT]  # Can reactivate cancelled invoices
        }
        
        if new_status_enum not in valid_transitions.get(current_status, []):
            return jsonify({
                'error': f'Cannot change status from {current_status.value} to {new_status_enum.value}'
            }), 400
        
        # Update status
        invoice.update_status(new_status_enum, current_user.id, notes)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Invoice status updated successfully',
            'invoice': invoice.to_dict(include_line_items=True)
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to update invoice status', 'details': str(e)}), 500

@invoice_bp.route('/<int:invoice_id>/qr-code', methods=['GET'])
@token_required
def get_invoice_qr_code(current_user, invoice_id):
    """Generate QR code for invoice payment"""
    try:
        invoice = Invoice.query.get(invoice_id)
        
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404
        
        base_url = request.args.get('base_url', 'https://wasatpay.com')
        qr_code_data = invoice.generate_qr_code(base_url)
        
        return jsonify({
            'qr_code': qr_code_data,
            'payment_url': f"{base_url}{invoice.payment_url}"
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to generate QR code', 'details': str(e)}), 500

@invoice_bp.route('/stats', methods=['GET'])
@token_required
def get_invoice_stats(current_user):
    """Get invoice statistics"""
    try:
        # Get date range from query parameters
        date_from = request.args.get('date_from', '').strip()
        date_to = request.args.get('date_to', '').strip()
        
        query = Invoice.query
        
        # Apply date filter if provided
        if date_from:
            try:
                from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
                query = query.filter(Invoice.issue_date >= from_date)
            except ValueError:
                return jsonify({'error': 'Invalid date_from format. Use YYYY-MM-DD'}), 400
        
        if date_to:
            try:
                to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
                query = query.filter(Invoice.issue_date <= to_date)
            except ValueError:
                return jsonify({'error': 'Invalid date_to format. Use YYYY-MM-DD'}), 400
        
        # Get all invoices for the period
        invoices = query.all()
        
        # Calculate statistics
        total_invoices = len(invoices)
        total_amount = sum(float(invoice.total_amount) for invoice in invoices)
        
        # Group by status
        status_counts = {}
        status_amounts = {}
        
        for status in InvoiceStatus:
            status_invoices = [inv for inv in invoices if inv.status == status]
            status_counts[status.value] = len(status_invoices)
            status_amounts[status.value] = sum(float(inv.total_amount) for inv in status_invoices)
        
        # Calculate overdue invoices
        overdue_invoices = [inv for inv in invoices if inv.is_overdue]
        
        # Recent invoices
        recent_invoices = sorted(invoices, key=lambda x: x.created_at, reverse=True)[:5]
        
        return jsonify({
            'total_invoices': total_invoices,
            'total_amount': total_amount,
            'status_counts': status_counts,
            'status_amounts': status_amounts,
            'overdue_count': len(overdue_invoices),
            'overdue_amount': sum(float(inv.total_amount) for inv in overdue_invoices),
            'recent_invoices': [inv.to_dict(include_line_items=False) for inv in recent_invoices]
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to retrieve invoice statistics', 'details': str(e)}), 500

