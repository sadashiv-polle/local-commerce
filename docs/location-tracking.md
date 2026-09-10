# Shop locations, delivery pins, and rider tracking

Owners configure the shop street address, map pin, delivery radius, and live
tracking switch in **Shop workspace → Shop settings**. Customers choose their
delivery pin during checkout. When a shop has a pin, checkout calculates a
straight-line distance on the server and rejects destinations beyond that shop's
configured radius. Postal-code serviceability is still checked separately.

The default map uses OpenStreetMap tiles through Leaflet. A deployment can set
these keys in the site's `site_config.json` to use another compatible tile
provider:

```json
{
  "lc_map_tile_url": "https://tiles.example.com/{z}/{x}/{y}.png",
  "lc_map_attribution": "© Example Maps",
  "lc_map_attribution_url": "https://example.com/maps/terms"
}
```

Tile and attribution URLs must use HTTPS. Provider credentials, quotas, and
production tile-service terms remain the deployer's responsibility. Never put a
secret provider key in the browser tile URL.

An assigned rider can start sharing after an order reaches **Out for Delivery**.
The server accepts an update at most once every five seconds and sends it only to
the order's customer realtime channel. The customer order page also refreshes
every ten seconds while delivery is active. Precise rider coordinates are cleared
as soon as the delivery is completed.

Browser geolocation requires HTTPS (localhost is the usual development exception).
Manual map pin selection remains available when geolocation is unavailable. Before
testing device GPS, deploy the site behind a valid HTTPS domain and allow location
access in the rider/customer browser.

This milestone does not calculate road routes, traffic-aware ETAs, delivery
batches, or background tracking after the rider closes the page. Distance is the
great-circle distance between shop and customer pins.
