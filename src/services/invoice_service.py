import os
import io
import base64
from datetime import datetime
from decimal import Decimal
from jinja2 import Template
from weasyprint import HTML, CSS
from flask import current_app, url_for
from flask_mail import Mail, Message
import qrcode
from PIL import Image, ImageDraw

class InvoiceService:
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize the invoice service with Flask app"""
        self.app = app
        
        # Configure Flask-Mail
        app.config.setdefault('MAIL_SERVER', 'smtp.gmail.com')
        app.config.setdefault('MAIL_PORT', 587)
        app.config.setdefault('MAIL_USE_TLS', True)
        app.config.setdefault('MAIL_USERNAME', os.environ.get('MAIL_USERNAME'))
        app.config.setdefault('MAIL_PASSWORD', os.environ.get('MAIL_PASSWORD'))
        app.config.setdefault('MAIL_DEFAULT_SENDER', os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@wasatpay.com'))
        
        self.mail = Mail(app)
    
    def generate_invoice_pdf(self, invoice, base_url="https://wasatpay.com"):
        """Generate PDF invoice with professional template"""
        try:
            # Generate QR code for payment
            qr_code_data = self._generate_qr_code(invoice, base_url)
            
            # Prepare template data
            template_data = {
                'invoice': invoice.to_dict(include_line_items=True),
                'customer': invoice.customer.to_dict(),
                'qr_code': qr_code_data,
                'payment_url': f"{base_url}/pay/{invoice.uuid}",
                'logo_path': self._get_logo_path(),
                'generated_date': datetime.now().strftime('%B %d, %Y'),
                'base_url': base_url
            }
            
            # Generate HTML from template
            html_content = self._render_invoice_template(template_data)
            
            # Generate PDF
            pdf_buffer = io.BytesIO()
            HTML(string=html_content, base_url=base_url).write_pdf(
                pdf_buffer,
                stylesheets=[CSS(string=self._get_invoice_css())]
            )
            
            pdf_buffer.seek(0)
            return pdf_buffer.getvalue()
            
        except Exception as e:
            current_app.logger.error(f"Error generating invoice PDF: {str(e)}")
            raise
    
    def send_invoice_email(self, invoice, recipient_email=None, include_pdf=True, base_url="https://wasatpay.com"):
        """Send invoice via email with optional PDF attachment"""
        try:
            recipient = recipient_email or invoice.customer.primary_email
            
            # Generate email content
            email_data = {
                'invoice': invoice.to_dict(include_line_items=True),
                'customer': invoice.customer.to_dict(),
                'payment_url': f"{base_url}/pay/{invoice.uuid}",
                'base_url': base_url
            }
            
            subject = f"Invoice {invoice.invoice_number} from Wasat Humanitarian Foundation"
            html_body = self._render_email_template(email_data)
            
            # Create message
            msg = Message(
                subject=subject,
                recipients=[recipient],
                html=html_body
            )
            
            # Attach PDF if requested
            if include_pdf:
                pdf_data = self.generate_invoice_pdf(invoice, base_url)
                msg.attach(
                    filename=f"Invoice_{invoice.invoice_number}.pdf",
                    content_type="application/pdf",
                    data=pdf_data
                )
            
            # Send email
            self.mail.send(msg)
            
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error sending invoice email: {str(e)}")
            raise
    
    def create_payment_link(self, invoice, base_url="https://wasatpay.com"):
        """Create a secure payment link for the invoice"""
        return f"{base_url}/pay/{invoice.uuid}"
    
    def _generate_qr_code(self, invoice, base_url):
        """Generate QR code for invoice payment"""
        payment_url = f"{base_url}/pay/{invoice.uuid}"
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(payment_url)
        qr.make(fit=True)
        
        # Create QR code image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()
        
        return f"data:image/png;base64,{img_str}"
    
    def _get_logo_path(self):
        """Get the path to the Wasat logo"""
        logo_path = os.path.join(
            current_app.static_folder,
            'assets',
            'images',
            'wasat-logo-official.png'
        )
        
        if os.path.exists(logo_path):
            with open(logo_path, 'rb') as f:
                logo_data = base64.b64encode(f.read()).decode()
                return f"data:image/png;base64,{logo_data}"
        
        return None
    
    def _render_invoice_template(self, data):
        """Render the invoice HTML template"""
        template = Template(self._get_invoice_html_template())
        return template.render(**data)
    
    def _render_email_template(self, data):
        """Render the email HTML template"""
        template = Template(self._get_email_html_template())
        return template.render(**data)
    
    def _get_invoice_html_template(self):
        """Get the invoice HTML template"""
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Invoice {{ invoice.invoice_number }}</title>
</head>
<body>
    <div class="invoice-container">
        <!-- Header -->
        <div class="header">
            <div class="logo-section">
                {% if logo_path %}
                <img src="{{ logo_path }}" alt="Wasat Humanitarian Foundation" class="logo">
                {% endif %}
                <div class="company-info">
                    <h1>Wasat Humanitarian Foundation</h1>
                    <p>Humanitarian Services & Development</p>
                </div>
            </div>
            <div class="invoice-info">
                <h2>INVOICE</h2>
                <p><strong>Invoice #:</strong> {{ invoice.invoice_number }}</p>
                <p><strong>Date:</strong> {{ invoice.issue_date }}</p>
                <p><strong>Due Date:</strong> {{ invoice.due_date }}</p>
                {% if invoice.reference_number %}
                <p><strong>Reference:</strong> {{ invoice.reference_number }}</p>
                {% endif %}
            </div>
        </div>

        <!-- Bill To Section -->
        <div class="billing-section">
            <div class="bill-to">
                <h3>Bill To:</h3>
                <div class="customer-info">
                    <p><strong>{{ customer.display_name }}</strong></p>
                    {% if customer.organization_name %}
                    <p>{{ customer.organization_name }}</p>
                    {% endif %}
                    <p>{{ customer.primary_email }}</p>
                    {% if customer.phone_primary %}
                    <p>{{ customer.phone_primary }}</p>
                    {% endif %}
                    {% if customer.address.full_address %}
                    <p>{{ customer.address.full_address }}</p>
                    {% endif %}
                </div>
            </div>
            <div class="payment-info">
                <div class="qr-section">
                    <h4>Pay Online</h4>
                    <img src="{{ qr_code }}" alt="Payment QR Code" class="qr-code">
                    <p class="payment-url">{{ payment_url }}</p>
                </div>
            </div>
        </div>

        <!-- Line Items -->
        <div class="items-section">
            <table class="items-table">
                <thead>
                    <tr>
                        <th>Description</th>
                        <th>Qty</th>
                        <th>Unit Price</th>
                        <th>Total</th>
                    </tr>
                </thead>
                <tbody>
                    {% for item in invoice.line_items %}
                    <tr>
                        <td>
                            <div class="item-description">
                                {{ item.description }}
                                {% if item.product_code %}
                                <small>({{ item.product_code }})</small>
                                {% endif %}
                            </div>
                        </td>
                        <td>{{ item.quantity }}{% if item.unit_of_measure %} {{ item.unit_of_measure }}{% endif %}</td>
                        <td>{{ invoice.currency }} {{ "%.2f"|format(item.unit_price) }}</td>
                        <td>{{ invoice.currency }} {{ "%.2f"|format(item.total_amount) }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <!-- Totals -->
        <div class="totals-section">
            <div class="totals-table">
                <div class="total-row">
                    <span>Subtotal:</span>
                    <span>{{ invoice.currency }} {{ "%.2f"|format(invoice.subtotal) }}</span>
                </div>
                {% if invoice.tax_amount > 0 %}
                <div class="total-row">
                    <span>Tax ({{ invoice.tax_rate }}%):</span>
                    <span>{{ invoice.currency }} {{ "%.2f"|format(invoice.tax_amount) }}</span>
                </div>
                {% endif %}
                {% if invoice.discount_amount > 0 %}
                <div class="total-row">
                    <span>Discount:</span>
                    <span>-{{ invoice.currency }} {{ "%.2f"|format(invoice.discount_amount) }}</span>
                </div>
                {% endif %}
                <div class="total-row final-total">
                    <span><strong>Total Amount:</strong></span>
                    <span><strong>{{ invoice.currency }} {{ "%.2f"|format(invoice.total_amount) }}</strong></span>
                </div>
            </div>
        </div>

        <!-- Payment Instructions -->
        <div class="payment-section">
            <h3>Payment Instructions</h3>
            <div class="payment-methods">
                <div class="payment-method">
                    <h4>Online Payment</h4>
                    <p>Scan the QR code above or visit: <a href="{{ payment_url }}">{{ payment_url }}</a></p>
                    <p>We accept credit cards, bank transfers, and mobile money payments.</p>
                </div>
                {% if invoice.payment_instructions %}
                <div class="payment-method">
                    <h4>Additional Instructions</h4>
                    <p>{{ invoice.payment_instructions }}</p>
                </div>
                {% endif %}
            </div>
            <p class="payment-terms">Payment Terms: {{ invoice.payment_terms }} days</p>
        </div>

        <!-- Notes -->
        {% if invoice.notes %}
        <div class="notes-section">
            <h3>Notes</h3>
            <p>{{ invoice.notes }}</p>
        </div>
        {% endif %}

        <!-- Footer -->
        <div class="footer">
            <p>Thank you for supporting Wasat Humanitarian Foundation</p>
            <p>For questions about this invoice, please contact us at finance@wasatfoundation.org</p>
            <p class="generated-date">Generated on {{ generated_date }}</p>
        </div>
    </div>
</body>
</html>
        """
    
    def _get_email_html_template(self):
        """Get the email HTML template"""
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Invoice {{ invoice.invoice_number }}</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { text-align: center; margin-bottom: 30px; }
        .logo { max-height: 80px; margin-bottom: 10px; }
        .invoice-summary { background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; }
        .payment-button { display: inline-block; background: #007bff; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; margin: 20px 0; }
        .footer { margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; font-size: 14px; color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Wasat Humanitarian Foundation</h1>
            <p>Invoice {{ invoice.invoice_number }}</p>
        </div>
        
        <p>Dear {{ customer.display_name }},</p>
        
        <p>Thank you for your continued support of Wasat Humanitarian Foundation. Please find your invoice details below:</p>
        
        <div class="invoice-summary">
            <h3>Invoice Summary</h3>
            <p><strong>Invoice Number:</strong> {{ invoice.invoice_number }}</p>
            <p><strong>Issue Date:</strong> {{ invoice.issue_date }}</p>
            <p><strong>Due Date:</strong> {{ invoice.due_date }}</p>
            <p><strong>Amount Due:</strong> {{ invoice.currency }} {{ "%.2f"|format(invoice.total_amount) }}</p>
        </div>
        
        <p>You can pay this invoice securely online by clicking the button below:</p>
        
        <div style="text-align: center;">
            <a href="{{ payment_url }}" class="payment-button">Pay Invoice Online</a>
        </div>
        
        <p>Or visit: <a href="{{ payment_url }}">{{ payment_url }}</a></p>
        
        <p>We accept the following payment methods:</p>
        <ul>
            <li>Credit and Debit Cards</li>
            <li>Bank Transfer</li>
            <li>Mobile Money (M-Pesa, etc.)</li>
        </ul>
        
        <p>If you have any questions about this invoice, please don't hesitate to contact us.</p>
        
        <div class="footer">
            <p>Best regards,<br>
            Wasat Humanitarian Foundation<br>
            Email: finance@wasatfoundation.org</p>
            
            <p><em>This is an automated message. Please do not reply to this email.</em></p>
        </div>
    </div>
</body>
</html>
        """
    
    def _get_invoice_css(self):
        """Get the CSS styles for the invoice"""
        return """
        @page {
            size: A4;
            margin: 1in;
        }
        
        body {
            font-family: 'Arial', sans-serif;
            font-size: 12px;
            line-height: 1.4;
            color: #333;
            margin: 0;
            padding: 0;
        }
        
        .invoice-container {
            max-width: 800px;
            margin: 0 auto;
        }
        
        .header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 2px solid #e74c3c;
        }
        
        .logo-section {
            display: flex;
            align-items: center;
            gap: 15px;
        }
        
        .logo {
            max-height: 60px;
            width: auto;
        }
        
        .company-info h1 {
            margin: 0;
            font-size: 24px;
            color: #e74c3c;
            font-weight: bold;
        }
        
        .company-info p {
            margin: 5px 0 0 0;
            color: #666;
            font-size: 14px;
        }
        
        .invoice-info {
            text-align: right;
        }
        
        .invoice-info h2 {
            margin: 0 0 10px 0;
            font-size: 28px;
            color: #e74c3c;
            font-weight: bold;
        }
        
        .invoice-info p {
            margin: 5px 0;
            font-size: 14px;
        }
        
        .billing-section {
            display: flex;
            justify-content: space-between;
            margin-bottom: 40px;
        }
        
        .bill-to {
            flex: 1;
        }
        
        .bill-to h3 {
            margin: 0 0 15px 0;
            font-size: 16px;
            color: #333;
            border-bottom: 1px solid #ddd;
            padding-bottom: 5px;
        }
        
        .customer-info p {
            margin: 5px 0;
            font-size: 14px;
        }
        
        .payment-info {
            text-align: center;
            margin-left: 40px;
        }
        
        .qr-section h4 {
            margin: 0 0 10px 0;
            font-size: 14px;
            color: #333;
        }
        
        .qr-code {
            width: 120px;
            height: 120px;
            border: 1px solid #ddd;
            margin-bottom: 10px;
        }
        
        .payment-url {
            font-size: 10px;
            color: #666;
            word-break: break-all;
            margin: 0;
        }
        
        .items-section {
            margin-bottom: 30px;
        }
        
        .items-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }
        
        .items-table th {
            background-color: #f8f9fa;
            padding: 12px;
            text-align: left;
            border: 1px solid #ddd;
            font-weight: bold;
            font-size: 14px;
        }
        
        .items-table td {
            padding: 12px;
            border: 1px solid #ddd;
            vertical-align: top;
        }
        
        .items-table tbody tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        
        .item-description {
            font-weight: 500;
        }
        
        .item-description small {
            color: #666;
            font-weight: normal;
        }
        
        .totals-section {
            display: flex;
            justify-content: flex-end;
            margin-bottom: 40px;
        }
        
        .totals-table {
            min-width: 300px;
        }
        
        .total-row {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #eee;
        }
        
        .final-total {
            border-top: 2px solid #333;
            border-bottom: 2px solid #333;
            font-size: 16px;
            margin-top: 10px;
            padding-top: 15px;
        }
        
        .payment-section {
            margin-bottom: 30px;
            padding: 20px;
            background-color: #f8f9fa;
            border-radius: 8px;
        }
        
        .payment-section h3 {
            margin: 0 0 15px 0;
            color: #333;
            font-size: 18px;
        }
        
        .payment-methods {
            margin-bottom: 15px;
        }
        
        .payment-method {
            margin-bottom: 15px;
        }
        
        .payment-method h4 {
            margin: 0 0 8px 0;
            color: #e74c3c;
            font-size: 14px;
        }
        
        .payment-method p {
            margin: 5px 0;
            font-size: 13px;
        }
        
        .payment-terms {
            font-weight: bold;
            color: #333;
            margin-top: 15px;
        }
        
        .notes-section {
            margin-bottom: 30px;
            padding: 15px;
            background-color: #fff3cd;
            border-left: 4px solid #ffc107;
        }
        
        .notes-section h3 {
            margin: 0 0 10px 0;
            color: #856404;
            font-size: 16px;
        }
        
        .footer {
            text-align: center;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            color: #666;
            font-size: 12px;
        }
        
        .footer p {
            margin: 5px 0;
        }
        
        .generated-date {
            font-style: italic;
            margin-top: 15px;
        }
        
        a {
            color: #007bff;
            text-decoration: none;
        }
        
        a:hover {
            text-decoration: underline;
        }
        """

# Global instance
invoice_service = InvoiceService()

