from src.models.user import db
from datetime import datetime
from enum import Enum

class CustomerType(Enum):
    INDIVIDUAL = "individual"
    ORGANIZATION = "organization"

class Customer(db.Model):
    __tablename__ = 'customers'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_type = db.Column(db.Enum(CustomerType), nullable=False, default=CustomerType.INDIVIDUAL)
    
    # Individual customer fields
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    
    # Organization customer fields
    organization_name = db.Column(db.String(200))
    organization_type = db.Column(db.String(100))  # NGO, Foundation, Government, etc.
    tax_id = db.Column(db.String(50))
    registration_number = db.Column(db.String(100))
    
    # Contact information
    primary_email = db.Column(db.String(120), nullable=False, index=True)
    secondary_email = db.Column(db.String(120))
    phone_primary = db.Column(db.String(20))
    phone_secondary = db.Column(db.String(20))
    website = db.Column(db.String(200))
    
    # Address information
    address_line1 = db.Column(db.String(200))
    address_line2 = db.Column(db.String(200))
    city = db.Column(db.String(100))
    state_province = db.Column(db.String(100))
    postal_code = db.Column(db.String(20))
    country = db.Column(db.String(100))
    
    # Billing address (if different from primary address)
    billing_address_line1 = db.Column(db.String(200))
    billing_address_line2 = db.Column(db.String(200))
    billing_city = db.Column(db.String(100))
    billing_state_province = db.Column(db.String(100))
    billing_postal_code = db.Column(db.String(20))
    billing_country = db.Column(db.String(100))
    
    # Customer preferences
    preferred_currency = db.Column(db.String(3), default='USD')  # ISO currency code
    preferred_language = db.Column(db.String(5), default='en')   # ISO language code
    payment_terms = db.Column(db.Integer, default=30)  # Payment terms in days
    
    # Communication preferences
    email_notifications = db.Column(db.Boolean, default=True)
    sms_notifications = db.Column(db.Boolean, default=False)
    whatsapp_notifications = db.Column(db.Boolean, default=False)
    
    # Status and metadata
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    notes = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_contact_date = db.Column(db.DateTime)
    
    # Relationships
    invoices = db.relationship('Invoice', backref='customer', lazy=True)
    
    def __repr__(self):
        if self.customer_type == CustomerType.INDIVIDUAL:
            return f'<Customer {self.first_name} {self.last_name}>'
        else:
            return f'<Customer {self.organization_name}>'
    
    @property
    def display_name(self):
        """Get display name based on customer type"""
        if self.customer_type == CustomerType.INDIVIDUAL:
            return f"{self.first_name} {self.last_name}".strip()
        else:
            return self.organization_name or "Unknown Organization"
    
    @property
    def full_address(self):
        """Get formatted full address"""
        address_parts = [
            self.address_line1,
            self.address_line2,
            self.city,
            self.state_province,
            self.postal_code,
            self.country
        ]
        return ", ".join([part for part in address_parts if part])
    
    @property
    def full_billing_address(self):
        """Get formatted billing address or fall back to primary address"""
        if self.billing_address_line1:
            billing_parts = [
                self.billing_address_line1,
                self.billing_address_line2,
                self.billing_city,
                self.billing_state_province,
                self.billing_postal_code,
                self.billing_country
            ]
            return ", ".join([part for part in billing_parts if part])
        else:
            return self.full_address
    
    def get_contact_info(self):
        """Get all contact information"""
        return {
            'primary_email': self.primary_email,
            'secondary_email': self.secondary_email,
            'phone_primary': self.phone_primary,
            'phone_secondary': self.phone_secondary,
            'website': self.website
        }
    
    def update_last_contact(self):
        """Update last contact date to current time"""
        self.last_contact_date = datetime.utcnow()
    
    def get_invoice_history(self):
        """Get customer's invoice history with summary statistics"""
        from src.models.invoice import Invoice, InvoiceStatus
        
        invoices = Invoice.query.filter_by(customer_id=self.id).all()
        
        total_invoices = len(invoices)
        total_amount = sum(invoice.total_amount for invoice in invoices)
        paid_invoices = [inv for inv in invoices if inv.status == InvoiceStatus.PAID]
        total_paid = sum(invoice.total_amount for invoice in paid_invoices)
        overdue_invoices = [inv for inv in invoices if inv.status == InvoiceStatus.OVERDUE]
        
        return {
            'total_invoices': total_invoices,
            'total_amount': total_amount,
            'paid_invoices': len(paid_invoices),
            'total_paid': total_paid,
            'overdue_invoices': len(overdue_invoices),
            'outstanding_amount': total_amount - total_paid,
            'recent_invoices': sorted(invoices, key=lambda x: x.created_at, reverse=True)[:5]
        }
    
    def to_dict(self, include_history=False):
        """Convert customer to dictionary"""
        data = {
            'id': self.id,
            'customer_type': self.customer_type.value,
            'display_name': self.display_name,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'organization_name': self.organization_name,
            'organization_type': self.organization_type,
            'tax_id': self.tax_id,
            'registration_number': self.registration_number,
            'contact_info': self.get_contact_info(),
            'address': {
                'line1': self.address_line1,
                'line2': self.address_line2,
                'city': self.city,
                'state_province': self.state_province,
                'postal_code': self.postal_code,
                'country': self.country,
                'full_address': self.full_address
            },
            'billing_address': {
                'line1': self.billing_address_line1,
                'line2': self.billing_address_line2,
                'city': self.billing_city,
                'state_province': self.billing_state_province,
                'postal_code': self.billing_postal_code,
                'country': self.billing_country,
                'full_address': self.full_billing_address
            },
            'preferences': {
                'currency': self.preferred_currency,
                'language': self.preferred_language,
                'payment_terms': self.payment_terms
            },
            'notifications': {
                'email': self.email_notifications,
                'sms': self.sms_notifications,
                'whatsapp': self.whatsapp_notifications
            },
            'is_active': self.is_active,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_contact_date': self.last_contact_date.isoformat() if self.last_contact_date else None
        }
        
        if include_history:
            data['invoice_history'] = self.get_invoice_history()
        
        return data
    
    @classmethod
    def search(cls, query, customer_type=None, is_active=True):
        """Search customers by name, email, or organization"""
        search_filter = cls.query.filter(cls.is_active == is_active)
        
        if customer_type:
            search_filter = search_filter.filter(cls.customer_type == customer_type)
        
        if query:
            search_term = f"%{query}%"
            search_filter = search_filter.filter(
                db.or_(
                    cls.first_name.ilike(search_term),
                    cls.last_name.ilike(search_term),
                    cls.organization_name.ilike(search_term),
                    cls.primary_email.ilike(search_term),
                    cls.secondary_email.ilike(search_term)
                )
            )
        
        return search_filter.order_by(cls.created_at.desc())

