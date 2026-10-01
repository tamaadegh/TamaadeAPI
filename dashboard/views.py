from datetime import timedelta

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Count, F, Sum, DecimalField, ExpressionWrapper
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache

from orders.models import Order, OrderItem
from products.models import Product, ProductCategory, ProductImage, ProductVideo
from sitecontent.models import BackgroundSound, PrivacyPolicy, SoundSettings
from .forms import (
    BackgroundSoundForm,
    OrderStatusForm,
    PrivacyPolicyForm,
    ProductForm,
    SoundSettingsForm,
)

User = get_user_model()


@never_cache
@staff_member_required
def index(request):
    # Metrics
    total_customers = User.objects.count()
    total_products = Product.objects.count()
    total_orders = Order.objects.count()

    total_sales = (
        OrderItem.objects.aggregate(
            total=Sum(ExpressionWrapper(F("quantity") * F("product__price"), output_field=DecimalField(max_digits=12, decimal_places=2)))
        )["total"]
        or 0
    )

    # Sales trend last 30 days
    thirty_days_ago = timezone.now() - timedelta(days=30)
    sales_trend_qs = (
        OrderItem.objects.filter(created_at__gte=thirty_days_ago)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(
            total=Sum(ExpressionWrapper(F("quantity") * F("product__price"), output_field=DecimalField(max_digits=12, decimal_places=2)))
        )
        .order_by("day")
    )
    sales_trend = {str(item["day"]): float(item["total"]) for item in sales_trend_qs}

    # Top products by quantity
    top_products_qs = (
        OrderItem.objects.values("product__name")
        .annotate(qty=Sum("quantity"))
        .order_by("-qty")[:5]
    )
    top_products = {item["product__name"]: int(item["qty"]) for item in top_products_qs}

    recent_orders = (
        Order.objects.select_related("buyer").order_by("-created_at")[:10]
    )

    context = {
        "total_customers": total_customers,
        "total_products": total_products,
        "total_orders": total_orders,
        "total_sales": float(total_sales),
        "sales_trend": sales_trend,
        "top_products": top_products,
        "recent_orders": recent_orders,
    }
    return render(request, "dashboard/index.html", context)


@never_cache
@staff_member_required
def products_list(request):
    qs = Product.objects.select_related("category", "seller").all()

    q = request.GET.get("q")
    order_by = request.GET.get("sort", "-created_at")

    if q:
        qs = qs.filter(name__icontains=q)

    if order_by:
        qs = qs.order_by(order_by)

    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    form = ProductForm()
    categories = ProductCategory.objects.all()

    return render(
        request,
        "dashboard/products_list.html",
        {"page_obj": page_obj, "query": q or "", "sort": order_by, "form": form, "categories": categories},
    )


@never_cache
@staff_member_required
def product_create(request):
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.seller = request.user
            product.save()
            # Handle multiple uploaded images/videos
            for idx, f in enumerate(request.FILES.getlist('image_files')):
                ProductImage.objects.create(product=product, file_local=f, order=idx)
            for idx, f in enumerate(request.FILES.getlist('video_files')):
                ProductVideo.objects.create(product=product, file_local=f, order=idx)
            messages.success(request, f'Product "{product.name}" created successfully!')
            return redirect("dashboard:products_list")
        else:
            # Form has errors, re-render with error messages
            messages.error(request, 'Please correct the errors below.')
            qs = Product.objects.select_related("category", "seller").all()
            q = request.GET.get("q")
            order_by = request.GET.get("sort", "-created_at")
            if q:
                qs = qs.filter(name__icontains=q)
            if order_by:
                qs = qs.order_by(order_by)
            paginator = Paginator(qs, 12)
            page_obj = paginator.get_page(request.GET.get("page"))
            categories = ProductCategory.objects.all()
            return render(
                request,
                "dashboard/products_list.html",
                {"page_obj": page_obj, "query": q or "", "sort": order_by, "form": form, "categories": categories},
            )
    return redirect("dashboard:products_list")


