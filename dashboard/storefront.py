"""
Storefront content pages in the dashboard: categories, hero banners and home tiles.

One small generic list / form / delete flow driven by RESOURCES, so the three pages share the
dashboard design instead of sending staff to the Django admin.
"""
from dataclasses import dataclass, field
from typing import Callable

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache

from products.models import (
    HeroBanner,
    HomeSection,
    MerchTile,
    NavLink,
    PriceTier,
    ProductCategory,
    StorefrontPromo,
)

from .forms import (
    CategoryForm,
    HeroBannerForm,
    HomeSectionForm,
    MerchTileForm,
    NavLinkForm,
    PriceTierForm,
    StorefrontPromoForm,
)


def _active_pill(obj):
    return ("success", "Live") if obj.is_active else ("neutral", "Hidden")


@dataclass
class Resource:
    slug: str
    title: str
    singular: str
    icon: str
    description: str
    form_class: type
    queryset: Callable
    image: Callable  # obj -> url or None
    name: Callable  # obj -> main text
    subtitle: Callable  # obj -> small text under the name
    columns: list = field(default_factory=list)  # [(label, obj -> text)]
    status: Callable = None  # obj -> (pill kind, label)
    round_image: bool = True
    has_image: bool = True
    empty_hint: str = ""
    delete_warning: Callable = lambda obj: ""

    def row(self, obj):
        return {
            "obj": obj,
            "image": self.image(obj),
            "name": self.name(obj),
            "subtitle": self.subtitle(obj),
            "cells": [fn(obj) for _, fn in self.columns],
            "status": self.status(obj) if self.status else None,
        }


