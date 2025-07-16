from src.models.user import db
from datetime import datetime
from enum import Enum
from decimal import Decimal

class PaymentStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"

class PaymentMethod(Enum):
    CARD = "card"
    BANK_TRANSFER = "bank_transfer"
    MOBILE_MONEY = "mobile_money"
    MPESA = "mpesa"

class PaymentProvider(Enum):
    STRIPE = "stripe"
    FLUTTERWAVE = "flutterwave"
    MANUAL = "manual"

class Payment(db.Model):
    __tablename__ = 'payments'
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False)
    
    # Payment details
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default='USD')
    status = db.Column(db.Enum(PaymentStatus), nullable=False, default=PaymentStatus.PENDING)
    method = db.Column(db.Enum(PaymentMethod), nullable=False)
    provider = db.Column(db.Enum(PaymentProvider), nullable=False)
    
    # Provider-specific information
    provider_transaction_id = db.Column(db.String(100), index=True)
    provider_payment_intent_id = db.Column(db.String(100))
    provider_customer_id = db.Column(db.String(100))
    
    # Payment metadata
    description = db.Column(db.String(500))
    reference_number = db.Column(db.String(100))
    
    # Customer information (for payment processing)
    customer_email = db.Column(db.String(120))
    customer_name = db.Column(db.String(200))
    customer_phone = db.Column(db.String(20))
    
    # Card information (tokenized/masked)
    card_last_four = db.Column(db.String(4))
    card_brand = db.Column(db.String(20))
    card_exp_month = db.Column(db.Integer)
    card_exp_year = db.Column(db.Integer)
    
    # Bank transfer information
    bank_name = db.Column(db.String(100))
    bank_account_number = db.Column(db.String(50))
    bank_reference = db.Column(db.String(100))
    
    # Mobile money information
    mobile_number = db.Column(db.String(20))
    mobile_network = db.Column(db.String(50))
    mobile_reference = db.Column(db.String(100))
    
    # Processing information
    processing_fee = db.Column(db.Numeric(10, 2), default=0)
    net_amount = db.Column(db.Numeric(10, 2))  # Amount after fees
    
    # Status tracking
    failure_reason = db.Column(db.String(500))
    failure_code = db.Column(db.String(50))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    processed_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    failed_at = db.Column(db.DateTime)
    
    # Relationships
    refunds = db.relationship('PaymentRefund', backref='payment', lazy=True)
    
    def __repr__(self):
        return f'<Payment {self.id} - {self.amount} {self.currency}>'
    
    @property
    def is_successful(self):
        """Check if payment was successful"""
        return self.status == PaymentStatus.COMPLETED
    
    @property
    def is_refundable(self):
        """Check if payment can be refunded"""
        return self.status == PaymentStatus.COMPLETED
    
    @property
    def total_refunded(self):
        """Calculate total amount refunded"""
        return sum(refund.amount for refund in self.refunds if refund.status == PaymentStatus.COMPLETED)
    
    @property
    def refundable_amount(self):
        """Calculate amount available for refund"""
        return self.amount - self.total_refunded
    
    def calculate_net_amount(self):
        """Calculate net amount after processing fees"""
        self.net_amount = self.amount - self.processing_fee
    
    def update_status(self, new_status, failure_reason=None, failure_code=None):
        """Update payment status with appropriate timestamps"""
        old_status = self.status
        self.status = new_status
        
        # Update timestamps based on status
        if new_status == PaymentStatus.PROCESSING:
            self.processed_at = datetime.utcnow()
        elif new_status == PaymentStatus.COMPLETED:
            self.completed_at = datetime.utcnow()
            # Update invoice status if fully paid
            if self.invoice.outstanding_amount <= 0:
                from src.models.invoice import InvoiceStatus
                self.invoice.update_status(InvoiceStatus.PAID)
        elif new_status == PaymentStatus.FAILED:
            self.failed_at = datetime.utcnow()
            self.failure_reason = failure_reason
            self.failure_code = failure_code
        
        # Create payment history record
        history = PaymentHistory(
            payment_id=self.id,
            old_status=old_status,
            new_status=new_status,
            failure_reason=failure_reason,
            failure_code=failure_code
        )
        db.session.add(history)
    
    def create_refund(self, amount, reason=None, user_id=None):
        """Create a refund for this payment"""
        if not self.is_refundable:
            raise ValueError("Payment is not refundable")
        
        if amount > self.refundable_amount:
            raise ValueError("Refund amount exceeds refundable amount")
        
        refund = PaymentRefund(
            payment_id=self.id,
            amount=amount,
            reason=reason,
            requested_by=user_id,
            status=PaymentStatus.PENDING
        )
        
        db.session.add(refund)
        return refund
    
    def to_dict(self, include_sensitive=False):
        """Convert payment to dictionary"""
        data = {
            'id': self.id,
            'invoice_id': self.invoice_id,
            'amount': float(self.amount) if self.amount else 0,
            'currency': self.currency,
            'status': self.status.value,
            'method': self.method.value,
            'provider': self.provider.value,
            'description': self.description,
            'reference_number': self.reference_number,
            'customer_email': self.customer_email,
            'customer_name': self.customer_name,
            'processing_fee': float(self.processing_fee) if self.processing_fee else 0,
            'net_amount': float(self.net_amount) if self.net_amount else 0,
            'total_refunded': float(self.total_refunded),
            'refundable_amount': float(self.refundable_amount),
            'is_successful': self.is_successful,
            'is_refundable': self.is_refundable,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'failed_at': self.failed_at.isoformat() if self.failed_at else None
        }
        
        # Add method-specific information
        if self.method == PaymentMethod.CARD:
            data['card_info'] = {
                'last_four': self.card_last_four,
                'brand': self.card_brand,
                'exp_month': self.card_exp_month,
                'exp_year': self.card_exp_year
            }
        elif self.method == PaymentMethod.BANK_TRANSFER:
            data['bank_info'] = {
                'bank_name': self.bank_name,
                'account_number': self.bank_account_number,
                'reference': self.bank_reference
            }
        elif self.method in [PaymentMethod.MOBILE_MONEY, PaymentMethod.MPESA]:
            data['mobile_info'] = {
                'number': self.mobile_number,
                'network': self.mobile_network,
                'reference': self.mobile_reference
            }
        
        if include_sensitive:
            data.update({
                'provider_transaction_id': self.provider_transaction_id,
                'provider_payment_intent_id': self.provider_payment_intent_id,
                'provider_customer_id': self.provider_customer_id,
                'failure_reason': self.failure_reason,
                'failure_code': self.failure_code
            })
        
        return data

