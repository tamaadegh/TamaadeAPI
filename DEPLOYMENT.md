# Django E-commerce API Deployment Guide

## Railway Deployment (Recommended)

Railway is the best option for this Django app because it supports:
- PostgreSQL database
- Redis for caching and Celery
- Background worker processes
- Easy environment variable management

### Step 1: Prepare Your Repository

1. Push your code to GitHub (if not already done)
2. Make sure all the new files are committed:
   - `railway.json`
   - `Procfile` 
   - `.env.production`
   - Updated `requirements.txt`
   - Updated production settings

### Step 2: Deploy to Railway

1. Go to [railway.app](https://railway.app) and sign up/login
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your repository
4. Railway will automatically detect it's a Django app

### Step 3: Add Services

Your app needs these services:

#### PostgreSQL Database
1. In your Railway project, click "New Service"
2. Select "Database" → "PostgreSQL"
3. Railway will automatically set the `DATABASE_URL` environment variable

#### Redis
1. Click "New Service" → "Database" → "Redis"
2. Railway will automatically set the `REDIS_URL` environment variable

### Step 4: Configure Environment Variables

In your Railway project settings, add these environment variables:

```bash
# Required - Generate a strong secret key
SECRET_KEY=your-super-secret-django-key

# Django Settings
DEBUG=False
DJANGO_SETTINGS_MODULE=config.settings.production

# Email (Gmail example)
EMAIL_USER=your-email@gmail.com
EMAIL_PASSWORD=your-gmail-app-password

# Twilio (for SMS verification)
TWILIO_ACCOUNT_SID=your-twilio-sid
TWILIO_AUTH_TOKEN=your-twilio-token
TWILIO_PHONE_NUMBER=+1234567890

# Stripe (use live keys for production)
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Domains (update after deployment)
BACKEND_DOMAIN=https://your-app.railway.app
FRONTEND_DOMAIN=https://your-frontend.com
PAYMENT_SUCCESS_URL=https://your-frontend.com/success
PAYMENT_CANCEL_URL=https://your-frontend.com/cancel
```

### Step 5: Deploy Worker Process

1. In Railway, add another service for Celery worker
2. Use the same GitHub repo
3. Set the start command to: `celery -A config worker --loglevel=info`
4. Add the same environment variables

### Step 6: Final Steps

1. Your app will be available at `https://your-app-name.railway.app`
2. Create a superuser: Use Railway's terminal to run:
   ```bash
   python manage.py createsuperuser
   ```
3. Test your API endpoints
4. Update your frontend to use the new backend URL

## Alternative Options

### Render.com
- Similar to Railway
- Good PostgreSQL and Redis support
- Slightly more complex setup

### DigitalOcean App Platform
- Cost-effective
- Managed databases available
- Good for production workloads

### Heroku
- Classic choice but more expensive
- Requires add-ons for PostgreSQL and Redis

## Important Notes

1. **Database Migrations**: Railway runs migrations automatically via the entrypoint script
2. **Static Files**: Configured with WhiteNoise for efficient serving
3. **Security**: Production settings include proper security headers
4. **Monitoring**: Check Railway logs for any deployment issues
5. **Scaling**: Railway can auto-scale based on traffic

## Troubleshooting

- **Build Fails**: Check the build logs in Railway dashboard
- **Database Connection**: Ensure DATABASE_URL is set correctly
- **Static Files**: Make sure `python manage.py collectstatic` runs successfully
- **Worker Process**: Verify Celery worker is running in a separate service

## Cost Estimation

Railway pricing (as of 2024):
- Hobby Plan: $5/month per service
- Typical setup: Web app ($5) + PostgreSQL ($5) + Redis ($5) + Worker ($5) = ~$20/month

This is much more cost-effective than managing separate VPS instances and includes managed databases.
