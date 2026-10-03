from datetime import timedelta
from pathlib import Path

from decouple import Csv, config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config("SECRET_KEY", default="django-insecure-default-key-change-in-production")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config("DEBUG", default=False, cast=bool)

ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="", cast=Csv())


# Application definition

INSTALLED_APPS = [
    "jazzmin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party apps
    "django.contrib.sites",
    "rest_framework",
    "rest_framework.authtoken",
    "dj_rest_auth",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "dj_rest_auth.registration",
    "phonenumber_field",
    "corsheaders",
    "drf_spectacular",
    # Local apps
    "users",
    "products",
    "orders",
    "payment",
    "dashboard",
    "sitecontent",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    # Removed cache middleware to allow real-time dashboard updates
    # "django.middleware.cache.UpdateCacheMiddleware",
    "django.middleware.common.CommonMiddleware",
    # "django.middleware.cache.FetchFromCacheMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "config.middleware.CSRFFixMiddleware",  # Custom middleware to fix CSRF issues
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR.parent / "templates"],  # Add custom templates directory
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database
# https://docs.djangoproject.com/en/4.0/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME", default="tamaade"),
        "USER": config("DB_USERNAME", default="tamaade_user"),
        "PASSWORD": config("DB_PASSWORD", default="password"),
        "HOST": config("DB_HOSTNAME", default="localhost"),
        "PORT": config("DB_PORT", default=5432, cast=int),
    }
}


# Password validation
# https://docs.djangoproject.com/en/4.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",  # noqa
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.0/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Default primary key field type
# https://docs.djangoproject.com/en/4.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ORIGIN_ALLOW_ALL = True

# Authentication
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "users.backends.phone_backend.PhoneNumberAuthBackend",
    "users.backends.email_backend.EmailAuthBackend",
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "dj_rest_auth.jwt_auth.JWTCookieAuthentication",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SITE_ID = 1

REST_USE_JWT = True

JWT_AUTH_COOKIE = "phonenumber-auth"
JWT_AUTH_REFRESH_COOKIE = "phonenumber-refresh-token"

# Storefront sessions: simplejwt defaults to 5-minute access tokens (and matching
# cookie expiry). AuthContext treats a 401 as logout and does not refresh.
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=12),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
}

# ACCOUNT_EMAIL_VERIFICATION SETTINGS
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_USERNAME_REQUIRED = False
# E-mail + password sign-in is a plain credentials check: no confirmation mail.
ACCOUNT_EMAIL_VERIFICATION = "none"


# Email
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_TIMEOUT = 10  # seconds; a slow SMTP server must not hang sign-up
EMAIL_HOST = "smtp.gmail.com"
EMAIL_USE_TLS = True
EMAIL_PORT = 587
EMAIL_HOST_USER = config("EMAIL_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_PASSWORD", default="")

# Phone number field
PHONENUMBER_DEFAULT_REGION = "GH"

# Phone OTP sign-in (users/otp.py). Every code is a paid Hubtel SMS.
# "disabled" | "log" (DEBUG only: code is logged, never sent) | "hubtel"
OTP_SMS_PROVIDER = config("OTP_SMS_PROVIDER", default="disabled")
HUBTEL_SMS_CLIENT_ID = config("HUBTEL_SMS_CLIENT_ID", default="")
HUBTEL_SMS_CLIENT_SECRET = config("HUBTEL_SMS_CLIENT_SECRET", default="")
# Must be a sender ID approved by Hubtel, or messages are rejected.
HUBTEL_SMS_SENDER_ID = config("HUBTEL_SMS_SENDER_ID", default="Tamaade")
OTP_EXPIRE_MINUTES = config("OTP_EXPIRE_MINUTES", default=10, cast=int)
OTP_MAX_ATTEMPTS = config("OTP_MAX_ATTEMPTS", default=5, cast=int)
OTP_RATE_LIMIT_ENABLED = config("OTP_RATE_LIMIT_ENABLED", default=True, cast=bool)
OTP_RESEND_COOLDOWN_SECONDS = config("OTP_RESEND_COOLDOWN_SECONDS", default=60, cast=int)
OTP_PHONE_SHORT_MAX = config("OTP_PHONE_SHORT_MAX", default=3, cast=int)  # per 15 min
OTP_PHONE_DAILY_MAX = config("OTP_PHONE_DAILY_MAX", default=10, cast=int)
# Ghana carriers put many users behind one CGNAT address: raise if real users hit these.
OTP_IP_HOURLY_MAX = config("OTP_IP_HOURLY_MAX", default=10, cast=int)
OTP_IP_DAILY_MAX = config("OTP_IP_DAILY_MAX", default=30, cast=int)
OTP_GLOBAL_HOURLY_MAX = config("OTP_GLOBAL_HOURLY_MAX", default=600, cast=int)
OTP_GLOBAL_DAILY_MAX = config("OTP_GLOBAL_DAILY_MAX", default=6000, cast=int)
OTP_VERIFY_FAIL_MAX = config("OTP_VERIFY_FAIL_MAX", default=10, cast=int)
OTP_VERIFY_LOCKOUT_SECONDS = config("OTP_VERIFY_LOCKOUT_SECONDS", default=3600, cast=int)
# Google Play review access: ONE number that accepts a fixed code for login.
# Unset both to revoke.
OTP_REVIEW_PHONE = config("OTP_REVIEW_PHONE", default="")
OTP_REVIEW_CODE = config("OTP_REVIEW_CODE", default="")

