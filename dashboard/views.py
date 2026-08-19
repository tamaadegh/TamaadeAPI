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
from .forms import ProductForm, OrderStatusForm

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
            "name": "SMS (Twilio)",
            "ok": all([
                settings.TWILIO_ACCOUNT_SID,
                settings.TWILIO_AUTH_TOKEN,
                settings.TWILIO_PHONE_NUMBER,
            ]),
            "detail": "Phone OTP codes cannot be sent without this.",
        },
        {
            "name": "ImageKit uploads",
            "ok": bool(settings.IMAGEKIT_PRIVATE_KEY and settings.IMAGEKIT_URL_ENDPOINT),
            "detail": "New product images are uploaded here.",
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
