"""
Foundation-specific service for Wasat Humanitarian Foundation
Customizes the WasatPay system based on the foundation's operations and needs
"""

class FoundationService:
    """Service class for Wasat Humanitarian Foundation specific operations"""
    
    # Foundation Information
    FOUNDATION_INFO = {
        'name': 'Wasat Humanitarian Foundation',
        'registration': 'Registered NGO under the NGO Coordination Act of Kenya',
        'website': 'www.wasathumanitarianfoundation.org',
        'email': 'finance@wasatfoundation.org',
        'contact_person': 'Abdirisack Sheikh',
        'phone': '+254733722221',
        'address': {
            'country': 'Kenya',
            'region': 'Northern Kenya',
            'focus_areas': ['Wajir County', 'ASAL Regions']
        }
    }
    
    # Mission and Vision
    MISSION = """
    To substantially contribute to reducing social injustice and vulnerability among 
    underserved pastoralist communities through holistic interventions. Recognizing 
    the challenges posed by erratic and unreliable rainfall in Arid and Semi-Arid 
    Lands (ASALs) counties in Kenya, the foundation focuses on implementing climate 
    change adaptation programs in these regions.
    """
    
    VISION = """
    To improve the lives of people living in the Northern Region of Kenya by enhancing 
    food security, delivering essential social services, reducing livelihood vulnerability, 
    and promoting the sustainable use of local resources.
    """
    
    # Core Values
    CORE_VALUES = [
        'Integrity',
        'Equity (Fairness, non-discrimination)',
        'Inclusivity',
        'Accountability'
    ]
    
    # Service Areas
    SERVICE_AREAS = {
        'humanitarian_relief': {
            'name': 'Humanitarian Relief',
            'description': 'Immediate humanitarian relief during post-disaster situations including droughts, floods, and other natural disasters.',
            'typical_items': [
                'Emergency Food Distribution',
                'Water and Sanitation Services',
                'Temporary Shelter Provision',
                'Medical Aid and Healthcare',
                'Emergency Response Team Deployment'
            ]
        },
        'food_security': {
            'name': 'Food Security Enhancement',
            'description': 'Promoting sustainable agricultural practices and providing access to drought-resistant crops and livestock breeds.',
            'typical_items': [
                'Drought-Resistant Crop Seeds',
                'Livestock Breed Improvement',
                'Small-Scale Farming Support',
                'Agribusiness Venture Development',
                'Agricultural Training Programs'
            ]
        },
        'social_services': {
            'name': 'Social Services Delivery',
            'description': 'Delivery of essential social services including healthcare, education, and clean water access.',
            'typical_items': [
                'Healthcare Facility Support',
                'Educational Resource Provision',
                'Clean Water Infrastructure',
                'Community Health Programs',
                'Educational Training and Workshops'
            ]
        },
        'livelihood_support': {
            'name': 'Livelihood Vulnerability Reduction',
            'description': 'Training, capacity-building, and entrepreneurship support to reduce livelihood vulnerability.',
            'typical_items': [
                'Vocational Training Programs',
                'Entrepreneurship Development',
                'Income-Generating Activities',
                'Community-Based Organization Support',
                'Self-Help Group Formation'
            ]
        },
        'climate_adaptation': {
            'name': 'Climate Change Adaptation Programs',
            'description': 'Programs designed to mitigate adverse effects of erratic rainfall in ASAL counties.',
            'typical_items': [
                'Water Management Systems',
                'Sustainable Agricultural Practices',
                'Livelihood Diversification',
                'Climate Resilience Training',
                'Disaster Risk Reduction'
            ]
        }
    }
    
    # Common Donor Types
    DONOR_TYPES = {
        'international_organizations': [
            'United Nations Agencies',
            'World Bank',
            'African Development Bank',
            'European Union',
            'USAID'
        ],
        'foundations': [
            'Private Foundations',
            'Corporate Foundations',
            'Family Foundations',
            'Community Foundations'
        ],
        'government_agencies': [
            'Kenya Government Ministries',
            'County Governments',
            'Foreign Government Aid Agencies',
            'Embassy Programs'
        ],
        'corporate_partners': [
            'Corporate Social Responsibility Programs',
            'Private Companies',
            'Local Businesses',
            'International Corporations'
        ]
    }
    
    # Typical Project Budget Ranges
    PROJECT_BUDGET_RANGES = {
        'small_projects': {'min': 5000, 'max': 50000, 'currency': 'USD'},
        'medium_projects': {'min': 50000, 'max': 500000, 'currency': 'USD'},
        'large_projects': {'min': 500000, 'max': 5000000, 'currency': 'USD'}
    }
    
    # Payment Terms for Different Donor Types
    PAYMENT_TERMS = {
        'international_organizations': 45,  # days
        'foundations': 30,
        'government_agencies': 60,
        'corporate_partners': 30,
        'individual_donors': 15
    }
    
    # Common Invoice Line Items Templates
    INVOICE_TEMPLATES = {
        'humanitarian_relief': [
            {
                'description': 'Emergency Food Distribution - Wajir County',
                'unit_of_measure': 'beneficiaries',
                'category': 'humanitarian_relief'
            },
            {
                'description': 'Water and Sanitation Services',
                'unit_of_measure': 'households',
                'category': 'humanitarian_relief'
            },
            {
                'description': 'Temporary Shelter Provision',
                'unit_of_measure': 'families',
                'category': 'humanitarian_relief'
            }
        ],
        'capacity_building': [
            {
                'description': 'Community Training Workshop',
                'unit_of_measure': 'sessions',
                'category': 'capacity_building'
            },
            {
                'description': 'Vocational Skills Training',
                'unit_of_measure': 'participants',
                'category': 'capacity_building'
            }
        ],
        'infrastructure': [
            {
                'description': 'Water Point Construction',
                'unit_of_measure': 'units',
                'category': 'infrastructure'
            },
            {
                'description': 'School Infrastructure Support',
                'unit_of_measure': 'facilities',
                'category': 'infrastructure'
            }
        ]
    }
    
    @classmethod
    def get_foundation_info(cls):
        """Get complete foundation information"""
        return {
            'info': cls.FOUNDATION_INFO,
            'mission': cls.MISSION,
            'vision': cls.VISION,
            'core_values': cls.CORE_VALUES,
            'service_areas': cls.SERVICE_AREAS
        }
    
    @classmethod
    def get_donor_suggestions(cls, donor_type=None):
        """Get donor type suggestions"""
        if donor_type and donor_type in cls.DONOR_TYPES:
            return cls.DONOR_TYPES[donor_type]
        return cls.DONOR_TYPES
    
    @classmethod
    def get_payment_terms_for_donor(cls, donor_type):
        """Get recommended payment terms based on donor type"""
        return cls.PAYMENT_TERMS.get(donor_type, 30)  # Default 30 days
    
    @classmethod
    def get_invoice_templates(cls, category=None):
        """Get invoice line item templates"""
        if category and category in cls.INVOICE_TEMPLATES:
            return cls.INVOICE_TEMPLATES[category]
        return cls.INVOICE_TEMPLATES
    
    @classmethod
    def get_project_budget_range(cls, project_size):
        """Get typical budget range for project size"""
        return cls.PROJECT_BUDGET_RANGES.get(project_size, cls.PROJECT_BUDGET_RANGES['medium_projects'])
    
    @classmethod
    def customize_invoice_description(cls, service_area, location='Wajir County'):
        """Generate customized invoice descriptions based on service area"""
        if service_area not in cls.SERVICE_AREAS:
            return None
        
        service = cls.SERVICE_AREAS[service_area]
        return {
            'service_name': service['name'],
            'description': service['description'],
            'location': location,
            'typical_items': service['typical_items']
        }
    
    @classmethod
    def get_bank_details(cls):
        """Get foundation's bank details for payment instructions"""
        return {
            'bank_name': 'Kenya Commercial Bank (KCB)',
            'account_name': 'Wasat Humanitarian Foundation',
            'account_number': 'To be provided',
            'swift_code': 'KCBLKENX',
            'branch': 'Wajir Branch',
            'currency_accounts': {
                'KES': 'Kenya Shillings Account',
                'USD': 'US Dollar Account',
                'EUR': 'Euro Account'
            },
            'mobile_money': {
                'mpesa': {
                    'paybill': 'To be provided',
                    'account': 'Wasat Foundation'
                }
            }
        }
    
    @classmethod
    def get_compliance_info(cls):
        """Get compliance and registration information"""
        return {
            'ngo_registration': 'Registered under NGO Coordination Act of Kenya',
            'tax_exemption': 'Tax exempt status under Kenya Revenue Authority',
            'certifications': [
                'NGO Coordination Board Certificate',
                'Certificate of Compliance',
                'Tax Exemption Certificate'
            ],
            'reporting_requirements': [
                'Annual NGO Board Reports',
                'Donor Financial Reports',
                'Government Compliance Reports',
                'Audit Reports'
            ]
        }

# Global instance
foundation_service = FoundationService()

