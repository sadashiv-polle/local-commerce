"""Public product gallery URLs; private attachments are never published."""

from urllib.parse import urlsplit

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif")


def gallery_urls(main_image, attachments):
    images = []
    for url in [main_image, *attachments]:
        if not url:
            continue
        parts = urlsplit(url)
        if parts.scheme not in ("", "http", "https") or parts.path.startswith("/private/"):
            continue
        if url != main_image and not parts.path.lower().endswith(IMAGE_EXTENSIONS):
            continue
        if url not in images:
            images.append(url)
    return images
