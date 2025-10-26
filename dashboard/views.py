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
from products.models import Product, ProductCategory
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
