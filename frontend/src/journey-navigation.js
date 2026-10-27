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