# Stripe
STRIPE_PUBLISHABLE_KEY = config("STRIPE_PUBLISHABLE_KEY", default="")
STRIPE_SECRET_KEY = config("STRIPE_SECRET_KEY", default="")
STRIPE_WEBHOOK_SECRET = config("STRIPE_WEBHOOK_SECRET", default="")

BACKEND_DOMAIN = config("BACKEND_DOMAIN", default="http://localhost:8000")
FRONTEND_DOMAIN = config("FRONTEND_DOMAIN", default="http://localhost:3000")

PAYMENT_SUCCESS_URL = config("PAYMENT_SUCCESS_URL", default="http://localhost:3000/checkout/success")
PAYMENT_CANCEL_URL = config("PAYMENT_CANCEL_URL", default="http://localhost:3000/checkout/cancel")

# Hubtel Online Checkout (same provider as UrbanAfrica)
HUBTEL_API_ID = config("HUBTEL_API_ID", default="")
HUBTEL_API_KEY = config("HUBTEL_API_KEY", default="")
HUBTEL_COLLECTION_ACCOUNT_NUMBER = config("HUBTEL_COLLECTION_ACCOUNT_NUMBER", default="")
HUBTEL_CHECKOUT_BASE = config("HUBTEL_CHECKOUT_BASE", default="https://payproxyapi.hubtel.com")

# Celery
CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = config("REDIS_BACKEND", default="redis://localhost:6379/0")


# DRF Spectacular
SPECTACULAR_SETTINGS = {
    "TITLE": "Tamaade API",
    "DESCRIPTION": "An Ecommerce API built using Django Rest Framework",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# Redis Cache
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": config("REDIS_BACKEND", default="redis://localhost:6379/0"),
    },
}
CACHE_MIDDLEWARE_ALIAS = "default"
CACHE_MIDDLEWARE_SECONDS = 3600
CACHE_MIDDLEWARE_KEY_PREFIX = ""

# CSRF Trusted Origins (comma-separated URLs), e.g., http://localhost:8000,https://example.com
CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", default="", cast=Csv())

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.0/howto/static-files/
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR.parent / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR.parent / 'static',
]

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR.parent / 'mediafiles'

# ImageKit configuration - set these in your .env or environment variables
IMAGEKIT_PUBLIC_KEY = config("IMAGEKIT_PUBLIC_KEY", default="")
IMAGEKIT_PRIVATE_KEY = config("IMAGEKIT_PRIVATE_KEY", default="")
IMAGEKIT_URL_ENDPOINT = config("IMAGEKIT_URL_ENDPOINT", default="")
IMAGEKIT_UPLOAD_ASYNC = config("IMAGEKIT_UPLOAD_ASYNC", default=True, cast=bool)

# Jazzmin configuration for a modern, branded admin
JAZZMIN_SETTINGS = {
    "site_title": "Tamaade Admin Portal",
    "site_header": "Tamaade Admin",
    "site_brand": "Tamaade",
    "welcome_sign": "Welcome to Tamaade Admin",
    "show_ui_builder": False,
}

JAZZMIN_UI_TWEAKS = {
    "theme": "flatly",
    "navbar": "navbar-dark",
    "accent": "accent-green",
    "sidebar_fixed": True,
}
