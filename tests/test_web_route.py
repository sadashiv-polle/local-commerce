"""Check the controller discovery convention used by Frappe v15 TemplatePage."""

import unittest
from pathlib import Path


class WebRouteTests(unittest.TestCase):
    def test_workspace_has_discoverable_controller(self):
        www = Path(__file__).resolve().parents[1] / "local_commerce/www"
        template = www / "local-commerce.html"
        controller = template.with_name(template.stem.replace("-", "_") + ".py")
        self.assertTrue(template.is_file())
        self.assertTrue(controller.is_file(), f"Frappe cannot discover {controller.name}")
