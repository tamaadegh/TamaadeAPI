import os
import dj_database_url
from .base import *

# Security settings for production
DEBUG = False
# Use ALLOWED_HOSTS from environment variable for security
# Fallback to ['*'] only if not set (not recommended for production)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='*', cast=Csv())

# Database configuration for Render
DATABASES = {
    'default': dj_database_url.parse(
        config('DATABASE_URL'), conn_max_age=600, ssl_require=False
    )
}

# Static files configuration
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files configuration
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'mediafiles')

# Security settings
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'

# CORS settings for production - Allow all origins
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

# JWT Cookie settings for production
JWT_AUTH_SECURE = True
JWT_AUTH_HTTPONLY = True
JWT_AUTH_SAMESITE = 'None'  # Required for mobile/cross-origin requests

# Session and CSRF cookie settings for production
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = 'None'
SESSION_COOKIE_HTTPONLY = True

# Critical fix for admin login issues
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = 'None'
CSRF_COOKIE_HTTPONLY = False  # Must be False for JavaScript access
CSRF_USE_SESSIONS = True  # Store CSRF token in session instead of cookie
CSRF_COOKIE_DOMAIN = None  # Allow subdomains to access CSRF token

# Trusted origins (fallback to Render domain if not set via env)
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='https://tamaadeapi-7it5.onrender.com', cast=Csv())

# Cache configuration for production - use local memory cache
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
