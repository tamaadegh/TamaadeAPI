from django.db import migrations, models
import products.models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0004_remove_legacy_image_video"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="image",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to=products.models.product_image_path,
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="video",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to=products.models.product_video_path,
            ),
        ),
    ]
