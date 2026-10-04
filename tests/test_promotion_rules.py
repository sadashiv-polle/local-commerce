import unittest
from local_commerce.services.promotion_rules import normalize


class PromotionRulesTests(unittest.TestCase):
    def slide(self, **changes):
        return {"title": "Weekend offer", "image": "/files/offer.png", **changes}

    def test_default_disabled(self):
        self.assertEqual(normalize({})["slides"], [])
        self.assertFalse(normalize({})["enabled"])

    def test_preserves_order_and_visibility(self):
        result = normalize({"enabled": 1, "interval": 7, "slides": [
            self.slide(enabled=False), self.slide(title="Second", link="/store/fish")
        ]})
        self.assertFalse(result["slides"][0]["enabled"])
        self.assertEqual(result["slides"][1]["title"], "Second")
        self.assertEqual(result["interval"], 7)

    def test_rejects_private_or_external_art(self):
        for image in ["/private/files/a.png", "https://host/a.png", "/files/../private/a.png"]:
            with self.subTest(image=image), self.assertRaises(ValueError):
                normalize({"slides": [self.slide(image=image)]})

    def test_rejects_unsafe_links(self):
        for link in ["javascript:alert(1)", "//host", "https://host", "/store/\\host"]:
            with self.subTest(link=link), self.assertRaises(ValueError):
                normalize({"slides": [self.slide(link=link)]})

    def test_limits(self):
        for config in [{"interval": 0}, {"interval": 31}, {"interval": "invalid"},
                       {"slides": [self.slide()] * 13}, {"slides": [self.slide(title="")]}]:
            with self.subTest(config=config), self.assertRaises(ValueError):
                normalize(config)
