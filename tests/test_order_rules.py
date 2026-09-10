import unittest

from local_commerce.services.order_rules import (
    address_fields,
    cart_rows,
    delivery_transition,
    transition,
    whole_quantity,
)


class TestOrderRules(unittest.TestCase):
    def test_cart_rejects_duplicates_and_ignores_client_prices(self):
        self.assertEqual(
            cart_rows([{"item": "A", "quantity": 2, "rate": -10}]), [{"item": "A", "quantity": "2"}]
        )
        with self.assertRaises(ValueError):
            cart_rows([{"item": "A", "quantity": 1}, {"item": "A", "quantity": 1}])

    def test_invalid_quantities(self):
        for quantity in [0, -1, "NaN", "Infinity", "0.0000001"]:
            with self.subTest(quantity=quantity), self.assertRaises(ValueError):
                cart_rows([{"item": "A", "quantity": quantity}])

    def test_bounded_cart(self):
        for rows in [[], {}, [{"item": str(i), "quantity": 1} for i in range(31)]]:
            with self.assertRaises(ValueError):
                cart_rows(rows)

    def test_customer_can_only_cancel_unaccepted_request(self):
        self.assertTrue(transition("Requested", "Cancelled", customer=True))
        for current, target in [("Accepted", "Cancelled"), ("Requested", "Accepted")]:
            with self.assertRaises(ValueError):
                transition(current, target, customer=True)

    def test_owner_cannot_skip_or_reopen(self):
        self.assertTrue(transition("Accepted", "Preparing"))
        self.assertFalse(transition("Accepted", "Accepted"))
        for current, target in [
            ("Requested", "Ready"),
            ("Cancelled", "Accepted"),
            ("Ready", "Completed"),
        ]:
            with self.assertRaises(ValueError):
                transition(current, target)

    def test_driver_must_follow_delivery_sequence(self):
        self.assertTrue(delivery_transition("Ready", "Picked Up"))
        self.assertTrue(delivery_transition("Picked Up", "Out for Delivery"))
        self.assertTrue(delivery_transition("Out for Delivery", "Delivered"))
        self.assertFalse(delivery_transition("Delivered", "Delivered"))
        for current, target in [
            ("Ready", "Delivered"),
            ("Picked Up", "Delivered"),
            ("Delivered", "Out for Delivery"),
        ]:
            with self.assertRaises(ValueError):
                delivery_transition(current, target)

    def test_address_normalized_and_required(self):
        address = dict(
            recipient=" Person ",
            phone="1234567890",
            line1="Road",
            city="City",
            postal_code=" ab12 ",
        )
        self.assertEqual(address_fields(address)["postal_code"], "AB12")
        for field in address:
            with self.assertRaises(ValueError):
                address_fields({**address, field: ""})

    def test_whole_units(self):
        whole_quantity("1.5", False)
        with self.assertRaises(ValueError):
            whole_quantity("1.5", True)
