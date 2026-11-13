from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.urls import reverse
import os

User = get_user_model()


def category_image_path(instance, filename):
    return f"product/category/icons/{instance.name}/{filename}"


def _product_folder(instance):
    # ProductImage / ProductVideo have no name of their own: use their product's id.
    product_id = getattr(instance, "product_id", None)
    if product_id:
        return str(product_id)
    return getattr(instance, "name", None) or "unassigned"  # Product's own image/video


def product_image_path(instance, filename):
    return f"product/images/{_product_folder(instance)}/{filename}"


def product_video_path(instance, filename):
    return f"product/videos/{_product_folder(instance)}/{filename}"

class ProductCategory(models.Model):
    name = models.CharField(_("Category name"), max_length=100)
    # Required when a category is created in the admin (see ProductCategoryAdmin); older
    # categories may still have none and show their first letter in the apps.
    icon = models.ImageField(upload_to=category_image_path, blank=True)
    # Where the icon lives once uploaded to Cloudinary; the local file is then removed,
    # because the server's media folder is not kept between deploys.
    icon_url = models.URLField(max_length=600, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Product Category")
        verbose_name_plural = _("Product Categories")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        _move_image_to_cloudinary(self, "icon", "icon_url", folder="categories")

    @property
    def resolved_icon(self):
        """Cloudinary URL, else the local file URL (dev without Cloudinary), else None."""
        if self.icon_url:
            return self.icon_url
        if self.icon:
            return self.icon.url
        return None


def _move_image_to_cloudinary(instance, file_attr, url_attr, folder):
    """
    After a save with a newly uploaded file in `file_attr`: push it to Cloudinary, store the
    URL in `url_attr`, clear the file field and delete the local copy. No-op without Cloudinary.
    """
    from config.cloudinary_media import remove_local_media, upload_image

    file_field = getattr(instance, file_attr)
    if not file_field or not getattr(file_field, "name", None):
        return
    url, _public_id = upload_image(file_field, folder=folder)
    if not url:
        return
    local_name = file_field.name
    setattr(instance, url_attr, url)
    setattr(instance, file_attr, "")  # "" = no file; works for non-null file fields too
    update = [file_attr, url_attr]
    if any(f.name == "updated_at" for f in instance._meta.fields):
        update.append("updated_at")
    type(instance).objects.filter(pk=instance.pk).update(**{f: getattr(instance, f) for f in update})
    remove_local_media(local_name)


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
    compare_at_price = models.DecimalField(
        decimal_places=2,
        max_digits=10,
        blank=True,
        null=True,
        help_text="Original price before discount. Leave empty if the product is not on promo.",
    )
    promo_label = models.CharField(
        max_length=120,
        blank=True,
        help_text='Shown on the product card, e.g. "UP TO 70% OFF".',
    )
    brand = models.CharField(max_length=120, blank=True)
    is_new = models.BooleanField(default=False)
    is_express = models.BooleanField(default=False)
    sale_ends_at = models.DateTimeField(blank=True, null=True)
    quantity = models.IntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.name

    @property
    def discount_percent(self):
        if not self.compare_at_price or self.compare_at_price <= 0:
            return None
        if self.price >= self.compare_at_price:
            return None
        return int(round((1 - (self.price / self.compare_at_price)) * 100))


class ProductImage(models.Model):
    """Images for products. Uploads arrive in `file_local`, are pushed to Cloudinary in `save`
    (or by a Celery task), and the final URL / public id are stored in `url` / `file_id`.
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
        """Saves, then uploads `file_local` to Cloudinary (async via Celery when enabled)."""
        has_local = bool(self.file_local and getattr(self.file_local, "name", None))
        super().save(*args, **kwargs)
        if not has_local or self.url:
            return

        if getattr(settings, "IMAGE_UPLOAD_ASYNC", False):
            try:
                from products.tasks import upload_product_image
                upload_product_image.delay(self.pk)
                return
            except Exception:
                pass  # broker unavailable: upload right away instead
        self.upload_to_cloudinary()

    def upload_to_cloudinary(self):
        """Pushes `file_local` to Cloudinary, stores url/file_id, removes the local file."""
        from config.cloudinary_media import remove_local_media, upload_image

        if not self.file_local or self.url:
            return self.url
        folder = f"products/{self.product_id}" if self.product_id else "products"
        url, public_id = upload_image(self.file_local, folder=folder)
        if url:
            local_name = self.file_local.name
            self.url, self.file_id, self.file_local = url, public_id, ""
            ProductImage.objects.filter(pk=self.pk).update(
                url=self.url, file_id=self.file_id, file_local=""
            )
            remove_local_media(local_name)
        return self.url

    def get_transformed_url(self, width=None, height=None, quality=None):
        from config.cloudinary_media import resized_url

        return resized_url(self.url, width=width, height=height, quality=quality)


def banner_image_path(instance, filename):
    return f"banners/{filename}"


class HeroBanner(models.Model):
    """Homepage carousel slide managed from the admin."""

    title = models.CharField(max_length=200)
    image = models.ImageField(upload_to=banner_image_path, blank=True, null=True)
    image_url = models.URLField(
        blank=True,
        help_text="Used if no image file is uploaded.",
    )
    link = models.CharField(max_length=500, default="/deals")
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("order", "id")
        verbose_name = "Hero banner"
        verbose_name_plural = "Hero banners"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        _move_image_to_cloudinary(self, "image", "image_url", folder="banners")

    @property
    def resolved_image(self):
        if self.image:
            return self.image.url
        return self.image_url or None


class PriceTier(models.Model):
    """Homepage "Only X ₵" promo tiles."""

    amount = models.PositiveIntegerField()
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("order", "amount")
        verbose_name = "Price tier"
        verbose_name_plural = "Price tiers"

    def __str__(self):
        return f"Only {self.amount}₵"


class StorefrontPromo(models.Model):
    """Site-wide promo copy (top strip, deals header)."""

    key = models.SlugField(unique=True)
    title = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=300, blank=True)
    highlight = models.CharField(max_length=120, blank=True)
    cta_label = models.CharField(max_length=80, blank=True)
    link = models.CharField(max_length=500, default="/deals")
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("order", "id")
        verbose_name = "Storefront promo"
        verbose_name_plural = "Storefront promos"

    def __str__(self):
        return f"{self.key}: {self.title}"


def merch_tile_image_path(instance, filename):
    return f"merch/{instance.placement}/{filename}"


class MerchTile(models.Model):
    """Homepage category / promo circles managed from the admin."""

    PLACEMENT_MAIN = "main"
    PLACEMENT_FEATURED = "featured"
    PLACEMENT_BOTTOM = "bottom"
    PLACEMENT_CHOICES = (
        (PLACEMENT_MAIN, "Main grid"),
        (PLACEMENT_FEATURED, "Featured row"),
        (PLACEMENT_BOTTOM, "Bottom grid"),
    )

    placement = models.CharField(max_length=20, choices=PLACEMENT_CHOICES, default=PLACEMENT_MAIN)
    title = models.CharField(max_length=120)
    image = models.ImageField(upload_to=merch_tile_image_path, blank=True, null=True)
    image_url = models.URLField(blank=True)
    link = models.CharField(max_length=500, default="/products")
    badge = models.CharField(max_length=40, blank=True)
    highlight = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("placement", "order", "id")
        verbose_name = "Merch tile"
        verbose_name_plural = "Merch tiles"

    def __str__(self):
        return f"{self.placement}: {self.title}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        _move_image_to_cloudinary(self, "image", "image_url", folder=f"merch/{self.placement}")

    @property
    def resolved_image(self):
        if self.image:
            return self.image.url
        return self.image_url or None


class HomeSection(models.Model):
    """Product rails on home / deals pages."""

    SOURCE_NEWEST = "newest"
    SOURCE_FEATURED = "featured"
    SOURCE_BESTSELLERS = "bestsellers"
    SOURCE_CHOICES = (
        (SOURCE_NEWEST, "Newest"),
        (SOURCE_FEATURED, "Featured"),
        (SOURCE_BESTSELLERS, "Bestsellers"),
    )
    LOCATION_HOME = "home"
    LOCATION_DEALS = "deals"
    LOCATION_CHOICES = (
        (LOCATION_HOME, "Home"),
        (LOCATION_DEALS, "Deals"),
    )

    key = models.SlugField()
    location = models.CharField(max_length=20, choices=LOCATION_CHOICES, default=LOCATION_HOME)
    title = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=300, blank=True)
    cta_label = models.CharField(max_length=80, default="View More")
    link = models.CharField(max_length=500, default="/products")
    product_source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_FEATURED)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("location", "order", "id")
        unique_together = ("location", "key")
        verbose_name = "Home section"
        verbose_name_plural = "Home sections"

    def __str__(self):
        return f"{self.location}/{self.key}: {self.title}"


class NavLink(models.Model):
    """Secondary category navigation under the header."""

    label = models.CharField(max_length=120)
    link = models.CharField(max_length=500)
    has_dropdown = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("order", "id")
        verbose_name = "Nav link"
        verbose_name_plural = "Nav links"

    def __str__(self):
        return self.label


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

