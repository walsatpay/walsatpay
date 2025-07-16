# WasatPay DigitalOcean Deployment Guide

## 🎯 Overview
This guide walks you through deploying WasatPay to DigitalOcean App Platform for production use by Wasat Humanitarian Foundation.

## 📋 Prerequisites

### 1. DigitalOcean Account
- Create a DigitalOcean account at https://digitalocean.com
- Add a payment method
- Consider using a referral link for $200 credit

### 2. GitHub Repository
- Create a GitHub repository for the WasatPay code
- Push all code to the repository
- Ensure the repository is public or grant DigitalOcean access

### 3. Domain Name (Optional but Recommended)
- Purchase a domain name (e.g., wasatpay.com)
- Configure DNS to point to DigitalOcean

## 🚀 Deployment Steps

### Step 1: Prepare the Application

1. **Run the deployment script:**
   ```bash
   cd wasatpay-backend
   python deploy.py
   ```

2. **Commit and push to GitHub:**
   ```bash
   git init
   git add .
   git commit -m "Initial WasatPay deployment"
   git remote add origin https://github.com/YOUR_USERNAME/wasatpay-backend.git
   git push -u origin main
   ```

### Step 2: Create DigitalOcean App

1. **Log in to DigitalOcean**
   - Go to https://cloud.digitalocean.com
   - Navigate to "Apps" in the sidebar

2. **Create New App**
   - Click "Create App"
   - Choose "GitHub" as source
   - Select your wasatpay-backend repository
   - Choose the "main" branch

3. **Configure App Settings**
   - App name: `wasatpay-backend`
   - Region: Choose closest to Kenya (e.g., Frankfurt or London)
   - Plan: Start with Basic ($12/month)

### Step 3: Configure Environment Variables

In the DigitalOcean App Platform, add these environment variables:

#### Required Variables:
```
FLASK_ENV=production
SECRET_KEY=your-super-secret-key-here-change-this
DATABASE_URL=${db.DATABASE_URL}
```

#### Email Configuration (SendGrid):
```
MAIL_SERVER=smtp.sendgrid.net
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=apikey
MAIL_PASSWORD=your-sendgrid-api-key
MAIL_DEFAULT_SENDER=noreply@wasatpay.com
```

#### Payment Provider Configuration:
```
STRIPE_PUBLISHABLE_KEY=pk_live_your_stripe_publishable_key
STRIPE_SECRET_KEY=sk_live_your_stripe_secret_key
FLUTTERWAVE_PUBLIC_KEY=FLWPUBK_your_flutterwave_public_key
FLUTTERWAVE_SECRET_KEY=FLWSECK_your_flutterwave_secret_key
```

#### CORS Configuration:
```
CORS_ORIGINS=https://wasatpay.com,https://www.wasatpay.com
```

### Step 4: Configure Database

1. **Add PostgreSQL Database**
   - In the app configuration, add a database component
   - Choose PostgreSQL 14
   - Plan: Basic ($15/month)
   - The DATABASE_URL will be automatically configured

### Step 5: Configure Domain (Optional)

1. **Add Custom Domain**
   - In app settings, go to "Domains"
   - Add your domain (e.g., wasatpay.com)
   - Configure DNS records as instructed

2. **SSL Certificate**
   - DigitalOcean automatically provides SSL certificates
   - Ensure "Force HTTPS" is enabled

### Step 6: Deploy and Test

1. **Deploy the App**
   - Click "Create Resources"
   - Wait for deployment to complete (5-10 minutes)

2. **Test the Deployment**
   - Visit your app URL
   - Test the health endpoint: `https://your-app-url/api/health`
   - Verify database connection

## 🔧 Post-Deployment Configuration

### 1. Set Up Email Service (SendGrid)

1. **Create SendGrid Account**
   - Go to https://sendgrid.com
   - Create a free account (100 emails/day)

2. **Create API Key**
   - Go to Settings > API Keys
   - Create a new API key with "Full Access"
   - Add the key to your environment variables

3. **Verify Sender Identity**
   - Go to Settings > Sender Authentication
   - Verify your email domain or single sender

### 2. Set Up Payment Providers

#### Stripe Setup:
1. Create account at https://stripe.com
2. Get API keys from Dashboard > Developers > API keys
3. Configure webhooks for payment events

#### Flutterwave Setup:
1. Create account at https://flutterwave.com
2. Get API keys from Settings > API
3. Configure webhooks for payment events

### 3. Create Initial Admin User

Use the API to create the first admin user:

```bash
curl -X POST https://your-app-url/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@wasatfoundation.org",
    "password": "secure-password",
    "first_name": "Admin",
    "last_name": "User",
    "role": "admin"
  }'
```

## 📊 Monitoring and Maintenance

### 1. Application Monitoring
- Use DigitalOcean's built-in monitoring
- Monitor CPU, memory, and response times
- Set up alerts for downtime

### 2. Database Backups
- DigitalOcean automatically backs up managed databases
- Consider additional backup strategies for critical data

### 3. Log Monitoring
- Access logs through DigitalOcean dashboard
- Monitor for errors and performance issues

## 💰 Cost Breakdown

### Monthly Costs:
- **App Platform (Basic)**: $12/month
- **PostgreSQL Database**: $15/month
- **Domain Name**: $10-15/year
- **SendGrid (Free tier)**: $0 (up to 100 emails/day)
- **Total**: ~$27/month + domain

### Payment Processing Fees:
- **Stripe**: 2.9% + $0.30 per transaction
- **Flutterwave**: 1.4% per transaction

## 🔒 Security Considerations

1. **Environment Variables**
   - Never commit secrets to Git
   - Use DigitalOcean's encrypted environment variables

2. **Database Security**
   - Use managed PostgreSQL with automatic security updates
   - Enable connection pooling

3. **SSL/TLS**
   - Force HTTPS for all connections
   - Use strong SSL certificates

4. **API Security**
   - Implement rate limiting
   - Use JWT tokens with short expiration
   - Validate all inputs

## 🆘 Troubleshooting

### Common Issues:

1. **Database Connection Errors**
   - Check DATABASE_URL environment variable
   - Verify database is running and accessible

2. **Email Not Sending**
   - Verify SendGrid API key
   - Check sender authentication
   - Review email logs

3. **Payment Processing Issues**
   - Verify API keys for payment providers
   - Check webhook configurations
   - Review payment provider logs

### Getting Help:
- DigitalOcean Documentation: https://docs.digitalocean.com
- DigitalOcean Support: Available 24/7
- WasatPay Issues: Contact development team

## 🎉 Success!

Once deployed, your WasatPay system will be available at:
- **API**: https://your-app-url/api
- **Health Check**: https://your-app-url/api/health
- **Payment Pages**: https://your-app-url/api/public/pay/{invoice-uuid}

The system is now ready for Wasat Humanitarian Foundation to:
- Create and send professional invoices
- Accept payments from donors worldwide
- Manage projects and track funding
- Generate reports and analytics

## 📞 Next Steps

1. **Train Foundation Staff**
   - Provide training on using the system
   - Create user documentation
   - Set up support processes

2. **Integrate with Existing Workflows**
   - Connect with accounting systems
   - Set up automated reporting
   - Configure donor communication

3. **Scale as Needed**
   - Monitor usage and performance
   - Upgrade plans as foundation grows
   - Add additional features as required

