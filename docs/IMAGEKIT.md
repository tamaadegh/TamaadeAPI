# ImageKit Integration

This project now integrates with ImageKit for media upload and hosting.

## Environment variables

Set the following in your `.env` or environment:

- IMAGEKIT_PUBLIC_KEY
- IMAGEKIT_PRIVATE_KEY
- IMAGEKIT_URL_ENDPOINT

Example:

```
IMAGEKIT_PUBLIC_KEY=public_...
IMAGEKIT_PRIVATE_KEY=private_...
IMAGEKIT_URL_ENDPOINT=https://ik.imagekit.io/your_imagekit_id
```

## Key changes in the project

- Added `config/imagekit.py` to initialize the SDK from the Django settings.
- New models in `products/models.py`:
  - `ProductImage` (supports multiple images per product)
  - `ProductVideo` (supports multiple videos per product)
  These use a temporary `file_local` field; files are uploaded to ImageKit and the returned `url` and `file_id` are stored.
- Admin now provides inlines to add multiple images and videos to a product.
- Dashboard `ProductForm` now supports `image_files` and `video_files` for multi-file uploads.
- Templates were updated to render the first item from `product.images` and `product.videos` if available.
- `ImageKit` keys are read from environment variables and are no longer hardcoded in source.
 - Uploads can optionally run asynchronously using Celery. Configure `IMAGEKIT_UPLOAD_ASYNC` in your `.env` to toggle.
 - A management command `migrate_media_to_imagekit` was added to migrate existing `Product.image` and `Product.video` fields into the new ImageKit-backed models.
 - A template tag `{% imagekit_url src width=300 height=300 quality=60 %}` is available via `{% load imagekit_tags %}` to generate transformed ImageKit URLs inside templates.

## Install dependencies and run

Make sure the `imagekitio` package is installed; it's already added to `requirements.txt`.

Build and run docker containers (production-like):

```pwsh
# Build and run production-like containers locally
docker compose -f docker-compose.prod.yml up --build --remove-orphans

# Run migrations for production container
docker compose -f docker-compose.prod.yml exec web python manage.py migrate

# Create superuser
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
```

## Admin dashboard

- Staff can upload multiple images and videos when creating or editing products via the dashboard UI.
- Files are uploaded to ImageKit and the returned URLs are used in frontends. Local files are removed if they were saved temporarily.

## Celery & async uploads

- To perform uploads asynchronously, set `IMAGEKIT_UPLOAD_ASYNC=True` in your `.env` and ensure a Celery worker is running.

When creating `ProductImage` or `ProductVideo` objects, the Celery task `upload_product_image_to_imagekit` or `upload_product_video_to_imagekit` will be scheduled for uploading.

## After deploying

1. Add the ImageKit keys to your environment on your deployment platform.
2. Run `python manage.py makemigrations` and `python manage.py migrate` to add `ProductImage` and `ProductVideo` tables.
3. Rebuild and restart your containers.
## ProductImage / ProductVideo APIs

The following REST endpoints are available under `/api/products/`:

- `GET /api/products/images/` - list all product images
- `GET /api/products/images/{id}/` - retrieve product image details
- `POST /api/products/images/` - create product image (requires `product` id and `file_local` attached)
- `PATCH/PUT /api/products/images/{id}/` - update product image
- `DELETE /api/products/images/{id}/` - delete product image

- `GET /api/products/videos/` - list all product videos
- `GET /api/products/videos/{id}/` - retrieve product video details
- `POST /api/products/videos/` - create product video (requires `product` id and `file_local` attached)
- `PATCH/PUT /api/products/videos/{id}/` - update product video
- `DELETE /api/products/videos/{id}/` - delete product video

Permissions: Create, update and delete operations are restricted to the product seller or staff admins. Read operations are public.


## Migrating existing media

Run the included management command to migrate legacy `Product.image` and `Product.video` fields to `ProductImage`/`ProductVideo` records:

```pwsh
python manage.py migrate_media_to_imagekit
```

After verifying that all media was migrated and ImageKit URLs are present (or uploads are scheduled), optionally run the migration `0004_remove_legacy_image_video.py` to drop the legacy fields.

If you want advanced features (image transformations, signed URLs for private files), we can add helpers or template tags to generate transform URLs (resize, quality) for mobile optimization. Please tell me if you'd like that too.