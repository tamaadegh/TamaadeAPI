from celery import shared_task
from django.conf import settings
from django.core.files.storage import default_storage
import os

from products.models import ProductImage, ProductVideo

try:
    from config.imagekit import imagekit
except Exception:
    imagekit = None


@shared_task(bind=True)
def upload_product_image(self, image_id):
    """Pushes a product image to Cloudinary (see ProductImage.upload_to_cloudinary)."""
    try:
        img = ProductImage.objects.get(pk=image_id)
    except ProductImage.DoesNotExist:
        return None
    if img.url or not img.file_local:
        return img.url
    url = img.upload_to_cloudinary()
    if not url:
        raise self.retry(countdown=10, max_retries=3)
    return url


# Old name, kept so tasks already queued before the switch to Cloudinary still run.
upload_product_image_to_imagekit = upload_product_image


@shared_task(bind=True)
def upload_product_video_to_imagekit(self, video_id):
    try:
        vid = ProductVideo.objects.get(pk=video_id)
    except ProductVideo.DoesNotExist:
        return None

    if not vid.file_local:
        return None
    if vid.url:
        return None

    try:
        file_obj = vid.file_local
        file_obj.open()
        filename = os.path.basename(file_obj.name)
        folder = f"/products/{vid.product.id}/videos" if vid.product_id else "/products/videos"
        if imagekit:
            result = imagekit.upload_file(file=file_obj, file_name=filename, options={"folder": folder})
            raw = getattr(result, "response_metadata", None)
            raw = getattr(raw, "raw", {}) if raw else {}
            vid.url = raw.get("url") or raw.get("filePath")
            vid.file_id = raw.get("fileId")
            vid.save()
        try:
            file_path = os.path.join(settings.MEDIA_ROOT, file_obj.name)
            if default_storage.exists(file_obj.name) and os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass
        return vid.url
    except Exception as exc:
        raise self.retry(exc=exc, countdown=10, max_retries=3)
