"""
ImageKit client initialization using environment settings
This keeps keys out of code and reads from environment variables as configured in `config/settings/base.py`.
"""
from django.conf import settings

try:
    from imagekitio import ImageKit
except Exception:
    ImageKit = None


def get_imagekit_client():
    """Return a configured ImageKit client or None if the SDK isn't installed.

    This is a thin factory to avoid failing import-time when the package
    is not installed (e.g., tests or environments without the SDK).
    """
    if ImageKit is None:
        return None

    return ImageKit(
        private_key=getattr(settings, "IMAGEKIT_PRIVATE_KEY", ""),
        public_key=getattr(settings, "IMAGEKIT_PUBLIC_KEY", ""),
        url_endpoint=getattr(settings, "IMAGEKIT_URL_ENDPOINT", ""),
    )


# Module-level client for convenience
imagekit = get_imagekit_client()
