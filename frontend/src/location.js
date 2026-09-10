export function distanceKm(origin, destination) {
  const raw = [origin?.latitude, origin?.longitude, destination?.latitude, destination?.longitude]
  if (raw.some(value => value == null || String(value).trim() === '')) return null
  const values = raw.map(Number)
  if (!values.every(Number.isFinite)) return null
  const [lat1, lon1, lat2, lon2] = values.map(value => value * Math.PI / 180)
  const latitudeDelta = lat2 - lat1, longitudeDelta = lon2 - lon1
  const haversine = Math.sin(latitudeDelta / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(longitudeDelta / 2) ** 2
  return 6371.0088 * 2 * Math.atan2(Math.sqrt(Math.min(1, Math.max(0, haversine))), Math.sqrt(1 - Math.min(1, Math.max(0, haversine))))
}
