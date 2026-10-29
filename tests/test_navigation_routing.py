"""Exercise routing with provider responses and an isolated cache, without a site."""
import ast
import hashlib
import json
import math
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from urllib.parse import urlencode
from urllib.request import Request
from urllib.error import HTTPError, URLError

from local_commerce.services.location_rules import point


class NavigationRoutingTests(unittest.TestCase):
    def setUp(self):
        self.cache = MagicMock()
        self.cache.get_value.return_value = None
        self.urlopen = MagicMock()
        def reject(message):
            raise ValueError(message)
        self.ns = dict(frappe=SimpleNamespace(cache=self.cache), hashlib=hashlib,
                       json=json, math=math, point=point, urlencode=urlencode,
                       Request=Request, urlopen=self.urlopen, HTTPError=HTTPError,
                       URLError=URLError, LockError=RuntimeError, reject=reject,
                       _endpoint=lambda: 'https://routing.example/route/v1/driving')
        tree = ast.parse(Path('local_commerce/services/routing.py').read_text())
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                     and n.name in ('_coordinates', '_shortest_route', 'road_route')]
        exec(compile(ast.Module(body=functions, type_ignores=[]), 'routing.py', 'exec'), self.ns)
        self.start = dict(latitude=15, longitude=73)
        self.finish = dict(latitude=15.01, longitude=73.01)

    def route(self, distance, duration):
        geometry = dict(coordinates=[[73, 15], [73.01, 15.01]])
        return dict(distance=distance, duration=duration, geometry=geometry,
                    legs=[dict(steps=[dict(name=str(distance), geometry=geometry)])])

    def fetch(self, navigation, start=None):
        self.urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(
            dict(code='Ok', routes=[self.route(3000, 120), self.route(2000, 240)])).encode()
        return self.ns['road_route'](start or self.start, self.finish, navigation)

    def test_navigation_prefers_distance_and_matching_directions(self):
        result = self.fetch(True)
        self.assertEqual(result['distance_km'], 2)
        self.assertEqual(result['steps'][0]['name'], '2000')
        self.assertIn('alternatives=true', self.urlopen.call_args.args[0].full_url)
        self.assertEqual(self.cache.set_value.call_args.kwargs['expires_in_sec'], 60)

    def test_customer_keeps_provider_default_and_cache(self):
        result = self.fetch(False)
        self.assertEqual(result['distance_km'], 3)
        self.assertNotIn('steps', result)
        self.assertNotIn('alternatives=', self.urlopen.call_args.args[0].full_url)
        self.assertEqual(self.cache.set_value.call_args.kwargs['expires_in_sec'], 86400)

    def test_reroute_uses_new_origin_and_cache_key(self):
        self.fetch(True)
        key = self.cache.set_value.call_args.args[0]
        self.fetch(True, dict(latitude=15.002, longitude=73.003))
        self.assertIn('/73.003,15.002;73.01,15.01?', self.urlopen.call_args.args[0].full_url)
        self.assertNotEqual(key, self.cache.set_value.call_args.args[0])

    def test_single_route_ties_and_invalid_metrics(self):
        choose = self.ns['_shortest_route']
        valid = self.route(2000, 120)
        self.assertIs(choose([valid]), valid)
        self.assertIs(choose([self.route(2000, 240), valid]), valid)
        self.assertIs(choose([self.route(float('nan'), 1), self.route(-1, 1), valid]), valid)
        with self.assertRaises(ValueError):
            choose([{}, self.route(float('inf'), 1)])
