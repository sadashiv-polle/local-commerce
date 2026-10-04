"""Validation shared by the admin API and settings document."""
from urllib.parse import urlsplit


def normalize(config):
    if not isinstance(config, dict):
        raise ValueError("Choose valid slider settings")
    try:
        interval = int(config.get("interval", 5))
    except (TypeError, ValueError):
        raise ValueError("Choose a slide interval from 3 to 30 seconds") from None
    if not 3 <= interval <= 30:
        raise ValueError("Choose a slide interval from 3 to 30 seconds")
    slides = config.get("slides", [])
    if not isinstance(slides, list) or len(slides) > 12:
        raise ValueError("Add up to 12 promotional slides")
    result = []
    for row in slides:
        if not isinstance(row, dict):
            raise ValueError("Choose valid promotional slides")
        title = str(row.get("title") or "").strip()
        image = str(row.get("image") or "").strip()
        link = str(row.get("link") or "").strip()
        # Only public uploaded artwork and internal app routes are allowed.
        if not title or len(title) > 80:
            raise ValueError("Give each slide a title of up to 80 characters")
        if not image.startswith("/files/") or any(c in image for c in ('\\', '?', '#')) or '..' in image or urlsplit(image).netloc:
            raise ValueError("Upload a public slide image before saving")
        if link and (not link.startswith(("/store/", "/store?", "/categories")) or any(c in link for c in ('\\', '\n', '\r'))):
            raise ValueError("Use a shop or category link inside the app, starting with /store/ or /categories")
        result.append({"title": title, "image": image, "link": link[:300],
                       "enabled": row.get("enabled", True) in (True, 1, "1")})
    return {"enabled": config.get("enabled", False) in (True, 1, "1"),
            "autoplay": config.get("autoplay", True) in (True, 1, "1"),
            "interval": interval, "slides": result}
