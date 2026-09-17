"""Convert the single shop pin between Desk GeoJSON and shared coordinates."""

import json

from local_commerce.services.location_rules import point


def pin(value):
    if not value:
        return None
    try:
        data = json.loads(value)
        if data.get('type') != 'FeatureCollection' or not isinstance(data.get('features'), list):
            raise ValueError
        features = data['features']
        if not features:
            return None
        if len(features) != 1:
            raise ValueError
        geometry = features[0]['geometry']
        coordinates = geometry['coordinates']
        if geometry['type'] != 'Point' or len(coordinates) != 2:
            raise ValueError
        return point(coordinates[1], coordinates[0], required=True)
    except (ValueError, TypeError, KeyError, AttributeError, IndexError):
        raise ValueError('Mark exactly one shop pin on the map using the marker tool') from None


def geojson(latitude, longitude):
    location = point(latitude, longitude)
    if location is None:
        return ''
    return json.dumps({'type': 'FeatureCollection', 'features': [
        {'type': 'Feature', 'properties': {}, 'geometry': {
            'type': 'Point', 'coordinates': [location['longitude'], location['latitude']]}}
    ]})


def synchronize(doc):
    previous = doc.get_doc_before_save()
    map_changed = doc.get('location_map') != (previous.get('location_map') if previous else None)
    if map_changed:
        location = pin(doc.get('location_map'))
        doc.latitude = location['latitude'] if location else None
        doc.longitude = location['longitude'] if location else None
    doc.location_map = geojson(doc.get('latitude'), doc.get('longitude'))
