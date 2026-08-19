"""Populate the storefront's homepage chrome from the real catalog.

The homepage, nav bar and /deals page are entirely data-driven: HomeSection,
NavLink, MerchTile, HeroBanner. With those tables empty the homepage renders
blank even though the catalog is fine, because `sections.map(...)` has nothing
to iterate. The legacy nxtbn database had no equivalent rows to carry over (its
29 product collections were all empty), so the structure has to be created.

Everything here is derived from real categories and real product imagery, and
only categories that actually contain products get a tile or nav entry — a
shopper should never land on an empty listing.

Deliberately NOT seeded: PriceTier and StorefrontPromo. Both exist to state
discounts ("Only 50₵", "UP TO 70% OFF"), and inventing a price claim is a
business decision, not a deployment one. They stay empty, which renders as
nothing, and staff can add real offers in the admin.

Idempotent: matches on the natural key of each row, so re-running updates
rather than duplicating.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from products.models import HeroBanner, HomeSection, MerchTile, NavLink, Product, ProductCategory


class Command(BaseCommand):
    help = "Create homepage sections, nav links, category tiles and hero banners from the real catalog."

    def add_arguments(self, parser):
        parser.add_argument("--max-tiles", type=int, default=12,
                            help="Cap on category circles for the homepage grid.")
        parser.add_argument("--max-nav", type=int, default=8,
                            help="Cap on secondary nav entries.")
        parser.add_argument("--hero-count", type=int, default=3,
                            help="Number of hero slides to build from top categories.")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        try:
            with transaction.atomic():
                lines = self._run(opts)
                if opts["dry_run"]:
                    raise _Rollback()
        except _Rollback:
            lines.append(self.style.WARNING("DRY RUN - rolled back."))
        for line in lines:
            self.stdout.write(line)

    def _run(self, opts):
        out = []

        # Only categories holding stock-worthy products are worth linking to.
        stocked = (
            ProductCategory.objects.annotate(n=Count("product_list"))
            .filter(n__gt=0)
            .order_by("-n", "name")
        )
        if not stocked:
            out.append(self.style.ERROR("No categories contain products - nothing to build."))
            return out
        out.append(f"Categories with products: {stocked.count()}")

        # ---- Home sections: the rails that actually surface products --------
        sections = [
            ("new-arrivals", "home", "New Arrivals", "The latest additions to our catalogue",
             HomeSection.SOURCE_NEWEST, "View All", "/products", 0),
            ("shop-range", "home", "Shop Our Range", "Furniture, electronics and tools",
             HomeSection.SOURCE_FEATURED, "View All", "/products", 1),
            ("more-from-tamaade", "home", "More From Tamaade", "",
             HomeSection.SOURCE_BESTSELLERS, "View All", "/products", 2),
            ("deals-all", "deals", "Browse the Catalogue", "",
             HomeSection.SOURCE_FEATURED, "View All", "/products", 0),
        ]
        n_sec = 0
        for key, loc, title, subtitle, source, cta, link, order in sections:
            HomeSection.objects.update_or_create(
                location=loc, key=key,
                defaults={
                    "title": title, "subtitle": subtitle, "product_source": source,
                    "cta_label": cta, "link": link, "order": order, "is_active": True,
                },
            )
            n_sec += 1
        out.append(f"Home sections:  {n_sec} (3 on /, 1 on /deals)")

        # ---- Secondary nav -------------------------------------------------
        n_nav = 0
        for order, cat in enumerate(stocked[: opts["max_nav"]]):
            NavLink.objects.update_or_create(
                label=cat.name,
                defaults={
                    "link": f"/products?category={cat.name}",
                    "has_dropdown": False, "order": order, "is_active": True,
                },
            )
            n_nav += 1
        out.append(f"Nav links:      {n_nav}")

        # ---- Category circles, illustrated with a real product photo -------
        n_tile = 0
        missing_img = []
        for order, cat in enumerate(stocked[: opts["max_tiles"]]):
            image_url = self._category_image(cat)
            if not image_url:
                missing_img.append(cat.name)
            MerchTile.objects.update_or_create(
                placement=MerchTile.PLACEMENT_MAIN, title=cat.name,
                defaults={
                    "image_url": image_url or "",
                    "link": f"/products?category={cat.name}",
                    "badge": "", "highlight": False,
                    "order": order, "is_active": True,
                },
            )
            n_tile += 1
        out.append(f"Category tiles: {n_tile}" + (f" ({len(missing_img)} without an image)" if missing_img else ""))

        # ---- Hero slides ---------------------------------------------------
        # Titles are plain category names on real product photography. No
        # discount or offer wording is invented here.
        n_hero = 0
        for order, cat in enumerate(stocked[: opts["hero_count"]]):
            image_url = self._category_image(cat)
            if not image_url:
                continue
            HeroBanner.objects.update_or_create(
                title=cat.name,
                defaults={
                    "image_url": image_url,
                    "link": f"/products?category={cat.name}",
                    "order": order, "is_active": True,
                },
            )
            n_hero += 1
        out.append(f"Hero banners:   {n_hero} (real product photos, neutral captions)")
        out.append("Skipped on purpose: PriceTier + StorefrontPromo (they assert discounts).")

        return out

    def _category_image(self, category):
        """Primary image of the newest product in this category, if any."""
        product = (
            Product.objects.filter(category=category, images__isnull=False)
            .order_by("-created_at")
            .distinct()
            .first()
        )
        if product is None:
            return None
        image = product.images.filter(is_primary=True).first() or product.images.first()
        return image.url if image else None


class _Rollback(Exception):
    """Internal signal used to abort the transaction for --dry-run."""
