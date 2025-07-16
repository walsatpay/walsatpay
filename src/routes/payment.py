from flask import Blueprint, request, jsonify
from src.models.user import db
from src.models.invoice import Invoice, InvoiceStatus
from src.models.payment import Payment, PaymentStatus, PaymentMethod, PaymentProvider, PaymentRefund
from src.routes.auth import token_required
from datetime import datetime

payment_bp = Blueprint('payment', __name__)

@payment_bp.route('/', methods=['GET'])
@token_required
def get_payments(current_user):
    """Get all payments with optional filtering and pagination"""
    try:
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        status = request.args.get('status', '').strip()
        method = request.args.get('method', '').strip()
        provider = request.args.get('provider', '').strip()
        invoice_id = request.args.get('invoice_id', type=int)
        date_from = request.args.get('date_from', '').strip()
        date_to = request.args.get('date_to', '').strip()
        
        # Build query
        query = Payment.query
        
        # Apply filters
        if status and status in [s.value for s in PaymentStatus]:
            query = query.filter_by(status=PaymentStatus(status))
        
        if method and method in [m.value for m in PaymentMethod]:
            query = query.filter_by(method=PaymentMethod(method))
        
        if provider and provider in [p.value for p in PaymentProvider]:
            query = query.filter_by(provider=PaymentProvider(provider))
        
        if invoice_id:
            query = query.filter_by(invoice_id=invoice_id)
        
        # Apply date range filter
        if date_from:
            try:
                from_date = datetime.strptime(date_from, '%Y-%m-%d')
                query = query.filter(Payment.created_at >= from_date)
            except ValueError:
                return jsonify({'error': 'Invalid date_from format. Use YYYY-MM-DD'}), 400
        
        if date_to:
            try:
                to_date = datetime.strptime(date_to, '%Y-%m-%d')
                query = query.filter(Payment.created_at <= to_date)
            except ValueError:
                return jsonify({'error': 'Invalid date_to format. Use YYYY-MM-DD'}), 400
        
        # Order by creation date (newest first)
        query = query.order_by(Payment.created_at.desc())
        
        # Paginate results
        pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        payments = [payment.to_dict() for payment in pagination.items]
        
        return jsonify({
            'payments': payments,
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
        return jsonify({'error': 'Failed to retrieve payments', 'details': str(e)}), 500

@payment_bp.route('/<int:payment_id>', methods=['GET'])
@token_required
def get_payment(current_user, payment_id):
    """Get a specific payment by ID"""
    try:
        payment = Payment.query.get(payment_id)
        
        if not payment:
            return jsonify({'error': 'Payment not found'}), 404
        
        include_sensitive = current_user.is_admin()
        
        return jsonify({
            'payment': payment.to_dict(include_sensitive=include_sensitive)
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to retrieve payment', 'details': str(e)}), 500

@payment_bp.route('/initiate', methods=['POST'])
def initiate_payment():
    """Initiate a payment for an invoice (public endpoint)"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        invoice_uuid = data.get('invoice_uuid')
        if not invoice_uuid:
            return jsonify({'error': 'Invoice UUID is required'}), 400
        
        # Find invoice by UUID
        invoice = Invoice.query.filter_by(uuid=invoice_uuid).first()
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404
        
        # Check if invoice can be paid
        if invoice.status not in [InvoiceStatus.SENT, InvoiceStatus.OVERDUE]:
            return jsonify({'error': 'Invoice cannot be paid in current status'}), 400
        
        # Validate payment details
        amount = data.get('amount')
        if not amount or amount <= 0:
            return jsonify({'error': 'Valid amount is required'}), 400
        
        if amount > float(invoice.outstanding_amount):
            return jsonify({'error': 'Payment amount exceeds outstanding amount'}), 400
        
        method = data.get('method')
        if not method or method not in [m.value for m in PaymentMethod]:
            return jsonify({'error': 'Valid payment method is required'}), 400
        
        provider = data.get('provider')
        if not provider or provider not in [p.value for p in PaymentProvider]:
            return jsonify({'error': 'Valid payment provider is required'}), 400
        
        # Create payment record
        payment = Payment(
            invoice_id=invoice.id,
            amount=amount,
            currency=invoice.currency,
            method=PaymentMethod(method),
            provider=PaymentProvider(provider),
            description=f"Payment for invoice {invoice.invoice_number}",
            customer_email=data.get('customer_email', invoice.customer.primary_email),
            customer_name=data.get('customer_name', invoice.customer.display_name),
            customer_phone=data.get('customer_phone')
        )
        
        # Set method-specific information
        if method == PaymentMethod.CARD.value:
            # Card payment will be processed through payment provider
            pass
        elif method == PaymentMethod.BANK_TRANSFER.value:
            payment.bank_name = data.get('bank_name')
            payment.bank_account_number = data.get('bank_account_number')
            payment.bank_reference = data.get('bank_reference')
        elif method in [PaymentMethod.MOBILE_MONEY.value, PaymentMethod.MPESA.value]:
            payment.mobile_number = data.get('mobile_number')
            payment.mobile_network = data.get('mobile_network')
        
        db.session.add(payment)
        db.session.commit()
        
        # In a real implementation, you would integrate with payment providers here
        # For now, we'll return the payment details for frontend processing
        
        return jsonify({
            'message': 'Payment initiated successfully',
            'payment': payment.to_dict(),
            'next_steps': {
                'card': 'Redirect to payment processor',
                'bank_transfer': 'Show bank transfer instructions',
                'mobile_money': 'Process mobile money payment',
                'mpesa': 'Process M-Pesa payment'
            }.get(method, 'Process payment')
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to initiate payment', 'details': str(e)}), 500

@payment_bp.route('/<int:payment_id>/status', methods=['PUT'])
@token_required
def update_payment_status(current_user, payment_id):
    """Update payment status (admin only)"""
    try:
        if not current_user.is_admin():
            return jsonify({'error': 'Admin access required'}), 403
        
        payment = Payment.query.get(payment_id)
        
        if not payment:
            return jsonify({'error': 'Payment not found'}), 404
        
        data = request.get_json()
        
        if not data or not data.get('status'):
            return jsonify({'error': 'Status is required'}), 400
        
        new_status = data['status']
        if new_status not in [s.value for s in PaymentStatus]:
            return jsonify({'error': 'Invalid status'}), 400
        
        new_status_enum = PaymentStatus(new_status)
        failure_reason = data.get('failure_reason')
        failure_code = data.get('failure_code')
        
        # Update payment status
        payment.update_status(new_status_enum, failure_reason, failure_code)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Payment status updated successfully',
            'payment': payment.to_dict(include_sensitive=True)
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to update payment status', 'details': str(e)}), 500

@payment_bp.route('/<int:payment_id>/refund', methods=['POST'])
@token_required
def create_refund(current_user, payment_id):
    """Create a refund for a payment (admin only)"""
    try:
        if not current_user.is_admin():
            return jsonify({'error': 'Admin access required'}), 403
        
        payment = Payment.query.get(payment_id)
        
        if not payment:
            return jsonify({'error': 'Payment not found'}), 404
        
        data = request.get_json()
        
        if not data or not data.get('amount'):
            return jsonify({'error': 'Refund amount is required'}), 400
        
        amount = data['amount']
        reason = data.get('reason', '').strip() or None
        
        try:
            refund = payment.create_refund(amount, reason, current_user.id)
            db.session.commit()
            
            return jsonify({
                'message': 'Refund created successfully',
                'refund': refund.to_dict()
            }), 201
            
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to create refund', 'details': str(e)}), 500

@payment_bp.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook events"""
    try:
        # In a real implementation, you would verify the webhook signature
        # and process the event based on its type
        
        data = request.get_json()
        
        if not data or not data.get('type'):
            return jsonify({'error': 'Invalid webhook data'}), 400
        
        event_type = data['type']
        event_data = data.get('data', {}).get('object', {})
        
        # Handle different event types
        if event_type == 'payment_intent.succeeded':
            # Payment succeeded
            payment_intent_id = event_data.get('id')
            if payment_intent_id:
                payment = Payment.query.filter_by(
                    provider_payment_intent_id=payment_intent_id
                ).first()
                
                if payment:
                    payment.update_status(PaymentStatus.COMPLETED)
                    db.session.commit()
        
        elif event_type == 'payment_intent.payment_failed':
            # Payment failed
            payment_intent_id = event_data.get('id')
            if payment_intent_id:
                payment = Payment.query.filter_by(
                    provider_payment_intent_id=payment_intent_id
                ).first()
                
                if payment:
                    failure_reason = event_data.get('last_payment_error', {}).get('message')
                    failure_code = event_data.get('last_payment_error', {}).get('code')
                    payment.update_status(PaymentStatus.FAILED, failure_reason, failure_code)
                    db.session.commit()
        
        return jsonify({'status': 'success'}), 200
        
    except Exception as e:
        return jsonify({'error': 'Webhook processing failed', 'details': str(e)}), 500

@payment_bp.route('/webhook/flutterwave', methods=['POST'])
def flutterwave_webhook():
    """Handle Flutterwave webhook events"""
    try:
        # In a real implementation, you would verify the webhook signature
        # and process the event based on its type
        
        data = request.get_json()
        
        if not data or not data.get('event'):
            return jsonify({'error': 'Invalid webhook data'}), 400
        
        event_type = data['event']
        event_data = data.get('data', {})
        
        # Handle different event types
        if event_type == 'charge.completed':
            # Payment completed
            transaction_id = event_data.get('id')
            if transaction_id:
                payment = Payment.query.filter_by(
                    provider_transaction_id=str(transaction_id)
                ).first()
                
                if payment:
                    payment.update_status(PaymentStatus.COMPLETED)
                    db.session.commit()
        
        elif event_type == 'charge.failed':
            # Payment failed
            transaction_id = event_data.get('id')
            if transaction_id:
                payment = Payment.query.filter_by(
                    provider_transaction_id=str(transaction_id)
                ).first()
                
                if payment:
                    failure_reason = event_data.get('processor_response')
                    payment.update_status(PaymentStatus.FAILED, failure_reason)
                    db.session.commit()
        
        return jsonify({'status': 'success'}), 200
        
    except Exception as e:
        return jsonify({'error': 'Webhook processing failed', 'details': str(e)}), 500

@payment_bp.route('/stats', methods=['GET'])
@token_required
def get_payment_stats(current_user):
    """Get payment statistics"""
    try:
        # Get date range from query parameters
        date_from = request.args.get('date_from', '').strip()
        date_to = request.args.get('date_to', '').strip()
        
        query = Payment.query
        
        # Apply date filter if provided
        if date_from:
            try:
                from_date = datetime.strptime(date_from, '%Y-%m-%d')
                query = query.filter(Payment.created_at >= from_date)
            except ValueError:
                return jsonify({'error': 'Invalid date_from format. Use YYYY-MM-DD'}), 400
        
        if date_to:
            try:
                to_date = datetime.strptime(date_to, '%Y-%m-%d')
                query = query.filter(Payment.created_at <= to_date)
            except ValueError:
                return jsonify({'error': 'Invalid date_to format. Use YYYY-MM-DD'}), 400
        
        # Get all payments for the period
        payments = query.all()
        
        # Calculate statistics
        total_payments = len(payments)
        total_amount = sum(float(payment.amount) for payment in payments)
        successful_payments = [p for p in payments if p.status == PaymentStatus.COMPLETED]
        total_successful_amount = sum(float(p.amount) for p in successful_payments)
        
        # Group by status
        status_counts = {}
        status_amounts = {}
        
        for status in PaymentStatus:
            status_payments = [p for p in payments if p.status == status]
            status_counts[status.value] = len(status_payments)
            status_amounts[status.value] = sum(float(p.amount) for p in status_payments)
        
        # Group by method
        method_counts = {}
        method_amounts = {}
        
        for method in PaymentMethod:
            method_payments = [p for p in payments if p.method == method]
            method_counts[method.value] = len(method_payments)
            method_amounts[method.value] = sum(float(p.amount) for p in method_payments)
        
        # Group by provider
        provider_counts = {}
        provider_amounts = {}
        
        for provider in PaymentProvider:
            provider_payments = [p for p in payments if p.provider == provider]
            provider_counts[provider.value] = len(provider_payments)
            provider_amounts[provider.value] = sum(float(p.amount) for p in provider_payments)
        
        # Recent payments
        recent_payments = sorted(payments, key=lambda x: x.created_at, reverse=True)[:5]
        
        return jsonify({
            'total_payments': total_payments,
            'total_amount': total_amount,
            'successful_payments': len(successful_payments),
            'successful_amount': total_successful_amount,
            'success_rate': (len(successful_payments) / total_payments * 100) if total_payments > 0 else 0,
            'status_counts': status_counts,
            'status_amounts': status_amounts,
            'method_counts': method_counts,
            'method_amounts': method_amounts,
            'provider_counts': provider_counts,
            'provider_amounts': provider_amounts,
            'recent_payments': [p.to_dict() for p in recent_payments]
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to retrieve payment statistics', 'details': str(e)}), 500

