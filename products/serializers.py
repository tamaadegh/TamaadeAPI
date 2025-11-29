from rest_framework import serializers

from products.models import Product, ProductCategory, ProductImage, ProductVideo


class ProductCategoryReadSerializer(serializers.ModelSerializer):
    """
    Serializer class for product categories
    """

    class Meta:
        model = ProductCategory
        fields = "__all__"


class ProductReadSerializer(serializers.ModelSerializer):
    """
    Serializer class for reading products
    """

    seller = serializers.CharField(source="seller.get_full_name", read_only=True)
    category = serializers.CharField(source="category.name", read_only=True)
    images = serializers.SerializerMethodField()
    videos = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = "__all__"

    def get_images(self, obj):
        images = obj.images.all()
        return ProductImageSerializer(images, many=True).data

    def get_videos(self, obj):
        videos = obj.videos.all()
        return ProductVideoSerializer(videos, many=True).data


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ("id", "url", "file_id", "is_primary", "order")


class ProductImageCreateSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    class Meta:
        model = ProductImage
        fields = ("id", "file_local", "url", "file_id", "is_primary", "order")
        read_only_fields = ("url", "file_id")


class ProductVideoCreateSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    class Meta:
        model = ProductVideo
        fields = ("id", "file_local", "url", "file_id", "is_primary", "order")
        read_only_fields = ("url", "file_id")


class ProductVideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVideo
        fields = ("id", "url", "file_id", "is_primary", "order")


class ProductWriteSerializer(serializers.ModelSerializer):
    """
    Serializer class for writing products
    """

    seller = serializers.HiddenField(default=serializers.CurrentUserDefault())
    category = ProductCategoryReadSerializer()

    image_files = serializers.ListField(child=serializers.FileField(), write_only=True, required=False)
    video_files = serializers.ListField(child=serializers.FileField(), write_only=True, required=False)

    class Meta:
        model = Product
        fields = (
            "seller",
            "category",
            "name",
            "desc",
            "image",
            "price",
            "quantity",
            "image_files",
            "video_files",
        )

    def create(self, validated_data):
        category = validated_data.pop("category")
        image_files = validated_data.pop("image_files", []) if "image_files" in validated_data else []
        video_files = validated_data.pop("video_files", []) if "video_files" in validated_data else []
        instance, created = ProductCategory.objects.get_or_create(**category)
        product = Product.objects.create(**validated_data, category=instance)

        # Create ProductImage instances for uploaded image files
        for index, f in enumerate(image_files):
            ProductImage.objects.create(product=product, file_local=f, order=index)

        # Create ProductVideo instances for uploaded video files
        for index, f in enumerate(video_files):
            ProductVideo.objects.create(product=product, file_local=f, order=index)

        return product

    def update(self, instance, validated_data):
        if "category" in validated_data:
            nested_serializer = self.fields["category"]
            nested_instance = instance.category
            nested_data = validated_data.pop("category")
            nested_serializer.update(nested_instance, nested_data)

        # Handle uploaded files during update
        image_files = validated_data.pop("image_files", []) if "image_files" in validated_data else []
        video_files = validated_data.pop("video_files", []) if "video_files" in validated_data else []

        instance = super(ProductWriteSerializer, self).update(instance, validated_data)

        for idx, f in enumerate(image_files):
            ProductImage.objects.create(product=instance, file_local=f, order=idx)

        for idx, f in enumerate(video_files):
            ProductVideo.objects.create(product=instance, file_local=f, order=idx)

        return instance