class PaymentRefund(db.Model):
    __tablename__ = 'payment_refunds'
    
    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.id'), nullable=False)
    
    # Refund details
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    reason = db.Column(db.String(500))
    status = db.Column(db.Enum(PaymentStatus), nullable=False, default=PaymentStatus.PENDING)
    
    # Provider information
    provider_refund_id = db.Column(db.String(100))
    
    # Tracking
    requested_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    processed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    processed_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    
    # Relationships
    requested_by_user = db.relationship('User', foreign_keys=[requested_by], backref='requested_refunds')
    processed_by_user = db.relationship('User', foreign_keys=[processed_by], backref='processed_refunds')
    
    def __repr__(self):
        return f'<PaymentRefund {self.id} - {self.amount}>'
    
    def to_dict(self):
        """Convert refund to dictionary"""
        return {
            'id': self.id,
            'payment_id': self.payment_id,
            'amount': float(self.amount) if self.amount else 0,
            'reason': self.reason,
            'status': self.status.value,
            'provider_refund_id': self.provider_refund_id,
            'requested_by': self.requested_by,
            'processed_by': self.processed_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }

class PaymentHistory(db.Model):
    __tablename__ = 'payment_history'
    
    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.id'), nullable=False)
    
    # Status change details
    old_status = db.Column(db.Enum(PaymentStatus), nullable=False)
    new_status = db.Column(db.Enum(PaymentStatus), nullable=False)
    changed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Error information
    failure_reason = db.Column(db.String(500))
    failure_code = db.Column(db.String(50))
    
    # Relationships
    payment = db.relationship('Payment', backref='history')
    
    def __repr__(self):
        return f'<PaymentHistory {self.old_status.value} -> {self.new_status.value}>'
    
    def to_dict(self):
        """Convert payment history to dictionary"""
        return {
            'id': self.id,
            'old_status': self.old_status.value,
            'new_status': self.new_status.value,
            'changed_at': self.changed_at.isoformat() if self.changed_at else None,
            'failure_reason': self.failure_reason,
            'failure_code': self.failure_code
        }

