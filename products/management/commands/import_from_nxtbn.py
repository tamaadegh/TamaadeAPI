"""Import the catalog exported from the legacy nxtbn database.

The old deployment ran nxtbn, whose schema is unrelated to this project's
(`product_product` + `product_productvariant` + `filemanager_image` vs.
`products_product` + `products_productimage`). The two databases cannot be
shared, so the catalog is carried over field by field.

Source data is the JSON produced by the companion `extract.sql`, not a live
connection, so this command needs no access to the nxtbn container.

Image files themselves are never copied: they live in Cloudinary and are
referenced by URL, so only the URL is rebuilt here.
"""

import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.dateparse import parse_datetime

from products.models import Product, ProductCategory, ProductImage

User = get_user_model()


class Command(BaseCommand):
    help = "Import users, categories, products and image URLs exported from the legacy nxtbn database."

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True, help="Path to nxtbn_export.json")
        parser.add_argument(
            "--cloud-name",
            default="dkgvvyzxe",
            help="Cloudinary cloud name that hosts the legacy image files.",
        )
        parser.add_argument(
            "--default-quantity",
            type=int,
            default=100,
            help=(
                "Stock to give products nxtbn did not track inventory for. nxtbn treated "
                "track_inventory=false as always-available, but this schema only has an "
                "integer quantity, and quantity<=0 renders as out of stock."
            ),
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Delete existing products/categories/images first, then re-import.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change and roll back.",
        )

    def handle(self, *args, **opts):
        with open(opts["file"]) as fh:
            data = json.load(fh)

        for key in ("users", "categories", "products", "images"):
            if key not in data:
                raise CommandError(f"Export is missing the '{key}' section.")

        # Product names are not unique in the source (4 names appear twice), and this
        # schema has no field to hold the nxtbn id, so there is no key to match an
        # existing row on. Import therefore only runs into an empty catalog.
        existing = Product.objects.count()
        if existing and not opts["force"]:
            raise CommandError(
                f"{existing} products already exist. Re-importing would duplicate them. "
                "Pass --force to delete the current catalog and re-import."
            )

        try:
            with transaction.atomic():
                stats = self._run(data, opts)
                if opts["dry_run"]:
                    raise _Rollback()
        except _Rollback:
            self.stdout.write(self.style.WARNING("\nDRY RUN - rolled back, nothing written."))

        for line in stats:
            self.stdout.write(line)

    def _run(self, data, opts):
        out = []

        if opts["force"]:
            ProductImage.objects.all().delete()
            Product.objects.all().delete()
            ProductCategory.objects.all().delete()
            out.append(self.style.WARNING("--force: cleared existing catalog."))

        # ---- Users -------------------------------------------------------
        # Password hashes are copied verbatim (both are Django PBKDF2), so the
        # staff keep the exact credentials they had on nxtbn.
        users_by_email = {}
        created_u = updated_u = 0
        for row in data["users"]:
            user, created = User.objects.get_or_create(
                email=row["email"],
                defaults={"username": row["username"]},
            )
            user.username = row["username"]
            user.password = row["password"]  # already-hashed, do NOT set_password
            user.first_name = row.get("first_name") or ""
            user.last_name = row.get("last_name") or ""
            user.is_staff = bool(row["is_staff"])
            user.is_superuser = bool(row["is_superuser"])
            user.is_active = bool(row["is_active"])
            if row.get("date_joined"):
                user.date_joined = parse_datetime(row["date_joined"])
            user.save()
            users_by_email[row["email"]] = user
            created_u += int(created)
            updated_u += int(not created)

            # allauth requires a verified address for the JWT login endpoint
            # (ACCOUNT_EMAIL_VERIFICATION is mandatory); admin/session login
            # does not, but making them consistent avoids a surprise later.
            try:
                from allauth.account.models import EmailAddress

                EmailAddress.objects.update_or_create(
                    user=user,
                    email=row["email"],
                    defaults={"verified": True, "primary": True},
                )
            except Exception as exc:  # pragma: no cover
                out.append(self.style.WARNING(f"  EmailAddress for {row['email']}: {exc}"))

        out.append(f"Users:      {created_u} created, {updated_u} updated")

        # ---- Categories --------------------------------------------------
        # nxtbn categories are a tree; this schema is flat. Only one source
        # category has a parent and it holds no products, so flattening is
        # effectively lossless.
        cat_by_src_id = {}
        created_c = 0
        for row in data["categories"]:
            cat, created = ProductCategory.objects.get_or_create(name=row["name"])
            cat_by_src_id[row["id"]] = cat
            created_c += int(created)
        out.append(f"Categories: {created_c} created ({len(data['categories'])} in export)")

        # ---- Products ----------------------------------------------------
        seller = self._pick_seller(users_by_email)
        out.append(f"Seller assigned to imported products: {seller.email}")

        images_by_product = {}
        for row in data["images"]:
            images_by_product.setdefault(row["product_id"], []).append(row)

        base = f"https://res.cloudinary.com/{opts['cloud_name']}/image/upload/"
        created_p = created_i = 0
        no_stock = []

        for row in data["products"]:
            category = cat_by_src_id.get(row["category_id"])
            if category is None:
                raise CommandError(f"Product {row['id']} references unknown category {row['category_id']}")

            tracked = bool(row.get("track_inventory"))
            quantity = 0 if tracked else opts["default_quantity"]
            if tracked:
                no_stock.append(row["name"])

            product = Product(
                seller=seller,
                category=category,
                name=row["name"],
                desc=row.get("description") or row.get("summary") or "",
                price=Decimal(str(row["price"])) if row.get("price") is not None else Decimal("0"),
                compare_at_price=(
                    Decimal(str(row["compare_at_price"]))
                    if row.get("compare_at_price") is not None
                    else None
                ),
                brand=row.get("brand") or "",
                quantity=quantity,
            )
            product.save()

            # created_at is auto_now_add, so restore the original date afterwards
            # to keep the catalog ordering ("-created_at") the same as nxtbn.
            if row.get("created_at"):
                Product.objects.filter(pk=product.pk).update(
                    created_at=parse_datetime(row["created_at"])
                )

            created_p += 1

            primary_src = row.get("primary_image_id")
            rows = images_by_product.get(row["id"], [])
            matched_primary = any(i["image_id"] == primary_src for i in rows)
            for idx, img in enumerate(rows):
                is_primary = (
                    img["image_id"] == primary_src if matched_primary else idx == 0
                )
                ProductImage.objects.create(
                    product=product,
                    url=base + img["path"].lstrip("/"),
                    is_primary=is_primary,
                    order=idx,
                )
                created_i += 1

        out.append(f"Products:   {created_p} created")
        out.append(f"Images:     {created_i} created (Cloudinary URLs, files not copied)")
        out.append(
            f"Stock:      {opts['default_quantity']} assigned to untracked products; "
            f"{len(no_stock)} kept at 0 because nxtbn tracked them with no stock rows"
        )
        for name in no_stock:
            out.append(f"              out of stock: {name}")

        return out

    def _pick_seller(self, users_by_email):
        """Products need a seller FK; prefer the original nxtbn superuser."""
        for email in ("jun@tamaade.com", "hanson@tamaade.com"):
            if email in users_by_email:
                return users_by_email[email]
        user = User.objects.filter(is_superuser=True).order_by("id").first()
        if user is None:
            raise CommandError("No superuser available to own the imported products.")
        return user


class _Rollback(Exception):
    """Internal signal used to abort the transaction for --dry-run."""
