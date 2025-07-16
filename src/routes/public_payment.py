from flask import Blueprint, request, jsonify, render_template_string
from src.models.user import db
from src.models.invoice import Invoice, InvoiceStatus
from src.models.payment import Payment, PaymentStatus, PaymentMethod, PaymentProvider
from src.services.invoice_service import invoice_service
from datetime import datetime

public_payment_bp = Blueprint('public_payment', __name__)

@public_payment_bp.route('/pay/<uuid:invoice_uuid>', methods=['GET'])
def payment_page(invoice_uuid):
    """Public payment page for customers"""
    try:
        # Find invoice by UUID
        invoice = Invoice.query.filter_by(uuid=str(invoice_uuid)).first()
        
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404
        
        # Check if invoice can be paid
        if invoice.status not in [InvoiceStatus.SENT, InvoiceStatus.OVERDUE]:
            return jsonify({
                'error': 'Invoice cannot be paid',
                'status': invoice.status.value,
                'message': 'This invoice is not available for payment'
            }), 400
        
        # Check if invoice is already fully paid
        if float(invoice.outstanding_amount) <= 0:
            return jsonify({
                'error': 'Invoice already paid',
                'message': 'This invoice has been fully paid'
            }), 400
        
        # Return invoice details for payment
        base_url = request.host_url.rstrip('/')
        
        return jsonify({
            'invoice': {
                'uuid': invoice.uuid,
                'invoice_number': invoice.invoice_number,
                'issue_date': invoice.issue_date.isoformat(),
                'due_date': invoice.due_date.isoformat() if invoice.due_date else None,
                'total_amount': float(invoice.total_amount),
                'outstanding_amount': float(invoice.outstanding_amount),
                'currency': invoice.currency,
                'status': invoice.status.value,
                'is_overdue': invoice.is_overdue,
                'line_items': [item.to_dict() for item in invoice.line_items]
            },
            'customer': {
                'name': invoice.customer.display_name,
                'email': invoice.customer.primary_email,
                'organization': invoice.customer.organization_name
            },
            'organization': {
                'name': 'Wasat Humanitarian Foundation',
                'logo': invoice_service._get_logo_path()
            },
            'payment_methods': [
                {
                    'id': 'card',
                    'name': 'Credit/Debit Card',
                    'description': 'Pay securely with your credit or debit card',
                    'providers': ['stripe', 'flutterwave']
                },
                {
                    'id': 'bank_transfer',
                    'name': 'Bank Transfer',
                    'description': 'Transfer funds directly from your bank account',
                    'providers': ['manual']
                },
                {
                    'id': 'mobile_money',
                    'name': 'Mobile Money',
                    'description': 'Pay using mobile money services',
                    'providers': ['flutterwave']
                },
                {
                    'id': 'mpesa',
                    'name': 'M-Pesa',
                    'description': 'Pay using M-Pesa mobile money',
                    'providers': ['flutterwave']
                }
            ]
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to load payment page', 'details': str(e)}), 500

@public_payment_bp.route('/pay/<uuid:invoice_uuid>/initiate', methods=['POST'])
def initiate_payment(invoice_uuid):
    """Initiate payment for an invoice"""
    try:
        # Find invoice by UUID
        invoice = Invoice.query.filter_by(uuid=str(invoice_uuid)).first()
        
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404
        
        # Check if invoice can be paid
        if invoice.status not in [InvoiceStatus.SENT, InvoiceStatus.OVERDUE]:
            return jsonify({'error': 'Invoice cannot be paid in current status'}), 400
        
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Payment data is required'}), 400
        
        # Validate payment details
        amount = data.get('amount')
        if not amount or amount <= 0:
            return jsonify({'error': 'Valid payment amount is required'}), 400
        
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
            # Card payment - will be processed through payment provider
            payment.card_last_four = data.get('card_last_four')
            payment.card_brand = data.get('card_brand')
        elif method == PaymentMethod.BANK_TRANSFER.value:
            payment.bank_name = data.get('bank_name')
            payment.bank_account_number = data.get('bank_account_number')
            payment.bank_reference = data.get('bank_reference')
        elif method in [PaymentMethod.MOBILE_MONEY.value, PaymentMethod.MPESA.value]:
            payment.mobile_number = data.get('mobile_number')
            payment.mobile_network = data.get('mobile_network')
        
        db.session.add(payment)
        db.session.commit()
        
        # Return payment details for frontend processing
        response_data = {
            'message': 'Payment initiated successfully',
            'payment': {
                'id': payment.id,
                'uuid': payment.uuid,
                'amount': float(payment.amount),
                'currency': payment.currency,
                'method': payment.method.value,
                'provider': payment.provider.value,
                'status': payment.status.value
            },
            'next_steps': {
                'card': {
                    'action': 'redirect_to_processor',
                    'message': 'Redirecting to secure payment processor...'
                },
                'bank_transfer': {
                    'action': 'show_instructions',
                    'message': 'Please follow the bank transfer instructions below',
                    'instructions': {
                        'bank_name': 'Wasat Foundation Bank',
                        'account_number': '1234567890',
                        'account_name': 'Wasat Humanitarian Foundation',
                        'reference': f"INV-{invoice.invoice_number}-{payment.id}",
                        'amount': float(payment.amount),
                        'currency': payment.currency
                    }
                },
                'mobile_money': {
                    'action': 'process_mobile_payment',
                    'message': 'Processing mobile money payment...'
                },
                'mpesa': {
                    'action': 'process_mpesa',
                    'message': 'Processing M-Pesa payment...'
                }
            }.get(method, {'action': 'unknown', 'message': 'Processing payment...'})
        }
        
        return jsonify(response_data), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to initiate payment', 'details': str(e)}), 500

@public_payment_bp.route('/payment/<uuid:payment_uuid>/status', methods=['GET'])
def payment_status(payment_uuid):
    """Check payment status"""
    try:
        payment = Payment.query.filter_by(uuid=str(payment_uuid)).first()
        
        if not payment:
            return jsonify({'error': 'Payment not found'}), 404
        
        return jsonify({
            'payment': {
                'id': payment.id,
                'uuid': payment.uuid,
                'amount': float(payment.amount),
                'currency': payment.currency,
                'method': payment.method.value,
                'provider': payment.provider.value,
                'status': payment.status.value,
                'created_at': payment.created_at.isoformat(),
                'completed_at': payment.completed_at.isoformat() if payment.completed_at else None,
                'failure_reason': payment.failure_reason
            },
            'invoice': {
                'invoice_number': payment.invoice.invoice_number,
                'total_amount': float(payment.invoice.total_amount),
                'outstanding_amount': float(payment.invoice.outstanding_amount)
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get payment status', 'details': str(e)}), 500

@public_payment_bp.route('/payment/<uuid:payment_uuid>/confirm', methods=['POST'])
def confirm_payment(payment_uuid):
    """Confirm payment completion (for manual methods like bank transfer)"""
    try:
        payment = Payment.query.filter_by(uuid=str(payment_uuid)).first()
        
        if not payment:
            return jsonify({'error': 'Payment not found'}), 404
        
        if payment.status != PaymentStatus.PENDING:
            return jsonify({'error': 'Payment cannot be confirmed in current status'}), 400
        
        data = request.get_json() or {}
        
        # For bank transfer, customer can provide additional details
        if payment.method == PaymentMethod.BANK_TRANSFER:
            if data.get('bank_reference'):
                payment.bank_reference = data['bank_reference']
            if data.get('transaction_date'):
                try:
                    payment.transaction_date = datetime.fromisoformat(data['transaction_date'])
                except ValueError:
                    pass
        
        # Mark as pending verification (admin will need to verify manually)
        payment.status = PaymentStatus.PENDING
        payment.notes = data.get('notes', 'Customer confirmed payment completion')
        
        db.session.commit()
        
        return jsonify({
            'message': 'Payment confirmation received',
            'payment': {
                'uuid': payment.uuid,
                'status': payment.status.value,
                'message': 'Your payment confirmation has been received and is being verified. You will receive an email confirmation once verified.'
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to confirm payment', 'details': str(e)}), 500

@public_payment_bp.route('/invoice/<uuid:invoice_uuid>/receipt', methods=['GET'])
def payment_receipt(invoice_uuid):
    """Generate payment receipt for completed payments"""
    try:
        invoice = Invoice.query.filter_by(uuid=str(invoice_uuid)).first()
        
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404
        
        # Get completed payments for this invoice
        completed_payments = Payment.query.filter_by(
            invoice_id=invoice.id,
            status=PaymentStatus.COMPLETED
        ).order_by(Payment.completed_at.desc()).all()
        
        if not completed_payments:
            return jsonify({'error': 'No completed payments found for this invoice'}), 404
        
        return jsonify({
            'invoice': {
                'invoice_number': invoice.invoice_number,
                'total_amount': float(invoice.total_amount),
                'outstanding_amount': float(invoice.outstanding_amount),
                'currency': invoice.currency
            },
            'customer': {
                'name': invoice.customer.display_name,
                'email': invoice.customer.primary_email
            },
            'payments': [
                {
                    'id': payment.id,
                    'amount': float(payment.amount),
                    'method': payment.method.value,
                    'provider': payment.provider.value,
                    'completed_at': payment.completed_at.isoformat(),
                    'provider_transaction_id': payment.provider_transaction_id
                }
                for payment in completed_payments
            ],
            'total_paid': sum(float(p.amount) for p in completed_payments),
            'organization': {
                'name': 'Wasat Humanitarian Foundation',
                'logo': invoice_service._get_logo_path()
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to generate receipt', 'details': str(e)}), 500

