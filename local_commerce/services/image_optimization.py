"""Bound new product artwork to a useful display size, stripping metadata."""
from io import BytesIO
from PIL import Image, ImageOps


def optimize(content):
    with Image.open(BytesIO(content)) as source:
        if source.format not in {"JPEG", "PNG", "WEBP"}:
            raise ValueError("Upload a JPG, PNG or WebP image")
        image = ImageOps.exif_transpose(source)
        image.thumbnail((1400, 1400), Image.Resampling.LANCZOS)
        image = image.convert("RGBA" if "A" in image.getbands() or "transparency" in image.info else "RGB")
        output = BytesIO()
        image.save(output, format="WEBP", quality=82, method=4)
        return output.getvalue()
