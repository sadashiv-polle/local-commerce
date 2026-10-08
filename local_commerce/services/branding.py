"""Platform-owned browser favicon, stored in the existing storefront settings."""
from io import BytesIO

import frappe
from local_commerce.permissions.scope import require_platform

DEFAULT_FAVICON = "/assets/local_commerce/icons/favicon.svg?v=20261008"


def favicon():
    value = frappe.get_single("LC Store Settings").get("app_favicon") or ""
    return value if value.startswith("/files/") else DEFAULT_FAVICON


def settings():
    require_platform()
    return {"favicon": favicon()}


def upload():
    require_platform()
    from PIL import Image, ImageOps
    from frappe.utils.file_manager import save_file

    file = getattr(frappe.request, "files", {}).get("file")
    if not file:
        frappe.throw("Choose an image for the favicon")
    content = file.stream.read(2 * 1024 * 1024 + 1)
    if not content or len(content) > 2 * 1024 * 1024:
        frappe.throw("Choose an image smaller than 2 MB")
    try:
        with Image.open(BytesIO(content)) as image:
            if image.format not in {"PNG", "JPEG", "WEBP", "ICO"}:
                frappe.throw("Choose a PNG, JPG, WebP or ICO image")
            if image.width * image.height > 16000000:
                frappe.throw("Choose an image no larger than 16 megapixels")
            image = ImageOps.exif_transpose(image).convert("RGBA")
            image.thumbnail((64, 64), Image.Resampling.LANCZOS)
            canvas = Image.new("RGBA", (64, 64))
            canvas.paste(image, ((64 - image.width) // 2, (64 - image.height) // 2))
            output = BytesIO()
            canvas.save(output, format="PNG")
    except (OSError, ValueError, Image.DecompressionBombError):
        frappe.throw("This image could not be read. Choose another image")
    saved = save_file(f"favicon-{frappe.generate_hash(length=12)}.png", output.getvalue(),
                      "LC Store Settings", "LC Store Settings", is_private=0)
    doc = frappe.get_single("LC Store Settings")
    doc.app_favicon = saved.file_url
    doc.save()
    return settings()


def reset():
    require_platform()
    doc = frappe.get_single("LC Store Settings")
    doc.app_favicon = ""
    doc.save()
    return settings()
