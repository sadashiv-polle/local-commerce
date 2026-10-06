// Frappe timestamps are site-local wall times: preserve the supplied date/time.
export function displayTime(value) {
  if (value == null) return ''
  return String(value).replace(/(^|[T\s])(\d{1,2}):(\d{2})(?::\d{2}(?:\.\d+)?)?(?!\d)/g, (match, prefix, hour, minute) => {
    const h = Number(hour)
    if (h > 23 || Number(minute) > 59) return match
    return `${prefix === 'T' ? ' ' : prefix}${h % 12 || 12}:${minute} ${h >= 12 ? 'PM' : 'AM'}`
  })
}