RESOURCES = {
    "categories": Resource(
        slug="categories",
        title="Categories",
        singular="category",
        icon="fa-shapes",
        description="Group products so people can browse them. Each category shows its image in the apps.",
        form_class=CategoryForm,
        queryset=lambda: ProductCategory.objects.annotate(n_products=Count("product_list")).order_by("name"),
        image=lambda o: o.resolved_icon,
        name=lambda o: o.name,
        subtitle=lambda o: "No image yet: the apps show its first letter" if not o.resolved_icon else "",
        columns=[("Products", lambda o: o.n_products), ("Created", lambda o: o.created_at.strftime("%d %b %Y"))],
        status=lambda o: ("success", "Image") if o.resolved_icon else ("warning", "No image"),
        empty_hint="Create a category, then pick it when you add products.",
        delete_warning=lambda o: (
            f"Its {o.n_products} product{'s' if o.n_products != 1 else ''} will be moved to “Others”."
            if getattr(o, "n_products", 0) else ""
        ),
    ),
    "banners": Resource(
        slug="banners",
        title="Banners",
        singular="banner",
        icon="fa-images",
        description="The big slides at the top of the home page, on the website and in the app.",
        form_class=HeroBannerForm,
        queryset=lambda: HeroBanner.objects.order_by("order", "id"),
        image=lambda o: o.resolved_image,
        name=lambda o: o.title,
        subtitle=lambda o: f"Opens {o.link}" if o.link else "",
        columns=[("Position", lambda o: o.order)],
        status=_active_pill,
        round_image=False,
        empty_hint="Add a banner to promote deals or new arrivals on the home page.",
    ),
    "tiles": Resource(
        slug="tiles",
        title="Home tiles",
        singular="tile",
        icon="fa-circle-dot",
        description="The round shortcuts on the home page (main grid, featured row and bottom grid).",
        form_class=MerchTileForm,
        queryset=lambda: MerchTile.objects.order_by("placement", "order", "id"),
        image=lambda o: o.resolved_image,
        name=lambda o: o.title,
        subtitle=lambda o: f"Opens {o.link}" if o.link else "",
        columns=[
            ("Where", lambda o: o.get_placement_display()),
            ("Badge", lambda o: o.badge or "—"),
            ("Position", lambda o: o.order),
        ],
        status=_active_pill,
        empty_hint="Add tiles to give shoppers one-tap shortcuts to categories and deals.",
    ),
    "sections": Resource(
        slug="sections",
        title="Home sections",
        singular="section",
        icon="fa-table-list",
        description="Product rows on the home and Deals pages, e.g. “New arrivals”.",
        form_class=HomeSectionForm,
        queryset=lambda: HomeSection.objects.order_by("location", "order", "id"),
        image=lambda o: None,
        name=lambda o: o.title,
        subtitle=lambda o: o.subtitle,
        columns=[
            ("Page", lambda o: o.get_location_display()),
            ("Products", lambda o: o.get_product_source_display()),
            ("Position", lambda o: o.order),
        ],
        status=_active_pill,
        has_image=False,
        empty_hint="Add a section to show a row of products on the home page.",
    ),
    "promos": Resource(
        slug="promos",
        title="Promo strips",
        singular="promo",
        icon="fa-bullhorn",
        description="The promo strip on the home page and the header of the Deals page.",
        form_class=StorefrontPromoForm,
        queryset=lambda: StorefrontPromo.objects.order_by("order", "id"),
        image=lambda o: None,
        name=lambda o: o.title,
        subtitle=lambda o: o.highlight or o.subtitle,
        columns=[("Key", lambda o: o.key), ("Position", lambda o: o.order)],
        status=_active_pill,
        has_image=False,
        empty_hint="Add a promo with the key top_strip to show a strip on the home page.",
    ),
    "price-tiers": Resource(
        slug="price-tiers",
        title="Shop by budget",
        singular="price tier",
        icon="fa-coins",
        description="The “Under GH₵…” shortcuts on the home page.",
        form_class=PriceTierForm,
        queryset=lambda: PriceTier.objects.order_by("order", "amount"),
        image=lambda o: None,
        name=lambda o: f"Under GH₵{o.amount:,}",
        subtitle=lambda o: "",
        columns=[("Position", lambda o: o.order)],
        status=_active_pill,
        has_image=False,
        empty_hint="Add amounts like 100, 500 and 1000 to help people shop by budget.",
    ),
    "nav-links": Resource(
        slug="nav-links",
        title="Website menu",
        singular="menu link",
        icon="fa-bars",
        description="Links in the top menu of the website.",
        form_class=NavLinkForm,
        queryset=lambda: NavLink.objects.order_by("order", "id"),
        image=lambda o: None,
        name=lambda o: o.label,
        subtitle=lambda o: o.link,
        columns=[("Dropdown", lambda o: "Yes" if o.has_dropdown else "No"), ("Position", lambda o: o.order)],
        status=_active_pill,
        has_image=False,
        empty_hint="Add links to show them in the website menu.",
    ),
}


def _resource(slug):
    try:
        return RESOURCES[slug]
    except KeyError:
        raise Http404


@never_cache
@staff_member_required
def resource_list(request, slug):
    res = _resource(slug)
    rows = [res.row(obj) for obj in res.queryset()]
    return render(request, "dashboard/resource_list.html", {"res": res, "rows": rows})


@never_cache
@staff_member_required
def resource_edit(request, slug, pk=None):
    res = _resource(slug)
    model = res.form_class._meta.model
    obj = get_object_or_404(model, pk=pk) if pk else None
    if request.method == "POST":
        form = res.form_class(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            saved = form.save()
            verb = "updated" if obj else "created"
            messages.success(request, f"{res.singular.capitalize()} “{res.name(saved)}” {verb}.")
            return redirect("dashboard:resource_list", slug=slug)
        messages.error(request, "Some fields need your attention.")
    else:
        form = res.form_class(instance=obj)
    return render(
        request,
        "dashboard/resource_form.html",
        {"res": res, "form": form, "obj": obj, "current_image": res.image(obj) if obj else None},
    )


@never_cache
@staff_member_required
def resource_delete(request, slug, pk):
    res = _resource(slug)
    obj = get_object_or_404(res.form_class._meta.model, pk=pk)
    if request.method == "POST":
        name = res.name(obj)
        obj.delete()
        messages.success(request, f"{res.singular.capitalize()} “{name}” deleted.")
    return redirect("dashboard:resource_list", slug=slug)
