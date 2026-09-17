import json
import unittest

from local_commerce.services.shop_map import geojson, pin, synchronize


class Doc(dict):
    def __init__(self, previous=None, **values):
        super().__init__(values)
        self.previous = previous

    def get_doc_before_save(self):
        return self.previous

    def __setattr__(self, key, value):
        if key == 'previous':
            super().__setattr__(key, value)
        else:
            self[key] = value


class TestShopMap(unittest.TestCase):
    def test_geojson_uses_longitude_first_and_rounds_coordinates(self):
        self.assertEqual(pin(geojson(15.4967614, 73.8354364)),
                         {'latitude': 15.496761, 'longitude': 73.835436})

    def test_marking_pin_updates_shared_coordinates(self):
        doc = Doc(previous={'location_map': ''}, latitude=0, longitude=0,
                  location_map=geojson(15.5, 73.8))
        synchronize(doc)
        self.assertEqual((doc['latitude'], doc['longitude']), (15.5, 73.8))

    def test_app_coordinate_change_updates_desk_map(self):
        old = geojson(15.5, 73.8)
        doc = Doc(previous={'location_map': old}, location_map=old,
                  latitude=16, longitude=74)
        synchronize(doc)
        self.assertEqual(pin(doc['location_map']), {'latitude': 16.0, 'longitude': 74.0})

    def test_deleted_pin_clears_coordinates(self):
        doc = Doc(previous={'location_map': geojson(15, 73)},
                  location_map='{"type":"FeatureCollection","features":[]}',
                  latitude=15, longitude=73)
        synchronize(doc)
        self.assertIsNone(doc['latitude'])
        self.assertIsNone(doc['longitude'])
        self.assertEqual(doc['location_map'], '')

    def test_rejects_shapes_multiple_pins_and_invalid_coordinates(self):
        valid = json.loads(geojson(15, 73))
        for value in ['invalid', '[]', json.dumps({**valid, 'features': valid['features'] * 2}),
                      json.dumps({'type': 'FeatureCollection', 'features': [{
                          'geometry': {'type': 'Polygon', 'coordinates': []}}]}),
                      json.dumps({'type': 'FeatureCollection', 'features': [{
                          'geometry': {'type': 'Point', 'coordinates': [73, 91]}}]})]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                pin(value)
