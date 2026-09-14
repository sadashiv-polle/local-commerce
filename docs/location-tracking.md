# Shop locations, delivery pins, and rider tracking

Platform administrators configure the shop street address, map pin, delivery radius, and live
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

After pickup, the app requests a driving route from OSRM and draws it from the
shop to the customer. Route responses are cached for one day. A deployment can
replace the default OSRM demo endpoint with a compatible service:

```json
{
  "lc_routing_url": "https://routing.example.com/route/v1/driving"
}
```

The default demo endpoint is suitable for light testing and early use. Use a
hosted or self-hosted routing service before traffic becomes significant.

When an assigned rider taps **Start delivery**, the browser requests precise GPS
permission and starts sharing automatically. The rider sends an update every 12
seconds while the delivery page remains open. The active order is remembered on
that device, so reloading the delivery page resumes sharing automatically. It is
forgotten only when the rider stops sharing or completes the delivery. The server
accepts an update at most once every ten seconds and sends it only to the order's
customer realtime channel. The customer order page also refreshes every ten
seconds while delivery is active. Precise rider coordinates are cleared as soon
as delivery is completed.

Browser geolocation requires HTTPS (localhost is the usual development exception).
Manual map pin selection remains available when geolocation is unavailable. Before
testing device GPS, deploy the site behind a valid HTTPS domain and allow location
access in the rider/customer browser.

The displayed duration is a routing estimate without live traffic. Browser
tracking pauses when the operating system suspends the page and stops when the
rider closes it; a native mobile app is required for dependable background GPS.
