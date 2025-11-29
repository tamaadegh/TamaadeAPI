from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.urls import reverse
import os

User = get_user_model()


def category_image_path(instance, filename):
    return f"product/category/icons/{instance.name}/{filename}"


def product_image_path(instance, filename):
    return f"product/images/{instance.name}/{filename}"


def product_video_path(instance, filename):
    return f"product/videos/{instance.name}/{filename}"

class ProductCategory(models.Model):
    name = models.CharField(_("Category name"), max_length=100)
    icon = models.ImageField(upload_to=category_image_path, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Product Category")
        verbose_name_plural = _("Product Categories")

    def __str__(self):
        return self.name


def get_default_product_category():
    return ProductCategory.objects.get_or_create(name="Others")[0]


class Product(models.Model):
    seller = models.ForeignKey(User, related_name="products", on_delete=models.CASCADE)
    category = models.ForeignKey(
        ProductCategory,
        related_name="product_list",
        on_delete=models.SET(get_default_product_category),
    )
    name = models.CharField(max_length=200)
    desc = models.TextField(_("Description"), blank=True)
    # Deprecated single fields, kept for backwards compatibility. Prefer using
    # ProductImage / ProductVideo models for multiple assets.
    image = models.ImageField(upload_to=product_image_path, blank=True, null=True)
    video = models.FileField(upload_to=product_video_path, blank=True, null=True)
    price = models.DecimalField(decimal_places=2, max_digits=10)
    quantity = models.IntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.name


class ProductImage(models.Model):
    """Images for products. Uses a local temporary file field for uploads (`file_local`),
    then uploads the file to ImageKit in `save` and stores the final URL and fileId.
    """
    product = models.ForeignKey(Product, related_name="images", on_delete=models.CASCADE)
    file_local = models.ImageField(upload_to=product_image_path, blank=True, null=True)
    url = models.URLField(max_length=600, blank=True, null=True)
    file_id = models.CharField(max_length=200, blank=True, null=True)
    is_primary = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "-created_at"]

    def __str__(self):
        return f"{self.product.name} - image {self.pk or ''}"

    def save(self, *args, **kwargs):
        """If `file_local` is present, upload it to ImageKit and store URL/file_id.
        Deletes the local file afterwards to avoid storing files locally in production.
        """
        # Async upload via Celery if enabled
        has_local = bool(self.file_local and getattr(self.file_local, "name", None))
        try:
            from django.conf import settings as _settings
            async_upload = getattr(_settings, "IMAGEKIT_UPLOAD_ASYNC", True)
        except Exception:
            async_upload = True

        if has_local and async_upload:
            # Schedule Celery task instead of uploading immediately
            try:
                from products.tasks import upload_product_image_to_imagekit
                # Save first to ensure file is on disk and we have pk
                super().save(*args, **kwargs)
                upload_product_image_to_imagekit.delay(self.pk)
                return
            except Exception:
                # Fall through and do synchronous behavior on failure
                pass

        # If async disabled or scheduling failed, perform upload synchronously
        try:
            from config.imagekit import imagekit
        except Exception:
            imagekit = None
        if has_local and imagekit:
            try:
                file_obj = self.file_local
                file_obj.open()
                filename = os.path.basename(file_obj.name)
                folder = f"/products/{self.product.id}/images" if self.product_id else "/products/images"
                result = imagekit.upload_file(file=file_obj, file_name=filename, options={"folder": folder})
                raw = getattr(result, "response_metadata", None)
                raw = getattr(raw, "raw", {}) if raw else {}
                self.url = raw.get("url") or raw.get("filePath")
                self.file_id = raw.get("fileId")
                try:
                    file_path = os.path.join(settings.MEDIA_ROOT, file_obj.name)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception:
                    pass
            except Exception:
                pass

        super().save(*args, **kwargs)

    def get_transformed_url(self, width=None, height=None, quality=None):
        try:
            from config.imagekit import imagekit
        except Exception:
            imagekit = None

        if not self.url:
            return None
        if not imagekit:
            return self.url

        transformation = []
        if height:
            transformation.append({"height": str(height)})
        if width:
            transformation.append({"width": str(width)})
        if quality:
            transformation.append({"quality": str(quality)})

        if transformation:
            return imagekit.url({"src": self.url, "transformation": transformation})
        return self.url


class ProductVideo(models.Model):
    """Videos for products. Similar behavior to `ProductImage`.
    """
    product = models.ForeignKey(Product, related_name="videos", on_delete=models.CASCADE)
    file_local = models.FileField(upload_to=product_video_path, blank=True, null=True)
    url = models.URLField(max_length=600, blank=True, null=True)
    file_id = models.CharField(max_length=200, blank=True, null=True)
    is_primary = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "-created_at"]

    def __str__(self):
        return f"{self.product.name} - video {self.pk or ''}"

    def save(self, *args, **kwargs):
        try:
            from django.conf import settings as _settings
            async_upload = getattr(_settings, "IMAGEKIT_UPLOAD_ASYNC", True)
        except Exception:
            async_upload = True
        has_local = bool(self.file_local and getattr(self.file_local, "name", None))
        if has_local and async_upload:
            try:
                from products.tasks import upload_product_video_to_imagekit
                super().save(*args, **kwargs)
                upload_product_video_to_imagekit.delay(self.pk)
                return
            except Exception:
                pass
        try:
            from config.imagekit import imagekit
        except Exception:
            imagekit = None
        if has_local and imagekit:
            try:
                file_obj = self.file_local
                file_obj.open()
                filename = os.path.basename(file_obj.name)
                folder = f"/products/{self.product.id}/videos" if self.product_id else "/products/videos"
                result = imagekit.upload_file(file=file_obj, file_name=filename, options={"folder": folder})
                raw = getattr(result, "response_metadata", None)
                raw = getattr(raw, "raw", {}) if raw else {}
                self.url = raw.get("url") or raw.get("filePath")
                self.file_id = raw.get("fileId")
                try:
                    file_path = os.path.join(settings.MEDIA_ROOT, file_obj.name)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception:
                    pass
            except Exception:
                pass

        super().save(*args, **kwargs)

    def get_transformed_url(self, width=None, height=None, quality=None):
        try:
            from config.imagekit import imagekit
        except Exception:
            imagekit = None

        if not self.url:
            return None
        if not imagekit:
            return self.url

        transformation = []
        if height:
            transformation.append({"height": str(height)})
        if width:
            transformation.append({"width": str(width)})
        if quality:
            transformation.append({"quality": str(quality)})

        if transformation:
            return imagekit.url({"src": self.url, "transformation": transformation})
        return self.url

