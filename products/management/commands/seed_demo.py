from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from allauth.account.models import EmailAddress

from products.models import (
    HeroBanner,
    HomeSection,
    MerchTile,
    NavLink,
    PriceTier,
    Product,
    ProductCategory,
    StorefrontPromo,
)

User = get_user_model()


class Command(BaseCommand):
    help = "Create demo seller, categories, products, and promos for local development."

    def handle(self, *args, **options):
        seller, created = User.objects.get_or_create(
            username="seller@tamaade.local",
            defaults={
                "email": "seller@tamaade.local",
                "first_name": "Tamaade",
                "last_name": "Seller",
                "is_active": True,
            },
        )
        if created or not seller.has_usable_password():
            seller.set_password("SellerPass123!")
            seller.save()

        EmailAddress.objects.update_or_create(
            user=seller,
            email=seller.email,
            defaults={"verified": True, "primary": True},
        )

        buyer, buyer_created = User.objects.get_or_create(
            username="buyer@tamaade.local",
            defaults={
                "email": "buyer@tamaade.local",
                "first_name": "Ama",
                "last_name": "Buyer",
                "is_active": True,
            },
        )
        if buyer_created or not buyer.has_usable_password():
            buyer.set_password("BuyerPass123!")
            buyer.save()
        EmailAddress.objects.update_or_create(
            user=buyer,
            email=buyer.email,
            defaults={"verified": True, "primary": True},
        )

        sale_ends_at = timezone.now() + timedelta(days=5)
        catalog = {
            "Electronics": [
                {
                    "name": "Wireless Headphones",
                    "desc": "Over-ear bluetooth headphones.",
                    "price": "89.99",
                    "compare_at_price": "179.99",
                    "quantity": 25,
                    "promo_label": "UP TO 50% OFF",
                    "brand": "Tamaade Audio",
                    "is_new": True,
                    "is_express": True,
                    "sale_ends_at": sale_ends_at,
                },
                {
                    "name": "USB-C Charger",
                    "desc": "30W fast wall charger.",
                    "price": "24.50",
                    "compare_at_price": "35.00",
                    "quantity": 40,
                    "promo_label": "FLASH DEAL",
                    "brand": "Tamaade Power",
                    "is_new": False,
                    "is_express": True,
                    "sale_ends_at": sale_ends_at,
                },
            ],
            "Home & Kitchen": [
                {
                    "name": "Blender Set",
                    "desc": "Kitchen blender with extra jars.",
                    "price": "59.00",
                    "compare_at_price": "99.00",
                    "quantity": 18,
                    "promo_label": "UP TO 40% OFF",
                    "brand": "Tamaade Home",
                    "is_new": False,
                    "is_express": True,
                    "sale_ends_at": sale_ends_at,
                },
                {
                    "name": "Non-stick Pan",
                    "desc": "28cm frying pan.",
                    "price": "32.00",
                    "compare_at_price": None,
                    "quantity": 30,
                    "promo_label": "",
                    "brand": "Tamaade Cook",
                    "is_new": False,
                    "is_express": False,
                    "sale_ends_at": None,
                },
            ],
            "Personal Care": [
                {
                    "name": "Massage Gun",
                    "desc": "Handheld percussion massager.",
                    "price": "75.00",
                    "compare_at_price": "150.00",
                    "quantity": 12,
                    "promo_label": "UP TO 50% OFF",
                    "brand": "Tamaade Care",
                    "is_new": True,
                    "is_express": True,
                    "sale_ends_at": sale_ends_at,
                },
            ],
            "Shoes": [
                {
                    "name": "City Sneakers",
                    "desc": "Everyday sneakers.",
                    "price": "45.00",
                    "compare_at_price": "90.00",
                    "quantity": 20,
                    "promo_label": "UP TO 50% OFF",
                    "brand": "Tamaade Wear",
                    "is_new": False,
                    "is_express": True,
                    "sale_ends_at": sale_ends_at,
                },
            ],
        }

        created_count = 0
        for category_name, items in catalog.items():
            category, _ = ProductCategory.objects.get_or_create(name=category_name)
            for item in items:
                product, was_created = Product.objects.get_or_create(
                    seller=seller,
                    name=item["name"],
                    defaults={
                        "category": category,
                        "desc": item["desc"],
                        "price": item["price"],
                        "quantity": item["quantity"],
                    },
                )
                product.category = category
                product.desc = item["desc"]
                product.price = Decimal(item["price"])
                product.compare_at_price = (
                    Decimal(item["compare_at_price"]) if item["compare_at_price"] else None
                )
                product.quantity = item["quantity"]
                product.promo_label = item["promo_label"]
                product.brand = item["brand"]
                product.is_new = item["is_new"]
                product.is_express = item["is_express"]
                product.sale_ends_at = item["sale_ends_at"]
                product.save()
                if was_created:
                    created_count += 1

        banners = [
            {
                "title": "4 Years Anniversary — Up to 70% OFF",
                "link": "/deals",
                "order": 0,
                "image_url": "",
                "local_file": "anniversary.jpg",
            },
            {
                "title": "Back To School — Explore the collection",
                "link": "/products?category=Back%20To%20School",
                "order": 1,
                "image_url": (
                    "https://images.unsplash.com/photo-1588776814546-1ffcf47267a5"
                    "?w=1400&h=400&fit=crop"
                ),
                "local_file": None,
            },
            {
                "title": "Hot Arrivals — Shop now",
                "link": "/products?ordering=-created_at",
                "order": 2,
                "image_url": (
                    "https://images.unsplash.com/photo-1607082348824-0a960f2a4b9d"
                    "?w=1400&h=400&fit=crop"
                ),
                "local_file": None,
            },
        ]
        anniversary = (
            Path(__file__).resolve().parents[4]
            / "TamaadeWeb"
            / "public"
            / "hero"
            / "anniversary.jpg"
        )
        banner_count = 0
        for item in banners:
            banner, was_created = HeroBanner.objects.get_or_create(
                title=item["title"],
                defaults={
                    "link": item["link"],
                    "order": item["order"],
                    "image_url": item["image_url"],
                    "is_active": True,
                },
            )
            if item["local_file"] and not banner.image and anniversary.exists():
                with anniversary.open("rb") as fh:
                    banner.image.save(item["local_file"], File(fh), save=True)
            if was_created:
                banner_count += 1

        for order, amount in enumerate([50, 100, 150, 200, 250]):
            PriceTier.objects.get_or_create(
                amount=amount,
                defaults={"order": order, "is_active": True},
            )

        promos = [
            {
                "key": "top_strip",
                "title": "Refresh Your Wardrobe.",
                "highlight": "35%–50% OFF",
                "cta_label": "shop now",
                "link": "/deals",
                "subtitle": "",
                "order": 0,
            },
            {
                "key": "deals_header",
                "title": "4th Anniversary!",
                "subtitle": "Up to 70% OFF — Limited time deals",
                "highlight": "",
                "cta_label": "SHOP NOW",
                "link": "/products",
                "order": 1,
            },
        ]
        promo_count = 0
        for item in promos:
            _, was_created = StorefrontPromo.objects.update_or_create(
                key=item["key"],
                defaults={
                    "title": item["title"],
                    "subtitle": item["subtitle"],
                    "highlight": item["highlight"],
                    "cta_label": item["cta_label"],
                    "link": item["link"],
                    "order": item["order"],
                    "is_active": True,
                },
            )
            if was_created:
                promo_count += 1

        def tile_image(seed):
            return f"https://picsum.photos/seed/{seed}/200/200"

        main_tiles = [
            ("4th Anniversary!", "/deals", "Up to 70% OFF", True, ""),
            ("Appliances", "/products?category=Appliances", "", False, "appliances"),
            ("Decor", "/products?category=Decor", "", False, "decor"),
            ("Personal Care", "/products?category=Personal%20Care", "", False, "personal-care"),
            ("Kitchen & Dining", "/products?category=Kitchen%20%26%20Dining", "", False, "kitchen-dining"),
            ("Lighting", "/products?category=Lighting", "", False, "lighting"),
            ("Shavers", "/products?category=Shavers", "", False, "shavers"),
            ("Housekeeping", "/products?category=Housekeeping", "", False, "housekeeping"),
            ("Kitchen & Bath Fixtures", "/products?category=Kitchen%20%26%20Bath", "", False, "kitchen-bath"),
            ("Back To School!", "/products?category=Back%20To%20School", "70%", False, "school"),
            ("Fitness", "/products?category=Fitness", "", False, "fitness"),
            ("Electronics", "/products?category=Electronics", "70%", False, "electronics"),
            ("Automotive", "/products?category=Automotive", "", False, "automotive"),
            ("Home Furniture", "/products?category=Home%20Furniture", "", False, "furniture"),
            ("Storage & Organization", "/products?category=Storage", "", False, "storage"),
            ("Luggage", "/products?category=Luggage", "", False, "luggage"),
            ("Cooling", "/products?category=Cooling", "", False, "cooling"),
            ("Shoes", "/products?category=Shoes", "70%", False, "shoes"),
            ("Shop By Bundles", "/deals", "", False, "bundles"),
            ("Tools", "/products?category=Tools", "", False, "tools"),
            ("Baby & Toys", "/products?category=Baby%20%26%20Toys", "", False, "baby"),
            ("Camping & Outdoor", "/products?category=Camping", "", False, "camping"),
            ("Bath", "/products?category=Bath", "", False, "bath"),
            ("Patio & Garden", "/products?category=Patio%20%26%20Garden", "", False, "garden"),
            ("Cameras", "/products?category=Cameras", "", False, "cameras"),
            ("Shoe Organizer", "/products?category=Shoe%20Organizer", "", False, "shoe-org"),
            ("Top Brands", "/products?filter=top-brands", "", False, "brands"),
        ]
        merch_count = 0
        for order, (title, link, badge, highlight, seed) in enumerate(main_tiles):
            _, was_created = MerchTile.objects.get_or_create(
                placement=MerchTile.PLACEMENT_MAIN,
                title=title,
                defaults={
                    "link": link,
                    "badge": badge,
                    "highlight": highlight,
                    "image_url": "" if highlight else tile_image(seed or title),
                    "order": order,
                    "is_active": True,
                },
            )
            if was_created:
                merch_count += 1

        featured_tiles = [
            ("Shoes", "/products?category=Shoes", "feat-shoes"),
            ("Clothing", "/products?category=Clothing", "feat-clothing"),
            ("Bags", "/products?category=Bags", "feat-bags"),
            ("Watches", "/products?category=Watches", "feat-watches"),
            ("Accessories", "/products?category=Accessories", "feat-accessories"),
        ]
        for order, (title, link, seed) in enumerate(featured_tiles):
            _, was_created = MerchTile.objects.get_or_create(
                placement=MerchTile.PLACEMENT_FEATURED,
                title=title,
                defaults={
                    "link": link,
                    "image_url": tile_image(seed),
                    "order": order,
                    "is_active": True,
                },
            )
            if was_created:
                merch_count += 1

        bottom_tiles = [
            "Coffee & More",
            "Air Quality",
            "Kitchen Storage",
            "Decorative Accessories",
            "Drinkware",
            "Rugs & Carpets",
            "Cookware",
            "Inflatable Furniture",
            "Clocks",
            "Vacuums & Floor Care",
            "Wall Decor",
            "Kitchen Gadgets",
            "Shoes Organizer",
            "Living Room Furniture",
            "Blenders",
            "Bathroom Storage",
            "Irons & Steamers",
            "Dinnerware",
        ]
        for order, title in enumerate(bottom_tiles):
            _, was_created = MerchTile.objects.get_or_create(
                placement=MerchTile.PLACEMENT_BOTTOM,
                title=title,
                defaults={
                    "link": f"/products?category={title.replace(' ', '%20')}",
                    "image_url": tile_image(f"bottom-{order}"),
                    "order": order,
                    "is_active": True,
                },
            )
            if was_created:
                merch_count += 1

        home_sections = [
            ("home", "hot-arrivals", "Hot Arrivals!", "Don't Miss What Just Arrived!", "newest", "/products?ordering=-created_at", 0),
            ("home", "top-picks", "Our Top Picks", "Tried, loved, and highly rated", "featured", "/products?filter=top-picks", 1),
            ("home", "hot-sellers", "Hot Sellers", "The items everyone's buying", "bestsellers", "/products?filter=top-selling", 2),
            ("deals", "anniversary-deals", "Anniversary Deals", "Celebrate 4 Years of Savings!", "newest", "/products", 0),
            ("deals", "bundles", "Shop By Bundles", "Save more when you buy together", "featured", "/products?filter=bundles", 1),
        ]
        section_count = 0
        for location, key, title, subtitle, source, link, order in home_sections:
            _, was_created = HomeSection.objects.update_or_create(
                location=location,
                key=key,
                defaults={
                    "title": title,
                    "subtitle": subtitle,
                    "cta_label": "View More",
                    "link": link,
                    "product_source": source,
                    "order": order,
                    "is_active": True,
                },
            )
            if was_created:
                section_count += 1

        nav_items = [
            ("Home & Kitchen", "/products?category=Home%20%26%20Kitchen", True),
            ("Tools & Improvement", "/products?category=Tools", True),
            ("Electronics", "/products?category=Electronics", True),
            ("Storage & Organization", "/products?category=Storage", True),
            ("New Arrivals", "/products?ordering=-created_at", False),
            ("Back To Stock", "/products?filter=back-to-stock", False),
            ("Top Selling", "/products?filter=top-selling", False),
        ]
        nav_count = 0
        for order, (label, link, has_dropdown) in enumerate(nav_items):
            _, was_created = NavLink.objects.get_or_create(
                label=label,
                defaults={
                    "link": link,
                    "has_dropdown": has_dropdown,
                    "order": order,
                    "is_active": True,
                },
            )
            if was_created:
                nav_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed complete. New products: {created_count}. "
                f"New banners: {banner_count}. New promos: {promo_count}. "
                f"New merch tiles: {merch_count}. New sections: {section_count}. "
                f"New nav links: {nav_count}. "
                "Login buyer@tamaade.local / BuyerPass123!"
            )
        )
