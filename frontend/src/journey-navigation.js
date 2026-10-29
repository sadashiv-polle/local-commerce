export function metres(a, b) {
  const radians = Math.PI / 180, lat = (b.latitude - a.latitude) * radians, lon = (b.longitude - a.longitude) * radians
  return 6371000 * 2 * Math.asin(Math.min(1, Math.sqrt(Math.sin(lat / 2) ** 2 + Math.cos(a.latitude * radians) * Math.cos(b.latitude * radians) * Math.sin(lon / 2) ** 2)))
}

export function segmentDistance(location, points) {
  if (!points.length) return Infinity
  let nearest = metres(location, points[0])
  const scale = Math.cos(location.latitude * Math.PI / 180)
  for (let i = 1; i < points.length; i++) {
    const a = points[i - 1], b = points[i]
    const x = (b.longitude - a.longitude) * scale, y = b.latitude - a.latitude
    const length = x * x + y * y
    const t = length ? Math.max(0, Math.min(1, (((location.longitude - a.longitude) * scale) * x + (location.latitude - a.latitude) * y) / length)) : 0
    nearest = Math.min(nearest, metres(location, { latitude: a.latitude + t * y, longitude: a.longitude + t * (b.longitude - a.longitude) }))
  }
  return nearest
}

// Count distinct GPS fixes, never repeated one-second renders of the same fix.
export function createRerouteGuard() {
  let timestamp = null, misses = 0
  return (position, distance, lastRequest, now) => {
    if (position.timestamp !== timestamp) {
      timestamp = position.timestamp
      misses = distance > Math.max(35, position.coords.accuracy * 1.5) ? misses + 1 : 0
    }
    return misses >= 2 && now - lastRequest >= 5000
  }
}

// Prefer GPS course; infer only from distinct fixes with movement beyond GPS noise.
export function travelHeading(previous, current, lastHeading = null) {
  const c = current.coords
  if (Number.isFinite(c.heading) && c.heading >= 0 && c.heading < 360 && (!Number.isFinite(c.speed) || c.speed > 0.5)) return c.heading
  if (!previous || current.timestamp <= previous.timestamp) return lastHeading
  const a = previous.coords, b = c
  const from = { latitude: a.latitude, longitude: a.longitude }
  const to = { latitude: b.latitude, longitude: b.longitude }
  if (metres(from, to) < Math.max(8, a.accuracy || 0, b.accuracy || 0)) return lastHeading
  const rad = Math.PI / 180, delta = (b.longitude - a.longitude) * rad
  return (Math.atan2(Math.sin(delta) * Math.cos(b.latitude * rad), Math.cos(a.latitude * rad) * Math.sin(b.latitude * rad) - Math.sin(a.latitude * rad) * Math.cos(b.latitude * rad) * Math.cos(delta)) / rad + 360) % 360
}

// Relative alpha has no north reference and must never be used as a compass.
export function phoneHeading(event, screenAngle = 0) {
  let heading
  if (Number.isFinite(event.webkitCompassHeading) && event.webkitCompassHeading >= 0) {
    if (Number.isFinite(event.webkitCompassAccuracy) && (event.webkitCompassAccuracy < 0 || event.webkitCompassAccuracy > 50)) return null
    heading = event.webkitCompassHeading
  } else if (event.absolute === true && Number.isFinite(event.alpha)) heading = 360 - event.alpha
  else return null
  return ((heading + (Number.isFinite(screenAngle) ? screenAngle : 0)) % 360 + 360) % 360
}

export function smoothHeading(previous, next) {
  if (!Number.isFinite(previous)) return next
  const delta = ((next - previous + 540) % 360) - 180
  return (previous + delta * 0.3 + 360) % 360
}
