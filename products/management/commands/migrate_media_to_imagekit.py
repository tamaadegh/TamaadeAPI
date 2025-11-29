from django.core.management.base import BaseCommand
from products.models import Product, ProductImage, ProductVideo


class Command(BaseCommand):
    help = "Migrate existing Product.image and Product.video fields to ProductImage/ProductVideo models"

    def handle(self, *args, **options):
        migrated_images = 0
        migrated_videos = 0
        for product in Product.objects.all():
            if product.image:
                # Create ProductImage pointing to the same file
                try:
                    ProductImage.objects.create(product=product, file_local=product.image, is_primary=True)
                    migrated_images += 1
                except Exception:
                    self.stdout.write(self.style.WARNING(f"Failed to migrate image for Product id={product.id}"))
            if product.video:
                try:
                    ProductVideo.objects.create(product=product, file_local=product.video, is_primary=True)
                    migrated_videos += 1
                except Exception:
                    self.stdout.write(self.style.WARNING(f"Failed to migrate video for Product id={product.id}"))

        self.stdout.write(self.style.SUCCESS(f"Migrated {migrated_images} images and {migrated_videos} videos to ImageKit model instances."))
