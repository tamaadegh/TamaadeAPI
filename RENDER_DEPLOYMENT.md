# Django E-commerce API - Render Deployment Guide

## Why Render?

Render is perfect for your Django e-commerce API because it provides:
- ✅ **Managed PostgreSQL** database
- ✅ **Redis** for caching and Celery
- ✅ **Background workers** for payment processing
- ✅ **Auto-scaling** and SSL certificates
- ✅ **Simple deployment** from GitHub
- ✅ **Competitive pricing** (~$15-20/month)

## Quick Start

### 1. Push to GitHub
```bash
git add .
git commit -m "Add Render deployment config"
git push origin main
```

### 2. Deploy on Render

1. Go to [render.com](https://render.com) and sign up
2. Click **"New"** → **"Blueprint"**
3. Connect your GitHub repository: `https://github.com/BraKoose/TamaadeAPI`
4. Render will automatically detect the `render.yaml` file

### 3. Configure Environment Variables

Add these in your Render service settings:

#### Required Variables:
```bash
SECRET_KEY=your-super-secret-django-key-here
DEBUG=False
DJANGO_SETTINGS_MODULE=config.settings.production

# Email (for user verification)
EMAIL_USER=your-email@gmail.com
EMAIL_PASSWORD=your-gmail-app-password

# Twilio (for SMS verification)
TWILIO_ACCOUNT_SID=your-twilio-sid
TWILIO_AUTH_TOKEN=your-twilio-token
TWILIO_PHONE_NUMBER=+1234567890

# Stripe (use test keys first, then live keys)
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Domains (update after deployment)
BACKEND_DOMAIN=https://tamaade-api.onrender.com
FRONTEND_DOMAIN=https://your-frontend.com
PAYMENT_SUCCESS_URL=https://your-frontend.com/success
PAYMENT_CANCEL_URL=https://your-frontend.com/cancel
```

## What Gets Deployed

Your `render.yaml` creates:

1. **PostgreSQL Database** (`tamaade-db`)
2. **Redis Instance** (`tamaade-redis`) 
3. **Web Service** (`tamaade-api`) - Your Django API
4. **Worker Service** (`tamaade-worker`) - Celery for background tasks

## Post-Deployment Steps

### 1. Create Superuser
In Render dashboard → Services → tamaade-api → Shell:
```bash
python manage.py createsuperuser
```

### 2. Test Your API
- API Base: `https://your-app.onrender.com`
- Admin Panel: `https://your-app.onrender.com/admin/`
- API Docs: `https://your-app.onrender.com/api/schema/swagger-ui/`

### 3. Configure Stripe Webhooks
1. In Stripe Dashboard → Webhooks
2. Add endpoint: `https://your-app.onrender.com/api/payment/webhook/`
3. Select events: `payment_intent.succeeded`, `payment_intent.payment_failed`
4. Copy webhook secret to `STRIPE_WEBHOOK_SECRET`

## File Structure Created

```
├── render.yaml          # Render services configuration
├── build.sh            # Build script for deployment
├── .env.render         # Environment variables template
├── config/settings/
│   └── production.py   # Production Django settings
└── requirements.txt    # Updated with deployment dependencies
```

## Cost Breakdown (Monthly)

- **Web Service**: $7/month (Starter plan)
- **PostgreSQL**: $7/month (Starter plan)  
- **Redis**: $7/month (Starter plan)
- **Worker Service**: $7/month (Starter plan)
- **Total**: ~$28/month

*Note: Render offers free tiers for testing, but production apps need paid plans for reliability*

## Troubleshooting

### Build Fails
- Check build logs in Render dashboard
- Ensure all dependencies in `requirements.txt`
- Verify `build.sh` has execute permissions

### Database Connection Issues
- Ensure `DATABASE_URL` is automatically set by Render
- Check PostgreSQL service is running

### Static Files Not Loading
- Verify WhiteNoise is in middleware
- Check `python manage.py collectstatic` runs in build

### Celery Worker Issues
- Ensure Redis service is running
- Check worker logs in Render dashboard
- Verify `CELERY_BROKER_URL` points to Redis

## Security Notes

1. **Never commit secrets** to Git
2. **Use environment variables** for all sensitive data
3. **Enable 2FA** on your Render account
4. **Use strong SECRET_KEY** (generate with Django)
5. **Configure CORS** properly for your frontend domain

## Scaling

Render auto-scales based on traffic, but you can:
- Upgrade service plans for more resources
- Add multiple worker instances for heavy background processing
- Use Render's CDN for static files

## Monitoring

Render provides:
- Real-time logs
- Metrics dashboard
- Uptime monitoring
- Email alerts for downtime

Your Django e-commerce API will be production-ready with this setup!
