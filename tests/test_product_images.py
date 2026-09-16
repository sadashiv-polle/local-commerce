import unittest

from local_commerce.services.product_images import gallery_urls


class ProductImageTests(unittest.TestCase):
    def test_main_photo_first_and_duplicates_removed(self):
        self.assertEqual(
            gallery_urls("/files/fish.jpg", ["/files/fish.jpg", "/files/fish-side.PNG"]),
            ["/files/fish.jpg", "/files/fish-side.PNG"],
        )

    def test_private_files_and_non_images_are_excluded(self):
        self.assertEqual(
            gallery_urls(
                "/private/files/main.jpg",
                [
                    "/private/files/a.jpg",
                    "/files/a.pdf",
                    "javascript:alert(1)",
                    "/files/public.webp",
                ],
            ),
            ["/files/public.webp"],
        )

    def test_attachment_can_supply_missing_main_photo(self):
        self.assertEqual(gallery_urls(None, ["/files/a.jpg"]), ["/files/a.jpg"])
