from src.models.user import db
from datetime import datetime
import uuid
from enum import Enum
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship

class ProjectStatus(Enum):
    PLANNING = "planning"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    COMPLETED = "completed"
    CLOSED = "closed"

class FundingType(Enum):
    GRANT = "grant"
    DONATION = "donation"
    CONTRACT = "contract"
    PARTNERSHIP = "partnership"

class Project(db.Model):
    """Model for foundation projects and programs"""
    __tablename__ = 'projects'
    
    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    
    # Basic Information
    project_name = db.Column(db.String(200), nullable=False)
    project_code = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.Text)
    
    # Project Details
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)
    status = db.Column(SQLEnum(ProjectStatus), default=ProjectStatus.PLANNING, nullable=False)
    
    # Location Information
    country = db.Column(db.String(100), default='Kenya')
    region = db.Column(db.String(100))
    county = db.Column(db.String(100))
    specific_location = db.Column(db.String(200))
    
    # Financial Information
    total_budget = db.Column(db.Numeric(15, 2))
    currency = db.Column(db.String(3), default='USD')
    funding_type = db.Column(SQLEnum(FundingType), default=FundingType.GRANT)
    
    # Beneficiary Information
    target_beneficiaries = db.Column(db.Integer)
    direct_beneficiaries = db.Column(db.Integer, default=0)
    indirect_beneficiaries = db.Column(db.Integer, default=0)
    
    # Service Areas (from foundation service areas)
    service_area = db.Column(db.String(100))  # humanitarian_relief, food_security, etc.
    
    # Donor Information
    primary_donor = db.Column(db.String(200))
    donor_reference = db.Column(db.String(100))
    grant_agreement_number = db.Column(db.String(100))
    
    # Project Management
    project_manager_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Status tracking
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    # Relationships
    project_manager = relationship('User', foreign_keys=[project_manager_id], backref='managed_projects')
    creator = relationship('User', foreign_keys=[created_by], backref='created_projects')
    invoices = relationship('Invoice', back_populates='project', lazy='dynamic')
    
    def __init__(self, **kwargs):
        super(Project, self).__init__(**kwargs)
        if not self.project_code:
            self.generate_project_code()
    
    def generate_project_code(self):
        """Generate unique project code"""
        year = datetime.now().year
        # Get count of projects this year
        year_count = Project.query.filter(
            Project.created_at >= datetime(year, 1, 1),
            Project.created_at < datetime(year + 1, 1, 1)
        ).count() + 1
        
        # Format: WHF-YYYY-NNN (Wasat Humanitarian Foundation)
        self.project_code = f"WHF-{year}-{year_count:03d}"
    
    def to_dict(self, include_invoices=False, include_financial=True):
        """Convert project to dictionary"""
        data = {
            'id': self.id,
            'uuid': self.uuid,
            'project_name': self.project_name,
            'project_code': self.project_code,
            'description': self.description,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'status': self.status.value,
            'location': {
                'country': self.country,
                'region': self.region,
                'county': self.county,
                'specific_location': self.specific_location
            },
            'beneficiaries': {
                'target': self.target_beneficiaries,
                'direct': self.direct_beneficiaries,
                'indirect': self.indirect_beneficiaries
            },
            'service_area': self.service_area,
            'donor_info': {
                'primary_donor': self.primary_donor,
                'donor_reference': self.donor_reference,
                'grant_agreement_number': self.grant_agreement_number,
                'funding_type': self.funding_type.value if self.funding_type else None
            },
            'project_manager': {
                'id': self.project_manager.id,
                'name': f"{self.project_manager.first_name} {self.project_manager.last_name}"
            } if self.project_manager else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'is_active': self.is_active
        }
        
        if include_financial:
            data['financial'] = {
                'total_budget': float(self.total_budget) if self.total_budget else 0,
                'currency': self.currency,
                'funding_type': self.funding_type.value if self.funding_type else None
            }
        
        if include_invoices:
            data['invoices'] = [invoice.to_dict(include_line_items=False) for invoice in self.invoices]
        
        return data
    
    def get_total_invoiced(self):
        """Get total amount invoiced for this project"""
        from src.models.invoice import Invoice
        total = db.session.query(db.func.sum(Invoice.total_amount)).filter_by(
            project_id=self.id
        ).scalar()
        return float(total) if total else 0.0
    
    def get_budget_utilization(self):
        """Get budget utilization percentage"""
        if not self.total_budget or self.total_budget == 0:
            return 0.0
        
        total_invoiced = self.get_total_invoiced()
        return (total_invoiced / float(self.total_budget)) * 100
    
    def is_budget_exceeded(self):
        """Check if project budget is exceeded"""
        if not self.total_budget:
            return False
        
        return self.get_total_invoiced() > float(self.total_budget)
    
    def get_remaining_budget(self):
        """Get remaining budget amount"""
        if not self.total_budget:
            return 0.0
        
        return float(self.total_budget) - self.get_total_invoiced()
    
    def update_beneficiary_count(self, direct=None, indirect=None):
        """Update beneficiary counts"""
        if direct is not None:
            self.direct_beneficiaries = direct
        if indirect is not None:
            self.indirect_beneficiaries = indirect
    
    def close_project(self):
        """Close the project"""
        self.status = ProjectStatus.CLOSED
        self.is_active = False
    
    def __repr__(self):
        return f'<Project {self.project_code}: {self.project_name}>'

class ProjectMilestone(db.Model):
    """Model for project milestones and deliverables"""
    __tablename__ = 'project_milestones'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    
    # Milestone Information
    milestone_name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.DateTime)
    completion_date = db.Column(db.DateTime)
    
    # Financial Information
    milestone_value = db.Column(db.Numeric(15, 2))
    is_invoiceable = db.Column(db.Boolean, default=True)
    
    # Status
    is_completed = db.Column(db.Boolean, default=False)
    completion_percentage = db.Column(db.Integer, default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    project = relationship('Project', backref='milestones')
    
    def to_dict(self):
        """Convert milestone to dictionary"""
        return {
            'id': self.id,
            'project_id': self.project_id,
            'milestone_name': self.milestone_name,
            'description': self.description,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'completion_date': self.completion_date.isoformat() if self.completion_date else None,
            'milestone_value': float(self.milestone_value) if self.milestone_value else 0,
            'is_invoiceable': self.is_invoiceable,
            'is_completed': self.is_completed,
            'completion_percentage': self.completion_percentage,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    def mark_completed(self):
        """Mark milestone as completed"""
        self.is_completed = True
        self.completion_date = datetime.utcnow()
        self.completion_percentage = 100
    
    def __repr__(self):
        return f'<ProjectMilestone {self.milestone_name}>'

