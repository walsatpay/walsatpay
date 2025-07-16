from src.models.user import db
from datetime import datetime, timedelta
from enum import Enum
import uuid
import qrcode
import io
import base64
from decimal import Decimal

class InvoiceStatus(Enum):
    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"

class Invoice(db.Model):
    __tablename__ = 'invoices'
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    
    # Customer relationship
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    
    # Project relationship (for foundation-specific invoicing)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=True)
    
    # Invoice details
    issue_date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    due_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.Enum(InvoiceStatus), nullable=False, default=InvoiceStatus.DRAFT)
    
    # Optional reference fields
    reference_number = db.Column(db.String(100))
    po_number = db.Column(db.String(100))  # Purchase Order Number
    lpo_number = db.Column(db.String(100))  # Local Purchase Order Number
    delivery_date = db.Column(db.Date)
    
    # Financial information
    currency = db.Column(db.String(3), nullable=False, default='USD')
    subtotal = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    tax_rate = db.Column(db.Numeric(5, 2), default=0)  # Tax rate as percentage
    tax_amount = db.Column(db.Numeric(10, 2), default=0)
    discount_amount = db.Column(db.Numeric(10, 2), default=0)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    
    # Payment information
    payment_terms = db.Column(db.Integer, default=30)  # Payment terms in days
    payment_instructions = db.Column(db.Text)
    
    # Notes and additional information
    notes = db.Column(db.Text)
    internal_notes = db.Column(db.Text)  # Not visible to customer
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    sent_at = db.Column(db.DateTime)
    paid_at = db.Column(db.DateTime)
    
    # User tracking
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Relationships
    line_items = db.relationship('InvoiceLineItem', backref='invoice', lazy=True, cascade='all, delete-orphan')
    payments = db.relationship('Payment', backref='invoice', lazy=True)
    status_history = db.relationship('InvoiceStatusHistory', backref='invoice', lazy=True, cascade='all, delete-orphan')
    project = db.relationship('Project', back_populates='invoices')
    
    def __repr__(self):
        return f'<Invoice {self.invoice_number}>'
    
    @property
    def is_overdue(self):
        """Check if invoice is overdue"""
        return (self.status in [InvoiceStatus.SENT] and 
                self.due_date < datetime.utcnow().date())
    
    @property
    def days_until_due(self):
        """Calculate days until due date"""
        if self.due_date:
            delta = self.due_date - datetime.utcnow().date()
            return delta.days
        return None
    
    @property
    def payment_url(self):
        """Generate payment URL for this invoice"""
        return f"/pay/{self.uuid}"
    
    @property
    def total_paid(self):
        """Calculate total amount paid for this invoice"""
        from src.models.payment import Payment, PaymentStatus
        paid_payments = Payment.query.filter_by(
            invoice_id=self.id,
            status=PaymentStatus.COMPLETED
        ).all()
        return sum(payment.amount for payment in paid_payments)
    
    @property
    def outstanding_amount(self):
        """Calculate outstanding amount"""
        return self.total_amount - self.total_paid
    
    def generate_invoice_number(self):
        """Generate unique invoice number"""
        from datetime import datetime
        year = datetime.utcnow().year
        
        # Get the last invoice number for this year
        last_invoice = Invoice.query.filter(
            Invoice.invoice_number.like(f'INV-{year}-%')
        ).order_by(Invoice.invoice_number.desc()).first()
        
        if last_invoice:
            # Extract sequence number and increment
            try:
                last_seq = int(last_invoice.invoice_number.split('-')[-1])
                next_seq = last_seq + 1
            except (ValueError, IndexError):
                next_seq = 1
        else:
            next_seq = 1
        
        self.invoice_number = f'INV-{year}-{next_seq:04d}'
    
    def calculate_totals(self):
        """Calculate invoice totals based on line items"""
        self.subtotal = sum(item.total_amount for item in self.line_items)
        self.tax_amount = (self.subtotal * self.tax_rate / 100) if self.tax_rate else 0
        self.total_amount = self.subtotal + self.tax_amount - self.discount_amount
    
    def update_status(self, new_status, user_id=None, notes=None):
        """Update invoice status and create history record"""
        if self.status != new_status:
            old_status = self.status
            self.status = new_status
            
            # Update timestamps based on status
            if new_status == InvoiceStatus.SENT:
                self.sent_at = datetime.utcnow()
            elif new_status == InvoiceStatus.PAID:
                self.paid_at = datetime.utcnow()
            
            # Create status history record
            history = InvoiceStatusHistory(
                invoice_id=self.id,
                old_status=old_status,
                new_status=new_status,
                changed_by=user_id,
                notes=notes
            )
            db.session.add(history)
    
    def generate_qr_code(self, base_url="https://wasatpay.com"):
        """Generate QR code for payment URL"""
        payment_url = f"{base_url}{self.payment_url}"
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(payment_url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64 string
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()
        
        return f"data:image/png;base64,{img_str}"
    
    def check_overdue_status(self):
        """Check and update overdue status"""
        if self.is_overdue and self.status == InvoiceStatus.SENT:
            self.update_status(InvoiceStatus.OVERDUE)
    
    def to_dict(self, include_line_items=True, include_payments=False, include_history=False):
        """Convert invoice to dictionary"""
        data = {
            'id': self.id,
            'invoice_number': self.invoice_number,
            'uuid': self.uuid,
            'customer_id': self.customer_id,
            'customer': self.customer.to_dict() if self.customer else None,
            'issue_date': self.issue_date.isoformat() if self.issue_date else None,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'status': self.status.value,
            'reference_number': self.reference_number,
            'po_number': self.po_number,
            'lpo_number': self.lpo_number,
            'delivery_date': self.delivery_date.isoformat() if self.delivery_date else None,
            'currency': self.currency,
            'subtotal': float(self.subtotal) if self.subtotal else 0,
            'tax_rate': float(self.tax_rate) if self.tax_rate else 0,
            'tax_amount': float(self.tax_amount) if self.tax_amount else 0,
            'discount_amount': float(self.discount_amount) if self.discount_amount else 0,
            'total_amount': float(self.total_amount) if self.total_amount else 0,
            'total_paid': float(self.total_paid),
            'outstanding_amount': float(self.outstanding_amount),
            'payment_terms': self.payment_terms,
            'payment_instructions': self.payment_instructions,
            'payment_url': self.payment_url,
            'notes': self.notes,
            'internal_notes': self.internal_notes,
            'is_overdue': self.is_overdue,
            'days_until_due': self.days_until_due,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None,
            'created_by': self.created_by
        }
        
        if include_line_items:
            data['line_items'] = [item.to_dict() for item in self.line_items]
        
        if include_payments:
            data['payments'] = [payment.to_dict() for payment in self.payments]
        
        if include_history:
            data['status_history'] = [history.to_dict() for history in self.status_history]
        
        return data

class InvoiceLineItem(db.Model):
    __tablename__ = 'invoice_line_items'
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False)
    
    # Line item details
    description = db.Column(db.String(500), nullable=False)
    quantity = db.Column(db.Numeric(10, 2), nullable=False, default=1)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    
    # Optional fields
    unit_of_measure = db.Column(db.String(20))  # e.g., "hours", "pieces", "kg"
    product_code = db.Column(db.String(50))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f'<InvoiceLineItem {self.description[:50]}>'
    
    def calculate_total(self):
        """Calculate total amount for this line item"""
        self.total_amount = self.quantity * self.unit_price
    
    def to_dict(self):
        """Convert line item to dictionary"""
        return {
            'id': self.id,
            'description': self.description,
            'quantity': float(self.quantity) if self.quantity else 0,
            'unit_price': float(self.unit_price) if self.unit_price else 0,
            'total_amount': float(self.total_amount) if self.total_amount else 0,
            'unit_of_measure': self.unit_of_measure,
            'product_code': self.product_code,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class InvoiceStatusHistory(db.Model):
    __tablename__ = 'invoice_status_history'
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False)
    
    # Status change details
    old_status = db.Column(db.Enum(InvoiceStatus), nullable=False)
    new_status = db.Column(db.Enum(InvoiceStatus), nullable=False)
    changed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    changed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    notes = db.Column(db.Text)
    
    # Relationships
    changed_by_user = db.relationship('User', backref='status_changes', foreign_keys=[changed_by])
    
    def __repr__(self):
        return f'<StatusHistory {self.old_status.value} -> {self.new_status.value}>'
    
    def to_dict(self):
        """Convert status history to dictionary"""
        return {
            'id': self.id,
            'old_status': self.old_status.value,
            'new_status': self.new_status.value,
            'changed_at': self.changed_at.isoformat() if self.changed_at else None,
            'changed_by': self.changed_by,
            'changed_by_user': self.changed_by_user.to_dict() if self.changed_by_user else None,
            'notes': self.notes
        }