@never_cache
@staff_member_required
def product_update(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            # Update multiple uploads
            for idx, f in enumerate(request.FILES.getlist('image_files')):
                ProductImage.objects.create(product=product, file_local=f, order=idx)
            for idx, f in enumerate(request.FILES.getlist('video_files')):
                ProductVideo.objects.create(product=product, file_local=f, order=idx)
            messages.success(request, f'Product "{product.name}" updated successfully!')
        else:
            messages.error(request, 'Failed to update product. Please check the form.')
    return redirect("dashboard:products_list")


@never_cache
@staff_member_required
def product_delete(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if request.method == "POST":
        product_name = product.name
        product.delete()
        messages.success(request, f'Product "{product_name}" deleted successfully!')
    return redirect("dashboard:products_list")


@never_cache
@staff_member_required
def product_detail(request, product_id):
    product = get_object_or_404(Product.objects.select_related("category", "seller"), id=product_id)
    return render(
        request,
        "dashboard/product_detail.html",
        {"product": product},
    )


@never_cache
@staff_member_required
def orders_list(request):
    qs = (
        Order.objects.select_related("buyer")
        .prefetch_related("order_items__product")
        .all()
    )

    status = request.GET.get("status")
    if status in dict(Order.STATUS_CHOICES):
        qs = qs.filter(status=status)

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "dashboard/orders_list.html",
        {"page_obj": page_obj, "status": status or ""},
    )


@never_cache
@staff_member_required
def order_update_status(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if request.method == "POST":
        form = OrderStatusForm(request.POST, instance=order)
        if form.is_valid():
            form.save()
    return redirect("dashboard:orders_list")


@never_cache
@staff_member_required
def users_list(request):
    qs = (
        User.objects.all()
        .annotate(total_orders=Count("orders", distinct=True))
    )

    # Total spent per user using OrderItem linkage
    spent_map = (
        OrderItem.objects.values("order__buyer")
        .annotate(
            total=Sum(ExpressionWrapper(F("quantity") * F("product__price"), output_field=DecimalField(max_digits=12, decimal_places=2)))
        )
    )
    spent_dict = {row["order__buyer"]: float(row["total"]) for row in spent_map}

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "dashboard/users_list.html",
        {"page_obj": page_obj, "spent": spent_dict},
    )


@never_cache
@staff_member_required
def privacy_settings(request):
    policy = PrivacyPolicy.load()
    if request.method == "POST":
        form = PrivacyPolicyForm(request.POST, instance=policy)
        if form.is_valid():
            form.save()
            messages.success(request, "Privacy page updated. It is live on web and mobile.")
            return redirect("dashboard:privacy_settings")
        messages.error(request, "Please correct the errors below.")
    else:
        form = PrivacyPolicyForm(instance=policy)
    return render(request, "dashboard/privacy_settings.html", {"form": form, "policy": policy})


@never_cache
@staff_member_required
def sound_settings(request):
    settings_obj = SoundSettings.load()
    settings_form = SoundSettingsForm(instance=settings_obj)
    create_form = BackgroundSoundForm(initial={"is_active": not BackgroundSound.objects.exists()})

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "toggle":
            settings_form = SoundSettingsForm(request.POST, instance=settings_obj)
            if settings_form.is_valid():
                settings_form.save()
                state = "enabled" if settings_obj.music_enabled else "disabled"
                messages.success(request, f"Background music {state} for all users.")
                return redirect("dashboard:sound_settings")
        elif action == "create":
            create_form = BackgroundSoundForm(request.POST, request.FILES)
            if create_form.is_valid():
                sound = create_form.save()
                messages.success(request, f'Sound "{sound.title}" uploaded.')
                return redirect("dashboard:sound_settings")
            messages.error(request, "Could not upload the sound. Please check the form.")

    sounds = BackgroundSound.objects.defer("audio_data")
    edit_forms = [(sound, BackgroundSoundForm(instance=sound, prefix=f"s{sound.pk}")) for sound in sounds]
    return render(
        request,
        "dashboard/sound_settings.html",
        {
            "settings_form": settings_form,
            "sound_settings": settings_obj,
            "create_form": create_form,
            "edit_forms": edit_forms,
        },
    )


@never_cache
@staff_member_required
def sound_update(request, sound_id):
    sound = get_object_or_404(BackgroundSound, id=sound_id)
    if request.method == "POST":
        form = BackgroundSoundForm(request.POST, request.FILES, instance=sound, prefix=f"s{sound.pk}")
        if form.is_valid():
            form.save()
            messages.success(request, f'Sound "{sound.title}" updated.')
        else:
            errors = "; ".join(e for errs in form.errors.values() for e in errs)
            messages.error(request, f"Could not update the sound: {errors}")
    return redirect("dashboard:sound_settings")


@never_cache
@staff_member_required
def sound_activate(request, sound_id):
    sound = get_object_or_404(BackgroundSound.objects.defer("audio_data"), id=sound_id)
    if request.method == "POST":
        sound.is_active = True
        sound.save(update_fields=["is_active", "updated_at"])
        messages.success(request, f'"{sound.title}" is now the background music.')
    return redirect("dashboard:sound_settings")


@never_cache
@staff_member_required
def sound_delete(request, sound_id):
    sound = get_object_or_404(BackgroundSound.objects.defer("audio_data"), id=sound_id)
    if request.method == "POST":
        title = sound.title
        sound.delete()
        messages.success(request, f'Sound "{title}" deleted.')
    return redirect("dashboard:sound_settings")
