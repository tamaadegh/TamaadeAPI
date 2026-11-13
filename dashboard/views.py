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

# Sort keys the products page offers (anything else falls back to newest first).
PRODUCT_SORTS = {"-created_at", "name", "-price", "price", "quantity"}


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
    by_day = {item["day"]: float(item["total"] or 0) for item in sales_trend_qs}
    # Every day of the window, so the chart shows quiet days as 0 instead of skipping them.
    today = timezone.localdate()
    days = [today - timedelta(days=offset) for offset in range(29, -1, -1)]
    sales_trend = {day.strftime("%d %b"): by_day.get(day, 0.0) for day in days}
    sales_30d = sum(by_day.values())

    # Top products by quantity
    top_products_qs = (
        OrderItem.objects.values("product__name")
        .annotate(qty=Sum("quantity"))
        .order_by("-qty")[:5]
    )
    top_rows = [(item["product__name"], int(item["qty"] or 0)) for item in top_products_qs]
    top_max = max((qty for _, qty in top_rows), default=0) or 1
    top_products = [
        {"name": name, "qty": qty, "pct": round(qty * 100 / top_max)} for name, qty in top_rows
    ]

    recent_orders = (
        Order.objects.select_related("buyer").order_by("-created_at")[:8]
    )

    context = {
        "total_customers": total_customers,
        "total_products": total_products,
        "total_orders": total_orders,
        "total_sales": float(total_sales),
        "sales_30d": sales_30d,
        "pending_orders": Order.objects.filter(status=Order.PENDING).count(),
        "low_stock": Product.objects.filter(quantity__lte=3).count(),
        "new_customers_30d": User.objects.filter(date_joined__gte=thirty_days_ago).count(),
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
    if order_by not in PRODUCT_SORTS:
        order_by = "-created_at"

    if q:
        qs = qs.filter(name__icontains=q)

    qs = qs.order_by(order_by)

    paginator = Paginator(qs, 20)
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
            qs = qs.order_by("-created_at")
            paginator = Paginator(qs, 20)
            page_obj = paginator.get_page(request.GET.get("page"))
            categories = ProductCategory.objects.all()
            return render(
                request,
                "dashboard/products_list.html",
                {"page_obj": page_obj, "query": "", "sort": "-created_at", "form": form, "categories": categories},
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
            messages.success(request, f'Product "{product.name}" updated.')
        else:
            errors = "; ".join(f"{form.fields[k].label if k in form.fields else k}: {e}" for k, errs in form.errors.items() for e in errs)
            messages.error(request, f"Could not update the product. {errors}")
    back = request.POST.get("next") or ""
    if back.startswith("/dashboard/"):
        return redirect(back)
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
        {"product": product, "categories": ProductCategory.objects.all()},
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

    paginator = Paginator(qs.order_by("-created_at"), 15)
    page_obj = paginator.get_page(request.GET.get("page"))
    counts = {row["status"]: row["n"] for row in Order.objects.values("status").annotate(n=Count("id"))}

    return render(
        request,
        "dashboard/orders_list.html",
        {
            "page_obj": page_obj,
            "status": status or "",
            "count_all": sum(counts.values()),
            "count_pending": counts.get(Order.PENDING, 0),
            "count_completed": counts.get(Order.COMPLETED, 0),
        },
    )


@never_cache
@staff_member_required
def order_update_status(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if request.method == "POST":
        form = OrderStatusForm(request.POST, instance=order)
        if form.is_valid():
            form.save()
            messages.success(request, f"Order #{order.id} marked as {order.get_status_display()}.")
    back = request.POST.get("next") or ""
    if back.startswith("/dashboard/"):
        return redirect(back)
    return redirect("dashboard:orders_list")


@never_cache
@staff_member_required
def users_list(request):
    qs = (
        User.objects.all()
        .annotate(total_orders=Count("orders", distinct=True))
        .order_by("-date_joined")
    )
    q = (request.GET.get("q") or "").strip()
    if q:
        from django.db.models import Q

        qs = qs.filter(
            Q(first_name__icontains=q) | Q(last_name__icontains=q)
            | Q(email__icontains=q) | Q(username__icontains=q)
            | Q(phone__phone_number__icontains=q)
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
        {"page_obj": page_obj, "spent": spent_dict, "query": q, "total_users": paginator.count},
    )


@never_cache
@staff_member_required
def insights(request):
    """Operational health: did payments land, are carts being abandoned, is
    anything failing for customers?

    Everything here is derived from real rows - Payment/Order state plus the
    SystemEvent log - so an empty panel means "nothing has happened yet", not
    "not implemented".
    """
    from django.conf import settings
    from django.db.models import Q

    from dashboard.models import SystemEvent
    from payment.models import Payment

    now = timezone.now()
    window_days = int(request.GET.get("days") or 30)
    since = now - timedelta(days=window_days)

    # ---- Payments -----------------------------------------------------
    # Order.total_cost is a Python property, so money has to be summed via an
    # annotation over the line items rather than read off the order.
    line_value = ExpressionWrapper(
        F("order__order_items__quantity") * F("order__order_items__product__price"),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )

    def money(qs):
        return qs.aggregate(v=Sum(line_value))["v"] or 0

    payments = Payment.objects.filter(created_at__gte=since)
    paid_qs = payments.filter(status=Payment.COMPLETED)
    pending_qs = payments.filter(status=Payment.PENDING)
    failed_qs = payments.filter(status=Payment.FAILED)

    paid_count = paid_qs.count()
    pending_count = pending_qs.count()
    failed_count = failed_qs.count()
    attempted = paid_count + pending_count + failed_count

    payment_stats = {
        "attempted": attempted,
        "paid": paid_count,
        "pending": pending_count,
        "failed": failed_count,
        "paid_value": float(money(paid_qs)),
        "pending_value": float(money(pending_qs)),
        "failed_value": float(money(failed_qs)),
        "success_rate": round(paid_count / attempted * 100, 1) if attempted else None,
        "failure_rate": round(failed_count / attempted * 100, 1) if attempted else None,
    }

    # ---- Carts --------------------------------------------------------
    # A cart here is a PENDING order holding items. "Abandoned" = untouched for
    # longer than the stale window; anything with a payment row got as far as
    # checkout, which makes it the highest-intent group to follow up.
    stale_hours = int(request.GET.get("stale_hours") or 24)
    stale_before = now - timedelta(hours=stale_hours)

    cart_value = ExpressionWrapper(
        F("order_items__quantity") * F("order_items__product__price"),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )
    carts = (
        Order.objects.filter(status=Order.PENDING)
        .annotate(items=Count("order_items", distinct=True))
        .filter(items__gt=0)
    )
    active_carts = carts.filter(updated_at__gte=stale_before)
    abandoned = carts.filter(updated_at__lt=stale_before)

    abandoned_list = (
        abandoned.select_related("buyer")
        .annotate(value=Sum(cart_value))
        .order_by("updated_at")[:20]
    )

    cart_stats = {
        "stale_hours": stale_hours,
        "active": active_carts.count(),
        "abandoned": abandoned.count(),
        "abandoned_value": float(abandoned.aggregate(v=Sum(cart_value))["v"] or 0),
        # Reached Hubtel but never completed - worth chasing first.
        "reached_checkout": abandoned.filter(
            Q(payment__status=Payment.PENDING) | Q(payment__status=Payment.FAILED)
        ).count(),
    }

    # ---- Signup / auth health ----------------------------------------
    events = SystemEvent.objects.filter(created_at__gte=since)
    signup_ok = events.filter(category=SystemEvent.CAT_SIGNUP, level=SystemEvent.LEVEL_INFO).count()
    signup_bad = events.filter(
        category=SystemEvent.CAT_SIGNUP,
        level__in=[SystemEvent.LEVEL_WARNING, SystemEvent.LEVEL_ERROR],
    ).count()
    signup_attempts = signup_ok + signup_bad

    signup_stats = {
        "succeeded": signup_ok,
        "failed": signup_bad,
        "failure_rate": round(signup_bad / signup_attempts * 100, 1) if signup_attempts else None,
    }

    # ---- Problem feed -------------------------------------------------
    problems = (
        events.filter(level__in=[SystemEvent.LEVEL_WARNING, SystemEvent.LEVEL_ERROR])
        .select_related("user")
        .order_by("-created_at")[:40]
    )
    by_category = list(
        events.filter(level__in=[SystemEvent.LEVEL_WARNING, SystemEvent.LEVEL_ERROR])
        .values("category")
        .annotate(n=Count("id"))
        .order_by("-n")
    )
    recent_events = (
        events.select_related("user").order_by("-created_at")[:40]
    )

    # ---- Integration health ------------------------------------------
    # Config gaps that silently degrade the storefront. Checked live rather than
    # hardcoded, so the panel stays honest as the .env changes.
    email_ready = bool(settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD)
    integrations = [
        {
            "name": "Hubtel payments",
            "ok": all([
                settings.HUBTEL_API_ID,
                settings.HUBTEL_API_KEY,
                settings.HUBTEL_COLLECTION_ACCOUNT_NUMBER,
            ]),
            "detail": "Customers cannot pay without this.",
        },
        {
            "name": "Outbound e-mail",
            "ok": email_ready,
            "detail": (
                "Verification and password-reset e-mails are delivered."
                if email_ready
                else "No SMTP credentials: verification e-mails are not delivered, so "
                     "e-mail verification is running in optional mode."
            ),
        },
        {
            "name": "SMS (Hubtel)",
            "ok": settings.OTP_SMS_PROVIDER == "hubtel" and all([
                settings.HUBTEL_SMS_CLIENT_ID,
                settings.HUBTEL_SMS_CLIENT_SECRET,
                settings.HUBTEL_SMS_SENDER_ID,
            ]),
            "detail": "Phone sign-in codes cannot be sent without this.",
        },
        {
            "name": "Cloudinary uploads",
            "ok": bool(settings.CLOUDINARY_URL),
            "detail": "New product and category images are uploaded here.",
        },
    ]

    context = {
        "window_days": window_days,
        "payment_stats": payment_stats,
        "cart_stats": cart_stats,
        "abandoned_list": abandoned_list,
        "signup_stats": signup_stats,
        "problems": problems,
        "problem_count": len(problems),
        "by_category": by_category,
        "recent_events": recent_events,
        "integrations": integrations,
        "integration_problems": [i for i in integrations if not i["ok"]],
        "stuck_payments": (
            Payment.objects.filter(status=Payment.PENDING, created_at__lt=now - timedelta(hours=2))
            .select_related("order__buyer")
            .order_by("created_at")[:20]
        ),
    }
    return render(request, "dashboard/insights.html", context)
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
