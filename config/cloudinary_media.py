"""
Cloudinary uploads for every image the store shows (products, categories, banners, merch tiles).

Credentials come from the CLOUDINARY_URL setting (cloudinary://<api_key>:<api_secret>@<cloud_name>,
copied from the Cloudinary console's API Keys page). When it is empty, uploads are skipped and
files stay in the local media folder, which is fine for local development.
"""
import logging
import os
from urllib.parse import urlparse

from django.conf import settings

logger = logging.getLogger(__name__)

try:
    import cloudinary
    import cloudinary.uploader
except Exception:  # SDK missing (e.g. a trimmed test environment)
    cloudinary = None

_configured = False

UPLOAD_MARKER = "/image/upload/"


def _configure():
    """Applies CLOUDINARY_URL once; returns True when uploads can run."""
    global _configured
    if _configured:
        return True
    url = getattr(settings, "CLOUDINARY_URL", "") or ""
    if cloudinary is None or not url.startswith("cloudinary://"):
        return False
    parsed = urlparse(url)
    if not (parsed.hostname and parsed.username and parsed.password):
        logger.error("CLOUDINARY_URL is malformed; expected cloudinary://key:secret@cloud_name")
        return False
    cloudinary.config(
        cloud_name=parsed.hostname,
        api_key=parsed.username,
        api_secret=parsed.password,
        secure=True,
    )
    _configured = True
    return True


def cloudinary_enabled():
    return _configure()


def upload_image(file_field, folder):
    """
    Uploads a saved Django file field to Cloudinary under tamaade/<folder>.
    Returns (secure_url, public_id), or (None, None) when Cloudinary is off or the upload fails.
    """
    if not _configure():
        return None, None
    try:
        file_field.open("rb")
        result = cloudinary.uploader.upload(
            file_field,
            folder=f"tamaade/{folder.strip('/')}",
            resource_type="image",
            use_filename=True,
            unique_filename=True,
            overwrite=False,
        )
        return result.get("secure_url"), result.get("public_id")
    except Exception:
        logger.exception("Cloudinary upload failed for %s", getattr(file_field, "name", "?"))
        return None, None
    finally:
        try:
            file_field.close()
        except Exception:
            pass


def remove_local_media(name):
    """Deletes the local copy once the file is on Cloudinary (the server's media folder isn't kept)."""
    if not name:
        return
    try:
        path = os.path.join(settings.MEDIA_ROOT, name)
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def resized_url(url, width=None, height=None, quality=None, crop="limit"):
    """
    Same Cloudinary image at a smaller size (WebP/AVIF picked by the browser, auto quality).
    Other URLs, and URLs that already carry a transformation, come back unchanged.
    """
    if not url or "res.cloudinary.com" not in url or UPLOAD_MARKER not in url:
        return url
    head, rest = url.split(UPLOAD_MARKER, 1)
    first = rest.split("/", 1)[0]
    if "," in first or (len(first) > 2 and first[1] == "_"):
        return url
    parts = ["f_auto", f"q_{quality}" if quality else "q_auto"]
    if width or height:
        parts.append(f"c_{'fill' if (width and height) else crop}")
    if width:
        parts.append(f"w_{int(width)}")
    if height:
        parts.append(f"h_{int(height)}")
    return f"{head}{UPLOAD_MARKER}{','.join(parts)}/{rest}"
