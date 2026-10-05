import unittest
from local_commerce.services.label_access import signature, valid_signature


class LabelAccessTests(unittest.TestCase):
    def test_signature_is_bound_to_order_and_site(self):
        token = signature('site-secret', 'order-a')
        self.assertTrue(valid_signature('site-secret', 'order-a', token))
        self.assertFalse(valid_signature('site-secret', 'order-b', token))
        self.assertFalse(valid_signature('other-site', 'order-a', token))

    def test_missing_and_malformed_tokens_are_denied(self):
        for token in (None, '', 'x' * 64, 'é' * 64):
            self.assertFalse(valid_signature('secret', 'order', token))
        self.assertFalse(valid_signature('', 'order', 'x' * 64))
