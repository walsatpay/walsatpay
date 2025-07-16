from flask import Blueprint, request, jsonify
from src.models.user import db
from src.models.project import Project, ProjectStatus, FundingType, ProjectMilestone
from src.routes.auth import token_required
from src.services.foundation_service import foundation_service
from datetime import datetime
from sqlalchemy import or_

project_bp = Blueprint('project', __name__)

@project_bp.route('/', methods=['GET'])
@token_required
def get_projects(current_user):
    """Get all projects with optional filtering and pagination"""
    try:
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        search = request.args.get('search', '').strip()
        status = request.args.get('status', '').strip()
        service_area = request.args.get('service_area', '').strip()
        funding_type = request.args.get('funding_type', '').strip()
        is_active = request.args.get('active', 'true').lower() == 'true'
        
        # Build query
        query = Project.query.filter_by(is_active=is_active)
        
        # Apply status filter
        if status and status in [s.value for s in ProjectStatus]:
            query = query.filter_by(status=ProjectStatus(status))
        
        # Apply service area filter
        if service_area:
            query = query.filter_by(service_area=service_area)
        
        # Apply funding type filter
        if funding_type and funding_type in [f.value for f in FundingType]:
            query = query.filter_by(funding_type=FundingType(funding_type))
        
        # Apply search filter
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    Project.project_name.ilike(search_term),
                    Project.project_code.ilike(search_term),
                    Project.primary_donor.ilike(search_term),
                    Project.county.ilike(search_term)
                )
            )
        
        # Order by creation date (newest first)
        query = query.order_by(Project.created_at.desc())
        
        # Paginate results
        pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        projects = [project.to_dict(include_financial=True) for project in pagination.items]
        
        return jsonify({
            'projects': projects,
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
        return jsonify({'error': 'Failed to retrieve projects', 'details': str(e)}), 500

@project_bp.route('/<int:project_id>', methods=['GET'])
@token_required
def get_project(current_user, project_id):
    """Get a specific project by ID"""
    try:
        project = Project.query.get(project_id)
        
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        include_invoices = request.args.get('include_invoices', 'false').lower() == 'true'
        include_milestones = request.args.get('include_milestones', 'false').lower() == 'true'
        
        project_data = project.to_dict(include_invoices=include_invoices)
        
        # Add financial summary
        project_data['financial_summary'] = {
            'total_invoiced': project.get_total_invoiced(),
            'budget_utilization': project.get_budget_utilization(),
            'remaining_budget': project.get_remaining_budget(),
            'is_budget_exceeded': project.is_budget_exceeded()
        }
        
        # Add milestones if requested
        if include_milestones:
            project_data['milestones'] = [milestone.to_dict() for milestone in project.milestones]
        
        return jsonify({
            'project': project_data
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to retrieve project', 'details': str(e)}), 500

@project_bp.route('/', methods=['POST'])
@token_required
def create_project(current_user):
    """Create a new project"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        if not data.get('project_name'):
            return jsonify({'error': 'Project name is required'}), 400
        
        # Validate enums
        status = data.get('status', 'planning')
        if status not in [s.value for s in ProjectStatus]:
            return jsonify({'error': 'Invalid project status'}), 400
        
        funding_type = data.get('funding_type', 'grant')
        if funding_type not in [f.value for f in FundingType]:
            return jsonify({'error': 'Invalid funding type'}), 400
        
        # Create new project
        project = Project(
            project_name=data['project_name'].strip(),
            description=data.get('description', '').strip() or None,
            status=ProjectStatus(status),
            funding_type=FundingType(funding_type),
            created_by=current_user.id
        )
        
        # Set dates
        if data.get('start_date'):
            try:
                project.start_date = datetime.strptime(data['start_date'], '%Y-%m-%d')
            except ValueError:
                return jsonify({'error': 'Invalid start_date format. Use YYYY-MM-DD'}), 400
        
        if data.get('end_date'):
            try:
                project.end_date = datetime.strptime(data['end_date'], '%Y-%m-%d')
            except ValueError:
                return jsonify({'error': 'Invalid end_date format. Use YYYY-MM-DD'}), 400
        
        # Set location information
        project.country = data.get('country', 'Kenya')
        project.region = data.get('region', '').strip() or None
        project.county = data.get('county', '').strip() or None
        project.specific_location = data.get('specific_location', '').strip() or None
        
        # Set financial information
        if data.get('total_budget'):
            project.total_budget = data['total_budget']
        project.currency = data.get('currency', 'USD')
        
        # Set beneficiary information
        if data.get('target_beneficiaries'):
            project.target_beneficiaries = data['target_beneficiaries']
        
        # Set service area
        project.service_area = data.get('service_area', '').strip() or None
        
        # Set donor information
        project.primary_donor = data.get('primary_donor', '').strip() or None
        project.donor_reference = data.get('donor_reference', '').strip() or None
        project.grant_agreement_number = data.get('grant_agreement_number', '').strip() or None
        
        # Set project manager
        if data.get('project_manager_id'):
            from src.models.user import User
            manager = User.query.get(data['project_manager_id'])
            if manager:
                project.project_manager_id = manager.id
        
        db.session.add(project)
        db.session.commit()
        
        return jsonify({
            'message': 'Project created successfully',
            'project': project.to_dict(include_financial=True)
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to create project', 'details': str(e)}), 500

@project_bp.route('/<int:project_id>', methods=['PUT'])
@token_required
def update_project(current_user, project_id):
    """Update an existing project"""
    try:
        project = Project.query.get(project_id)
        
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Update basic fields
        if 'project_name' in data:
            project.project_name = data['project_name'].strip()
        
        if 'description' in data:
            project.description = data['description'].strip() or None
        
        # Update status
        if 'status' in data:
            status = data['status']
            if status not in [s.value for s in ProjectStatus]:
                return jsonify({'error': 'Invalid project status'}), 400
            project.status = ProjectStatus(status)
        
        # Update dates
        if 'start_date' in data:
            if data['start_date']:
                try:
                    project.start_date = datetime.strptime(data['start_date'], '%Y-%m-%d')
                except ValueError:
                    return jsonify({'error': 'Invalid start_date format. Use YYYY-MM-DD'}), 400
            else:
                project.start_date = None
        
        if 'end_date' in data:
            if data['end_date']:
                try:
                    project.end_date = datetime.strptime(data['end_date'], '%Y-%m-%d')
                except ValueError:
                    return jsonify({'error': 'Invalid end_date format. Use YYYY-MM-DD'}), 400
            else:
                project.end_date = None
        
        # Update location
        location_fields = ['country', 'region', 'county', 'specific_location']
        for field in location_fields:
            if field in data:
                setattr(project, field, data[field].strip() or None)
        
        # Update financial information
        if 'total_budget' in data:
            project.total_budget = data['total_budget']
        
        if 'currency' in data:
            project.currency = data['currency']
        
        if 'funding_type' in data:
            funding_type = data['funding_type']
            if funding_type not in [f.value for f in FundingType]:
                return jsonify({'error': 'Invalid funding type'}), 400
            project.funding_type = FundingType(funding_type)
        
        # Update beneficiary information
        if 'target_beneficiaries' in data:
            project.target_beneficiaries = data['target_beneficiaries']
        
        if 'direct_beneficiaries' in data:
            project.direct_beneficiaries = data['direct_beneficiaries']
        
        if 'indirect_beneficiaries' in data:
            project.indirect_beneficiaries = data['indirect_beneficiaries']
        
        # Update service area
        if 'service_area' in data:
            project.service_area = data['service_area'].strip() or None
        
        # Update donor information
        donor_fields = ['primary_donor', 'donor_reference', 'grant_agreement_number']
        for field in donor_fields:
            if field in data:
                setattr(project, field, data[field].strip() or None)
        
        # Update project manager
        if 'project_manager_id' in data:
            if data['project_manager_id']:
                from src.models.user import User
                manager = User.query.get(data['project_manager_id'])
                if manager:
                    project.project_manager_id = manager.id
                else:
                    return jsonify({'error': 'Project manager not found'}), 404
            else:
                project.project_manager_id = None
        
        # Update active status
        if 'is_active' in data:
            project.is_active = data['is_active']
        
        db.session.commit()
        
        return jsonify({
            'message': 'Project updated successfully',
            'project': project.to_dict(include_financial=True)
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to update project', 'details': str(e)}), 500

@project_bp.route('/<int:project_id>/close', methods=['POST'])
@token_required
def close_project(current_user, project_id):
    """Close a project"""
    try:
        project = Project.query.get(project_id)
        
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        project.close_project()
        db.session.commit()
        
        return jsonify({
            'message': 'Project closed successfully',
            'project': project.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to close project', 'details': str(e)}), 500

@project_bp.route('/templates', methods=['GET'])
@token_required
def get_project_templates(current_user):
    """Get project templates and foundation information"""
    try:
        foundation_info = foundation_service.get_foundation_info()
        
        return jsonify({
            'foundation': foundation_info,
            'service_areas': list(foundation_info['service_areas'].keys()),
            'donor_types': foundation_service.get_donor_suggestions(),
            'invoice_templates': foundation_service.get_invoice_templates(),
            'project_budget_ranges': foundation_service.PROJECT_BUDGET_RANGES,
            'payment_terms': foundation_service.PAYMENT_TERMS
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to retrieve templates', 'details': str(e)}), 500

@project_bp.route('/stats', methods=['GET'])
@token_required
def get_project_stats(current_user):
    """Get project statistics"""
    try:
        # Get all projects
        projects = Project.query.filter_by(is_active=True).all()
        
        # Calculate statistics
        total_projects = len(projects)
        total_budget = sum(float(p.total_budget) for p in projects if p.total_budget)
        total_invoiced = sum(p.get_total_invoiced() for p in projects)
        
        # Group by status
        status_counts = {}
        for status in ProjectStatus:
            status_projects = [p for p in projects if p.status == status]
            status_counts[status.value] = len(status_projects)
        
        # Group by service area
        service_area_counts = {}
        for project in projects:
            if project.service_area:
                service_area_counts[project.service_area] = service_area_counts.get(project.service_area, 0) + 1
        
        # Recent projects
        recent_projects = sorted(projects, key=lambda x: x.created_at, reverse=True)[:5]
        
        return jsonify({
            'total_projects': total_projects,
            'total_budget': total_budget,
            'total_invoiced': total_invoiced,
            'budget_utilization': (total_invoiced / total_budget * 100) if total_budget > 0 else 0,
            'status_counts': status_counts,
            'service_area_counts': service_area_counts,
            'recent_projects': [p.to_dict(include_financial=False) for p in recent_projects]
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to retrieve project statistics', 'details': str(e)}), 500

