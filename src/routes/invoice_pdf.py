from flask import Blueprint, request, jsonify, send_file, current_app
from src.models.user import db
from src.models.invoice import Invoice
from src.routes.auth import token_required
from src.services.invoice_service import invoice_service
import io
import tempfile
import os

invoice_pdf_bp = Blueprint('invoice_pdf', __name__)

@invoice_pdf_bp.route('/<int:invoice_id>/pdf', methods=['GET'])
@token_required
def generate_invoice_pdf(current_user, invoice_id):
    """Generate and download invoice PDF"""
    try:
        invoice = Invoice.query.get(invoice_id)
        
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404
        
        base_url = request.args.get('base_url', request.host_url.rstrip('/'))
        
        # Generate PDF
        pdf_data = invoice_service.generate_invoice_pdf(invoice, base_url)
        
        # Create a temporary file to serve the PDF
        pdf_buffer = io.BytesIO(pdf_data)
        pdf_buffer.seek(0)
        
        filename = f"Invoice_{invoice.invoice_number}.pdf"
        
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
        
    except Exception as e:
        current_app.logger.error(f"Error generating PDF for invoice {invoice_id}: {str(e)}")
        return jsonify({'error': 'Failed to generate PDF', 'details': str(e)}), 500

@invoice_pdf_bp.route('/<int:invoice_id>/email', methods=['POST'])
@token_required
def send_invoice_email(current_user, invoice_id):
    """Send invoice via email"""
    try:
        invoice = Invoice.query.get(invoice_id)
        
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404
        
        data = request.get_json() or {}
        
        recipient_email = data.get('recipient_email') or invoice.customer.primary_email
        include_pdf = data.get('include_pdf', True)
        base_url = data.get('base_url', request.host_url.rstrip('/'))
        
        # Validate email address
        if not recipient_email:
            return jsonify({'error': 'Recipient email is required'}), 400
        
        # Send email
        success = invoice_service.send_invoice_email(
            invoice=invoice,
            recipient_email=recipient_email,
            include_pdf=include_pdf,
            base_url=base_url
        )
        
        if success:
            # Update invoice status to sent if it was draft
            if invoice.status.value == 'draft':
                from src.models.invoice import InvoiceStatus
                invoice.update_status(InvoiceStatus.SENT, current_user.id, "Invoice sent via email")
                db.session.commit()
            
            return jsonify({
                'message': 'Invoice sent successfully',
                'recipient': recipient_email,
                'include_pdf': include_pdf
            }), 200
        else:
            return jsonify({'error': 'Failed to send email'}), 500
        
    except Exception as e:
        current_app.logger.error(f"Error sending email for invoice {invoice_id}: {str(e)}")
        return jsonify({'error': 'Failed to send email', 'details': str(e)}), 500

@invoice_pdf_bp.route('/<int:invoice_id>/preview', methods=['GET'])
@token_required
def preview_invoice(current_user, invoice_id):
    """Preview invoice HTML (for testing purposes)"""
    try:
        invoice = Invoice.query.get(invoice_id)
        
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404
        
        base_url = request.args.get('base_url', request.host_url.rstrip('/'))
        
        # Generate QR code
        qr_code_data = invoice_service._generate_qr_code(invoice, base_url)
        
        # Prepare template data
        template_data = {
            'invoice': invoice.to_dict(include_line_items=True),
            'customer': invoice.customer.to_dict(),
            'qr_code': qr_code_data,
            'payment_url': f"{base_url}/pay/{invoice.uuid}",
            'logo_path': invoice_service._get_logo_path(),
            'generated_date': invoice_service.datetime.now().strftime('%B %d, %Y'),
            'base_url': base_url
        }
        
        # Generate HTML
        html_content = invoice_service._render_invoice_template(template_data)
        
        # Add CSS inline for preview
        css_content = invoice_service._get_invoice_css()
        html_with_css = f"""
        <html>
        <head>
            <style>{css_content}</style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """
        
        return html_with_css, 200, {'Content-Type': 'text/html'}
        
    except Exception as e:
        current_app.logger.error(f"Error previewing invoice {invoice_id}: {str(e)}")
        return jsonify({'error': 'Failed to preview invoice', 'details': str(e)}), 500

@invoice_pdf_bp.route('/<int:invoice_id>/payment-link', methods=['GET'])
@token_required
def get_payment_link(current_user, invoice_id):
    """Get payment link for invoice"""
    try:
        invoice = Invoice.query.get(invoice_id)
        
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404
        
        base_url = request.args.get('base_url', request.host_url.rstrip('/'))
        
        payment_link = invoice_service.create_payment_link(invoice, base_url)
        qr_code_data = invoice_service._generate_qr_code(invoice, base_url)
        
        return jsonify({
            'payment_link': payment_link,
            'qr_code': qr_code_data,
            'invoice_number': invoice.invoice_number,
            'amount': float(invoice.total_amount),
            'currency': invoice.currency,
            'due_date': invoice.due_date.isoformat() if invoice.due_date else None
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting payment link for invoice {invoice_id}: {str(e)}")
        return jsonify({'error': 'Failed to get payment link', 'details': str(e)}), 500

@invoice_pdf_bp.route('/bulk-email', methods=['POST'])
@token_required
def send_bulk_invoice_emails(current_user):
    """Send multiple invoices via email"""
    try:
        data = request.get_json()
        
        if not data or not data.get('invoice_ids'):
            return jsonify({'error': 'Invoice IDs are required'}), 400
        
        invoice_ids = data['invoice_ids']
        include_pdf = data.get('include_pdf', True)
        base_url = data.get('base_url', request.host_url.rstrip('/'))
        
        results = []
        successful = 0
        failed = 0
        
        for invoice_id in invoice_ids:
            try:
                invoice = Invoice.query.get(invoice_id)
                
                if not invoice:
                    results.append({
                        'invoice_id': invoice_id,
                        'status': 'error',
                        'message': 'Invoice not found'
                    })
                    failed += 1
                    continue
                
                # Send email
                success = invoice_service.send_invoice_email(
                    invoice=invoice,
                    recipient_email=invoice.customer.primary_email,
                    include_pdf=include_pdf,
                    base_url=base_url
                )
                
                if success:
                    # Update invoice status to sent if it was draft
                    if invoice.status.value == 'draft':
                        from src.models.invoice import InvoiceStatus
                        invoice.update_status(InvoiceStatus.SENT, current_user.id, "Invoice sent via bulk email")
                    
                    results.append({
                        'invoice_id': invoice_id,
                        'invoice_number': invoice.invoice_number,
                        'status': 'success',
                        'recipient': invoice.customer.primary_email
                    })
                    successful += 1
                else:
                    results.append({
                        'invoice_id': invoice_id,
                        'status': 'error',
                        'message': 'Failed to send email'
                    })
                    failed += 1
                    
            except Exception as e:
                results.append({
                    'invoice_id': invoice_id,
                    'status': 'error',
                    'message': str(e)
                })
                failed += 1
        
        db.session.commit()
        
        return jsonify({
            'message': f'Bulk email completed: {successful} successful, {failed} failed',
            'summary': {
                'total': len(invoice_ids),
                'successful': successful,
                'failed': failed
            },
            'results': results
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in bulk email: {str(e)}")
        return jsonify({'error': 'Bulk email failed', 'details': str(e)}), 500

