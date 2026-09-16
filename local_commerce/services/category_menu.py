"""Admin-owned category presentation; items retain ERPNext's taxonomy."""

import frappe

from local_commerce.permissions.scope import require_platform
from local_commerce.services.item_groups import COMMERCE_ITEM_GROUPS
from local_commerce.services.owner import reject
from local_commerce.services.product_images import gallery_urls


def seed_menu():
    doc = frappe.get_single("LC Store Settings")
    if doc.category_menu_initialized:
        return
    if not doc.categories:
        doc.set("categories", [
            {"item_group": group, "label": group, "enabled": 1,
             "section": "Snacks & meals" if group in {"Fast Food", "Snacks", "Beverages"}
             else "Everyday essentials"}
            for group in COMMERCE_ITEM_GROUPS
        ])
    doc.category_menu_enabled = 1
    doc.category_menu_initialized = 1
    # Seed only once, preserving later choices including an empty menu.
    doc.save(ignore_permissions=True)


def validate_menu(doc):
    if len(doc.categories) > 40:
        reject("Choose up to 40 menu categories")
    groups = set()
    for row in doc.categories:
        if row.item_group in groups:
            reject("Each Item Group can appear once in the menu")
        groups.add(row.item_group)
        if not frappe.db.exists("Item Group", row.item_group):
            reject("Select an existing Item Group")
        row.label = str(row.label or row.item_group).strip()[:60]
        row.section = str(row.section or "Shop by category").strip()[:60]
        if row.image and not gallery_urls(row.image, []):
            reject("Use a public category image")


def menu(admin=False):
    if admin:
        require_platform()
    doc = frappe.get_single("LC Store Settings")
    rows = []
    for row in doc.categories:
        if not admin and (not doc.category_menu_enabled or not row.enabled):
            continue
        images = gallery_urls(row.image, [])
        if not images:
            # Reuse public product artwork until the admin supplies category artwork.
            image = frappe.db.sql(
                """select i.image from `tabItem` i
                inner join `tabLC Shop` s on s.name=i.lc_shop
                where i.item_group=%s and i.disabled=0 and s.status='Active'
                and coalesce(i.image, '')!='' and i.image not like '/private/%%'
                order by i.modified desc limit 1""", (row.item_group,), pluck=True,
            )
            images = gallery_urls(image[0] if image else "", [])
        rows.append({"item_group": row.item_group, "label": row.label,
                     "section": row.section, "image": images[0] if images else "",
                     "enabled": bool(row.enabled)})
    return {"enabled": bool(doc.category_menu_enabled), "categories": rows,
            **({"groups": frappe.get_all("Item Group", pluck="name",
                                         order_by="name", limit_page_length=500)} if admin else {})}


def save_menu(enabled, categories):
    require_platform()
    rows = frappe.parse_json(categories) if isinstance(categories, str) else categories
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        reject("Choose a list of categories")
    doc = frappe.get_single("LC Store Settings")
    doc.category_menu_enabled = enabled in (True, 1, "1")
    doc.category_menu_initialized = 1
    doc.set("categories", [{key: row.get(key) for key in
                            ("item_group", "label", "section", "image", "enabled")}
                           for row in rows])
    doc.save()
    return menu(admin=True)


def upload_image():
    require_platform()
    uploaded = getattr(frappe.request, "files", {}).get("file")
    if not uploaded or not uploaded.filename:
        reject("Choose a category image")
    content = uploaded.stream.read(5 * 1024 * 1024 + 1)
    if not content or len(content) > 5 * 1024 * 1024:
        reject("Choose an image smaller than 5 MB")
    from io import BytesIO

    from frappe.utils.file_manager import save_file
    from PIL import Image

    try:
        with Image.open(BytesIO(content)) as image:
            if image.format not in {"JPEG", "PNG", "WEBP"}:
                reject("Upload a JPG, PNG or WebP image")
            extension = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}[image.format]
            image.verify()
    except (OSError, ValueError, Image.DecompressionBombError):
        reject("Choose a valid JPG, PNG or WebP image")
    file = save_file(f"category-{frappe.generate_hash(length=12)}.{extension}", content,
                     "LC Store Settings", "LC Store Settings", is_private=0)
    return {"image": file.file_url}
