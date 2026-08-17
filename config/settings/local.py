from .base import *

DEBUG = True
SECRET_KEY = config("SECRET_KEY", default="django-insecure-local-dev-key")
ALLOWED_HOSTS = ["*"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR.parent / "db.sqlite3",
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

CORS_ORIGIN_ALLOW_ALL = True
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "dj_rest_auth.jwt_auth.JWTCookieAuthentication",
    ),
}
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
ACCOUNT_EMAIL_VERIFICATION = "optional"
IMAGEKIT_UPLOAD_ASYNC = False
STATICFILES_DIRS = []

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR.parent / "mediafiles"
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR.parent / "staticfiles"
