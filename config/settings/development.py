import os
import dj_database_url
from .base import *

# Use DATABASE_URL for external database connection
DATABASES = {
    'default': dj_database_url.parse(
        config('DATABASE_URL', default='postgresql://localhost/tamaade')
    )
}

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "../", "mediafiles")

STATIC_URL = "static/"
STATIC_ROOT = os.path.join(BASE_DIR, "../", "staticfiles")
