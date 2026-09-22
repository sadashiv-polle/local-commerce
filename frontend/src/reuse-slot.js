// Shift wall-clock dates without converting the shop's times through the device timezone.
const fields = ['ordering_start', 'ordering_end', 'delivery_start', 'delivery_end']
function day(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) throw new Error('Choose a valid delivery date')
  const parsed = new Date(`${value}T00:00:00Z`)
  if (!Number.isFinite(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== value) throw new Error('Choose a valid delivery date')
  return parsed.getTime()
}
export function reuseSlot(slot, date) {
  const offset = day(date) - day(String(slot.delivery_start).slice(0, 10))
  const result = Object.fromEntries(['title', 'capacity', 'radius_km', 'products', 'postcodes'].map(key => [key, slot[key]]))
  result.enabled = 1
  for (const key of fields) {
    const text = String(slot[key])
    result[key] = new Date(day(text.slice(0, 10)) + offset).toISOString().slice(0, 10) + 'T' + text.slice(11, 16)
  }
  return result
}
export function tomorrowInZone(timezone, now = new Date()) {
  const parts = Object.fromEntries(new Intl.DateTimeFormat('en-US', { timeZone: timezone, year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(now).map(part => [part.type, part.value]))
  return new Date(day(`${parts.year}-${parts.month}-${parts.day}`) + 86400000).toISOString().slice(0, 10)
}
