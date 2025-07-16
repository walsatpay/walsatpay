import os
import sys
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
from src.config import get_config
from src.models.user import db
from src.models.customer import Customer
from src.models.invoice import Invoice, InvoiceLineItem, InvoiceStatusHistory
from src.models.payment import Payment, PaymentRefund, PaymentHistory
from src.models.project import Project, ProjectMilestone

# Import route blueprints
from src.routes.user import user_bp
from src.routes.auth import auth_bp
from src.routes.customer import customer_bp
from src.routes.invoice import invoice_bp
from src.routes.invoice_pdf import invoice_pdf_bp
from src.routes.payment import payment_bp
from src.routes.public_payment import public_payment_bp
from src.routes.project import project_bp

def create_app(config_name=None):
    """Application factory pattern"""
    app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
    
    # Load configuration
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    config_class = get_config()
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    
    # Configure CORS
    CORS(app, origins=app.config['CORS_ORIGINS'], supports_credentials=True)
    
    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(user_bp, url_prefix='/api/users')
    app.register_blueprint(customer_bp, url_prefix='/api/customers')
    app.register_blueprint(invoice_bp, url_prefix='/api/invoices')
    app.register_blueprint(invoice_pdf_bp, url_prefix='/api/invoices')
    app.register_blueprint(payment_bp, url_prefix='/api/payments')
    app.register_blueprint(public_payment_bp, url_prefix='/api/public')
    app.register_blueprint(project_bp, url_prefix='/api/projects')
    
    # Create database tables
    with app.app_context():
        # Ensure database directory exists for SQLite
        if 'sqlite' in app.config['SQLALCHEMY_DATABASE_URI']:
            db_dir = os.path.dirname(app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', ''))
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
        
        try:
            db.create_all()
            print("Database tables created successfully")
        except Exception as e:
            print(f"Error creating database tables: {e}")
    
    # Health check endpoint
    @app.route('/api/health')
    def health_check():
        """Health check endpoint for load balancers"""
        try:
            # Test database connection
            db.session.execute('SELECT 1')
            db_status = 'healthy'
        except Exception as e:
            db_status = f'unhealthy: {str(e)}'
        
        return jsonify({
            'status': 'healthy' if db_status == 'healthy' else 'unhealthy',
            'database': db_status,
            'service': 'WasatPay API',
            'version': '1.0.0',
            'environment': os.environ.get('FLASK_ENV', 'development')
        }), 200 if db_status == 'healthy' else 503
    
    # API info endpoint
    @app.route('/api')
    def api_info():
        """API information endpoint"""
        return jsonify({
            'service': 'WasatPay API',
            'version': '1.0.0',
            'description': 'Invoicing and Payment Gateway for Wasat Humanitarian Foundation',
            'endpoints': {
                'health': '/api/health',
                'auth': '/api/auth',
                'users': '/api/users',
                'customers': '/api/customers',
                'invoices': '/api/invoices',
                'payments': '/api/payments',
                'projects': '/api/projects',
                'public_payment': '/api/public'
            },
            'foundation': {
                'name': app.config['FOUNDATION_NAME'],
                'website': app.config['FOUNDATION_WEBSITE']
            }
        })
    
    # Serve static files and handle SPA routing
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_frontend(path):
        """Serve frontend static files or API info"""
        static_folder_path = app.static_folder
        
        # If path is empty or doesn't exist, try to serve index.html
        if path == '' or not os.path.exists(os.path.join(static_folder_path, path)):
            index_path = os.path.join(static_folder_path, 'index.html')
            if os.path.exists(index_path):
                return send_from_directory(static_folder_path, 'index.html')
            else:
                return jsonify({
                    'message': 'WasatPay API is running',
                    'endpoints': {
                        'health': '/api/health',
                        'auth': '/api/auth',
                        'users': '/api/users',
                        'customers': '/api/customers',
                        'invoices': '/api/invoices',
                        'payments': '/api/payments',
                        'projects': '/api/projects',
                        'public_payment': '/api/public'
                    }
                })
        
        # Serve the requested static file
        return send_from_directory(static_folder_path, path)
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Not found'}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500
    
    return app

# Create the app instance
app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)

