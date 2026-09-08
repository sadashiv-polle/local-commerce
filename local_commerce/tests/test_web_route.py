import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.website.page_renderers.template_page import TemplatePage


class TestWorkspaceRoute(FrappeTestCase):
    def test_frappe_discovers_workspace_controller(self):
        page = TemplatePage("local-commerce")
        page.set_pymodule()
        self.assertEqual(page.pymodule_name, "local_commerce.www.local_commerce")
        controller = frappe.get_module(page.pymodule_name)
        self.assertTrue(callable(controller.get_context))
        self.assertEqual(controller.no_cache, 1)
