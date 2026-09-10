const prefix = 'lc-cart-v1:'
export function readCart(storage, shop) {
  const data = JSON.parse(storage.getItem(prefix + shop) || '{}')
  if (!data || Array.isArray(data) || typeof data !== 'object') return {}
  return Object.fromEntries(Object.entries(data).filter(([key, row]) =>
    row && row.item === key && typeof row.item_name === 'string' &&
    Number.isFinite(Number(row.quantity)) && Number(row.quantity) > 0 &&
    Number.isFinite(Number(row.rate)) && Number(row.rate) >= 0
  ).slice(0, 30))
}
export function writeCart(storage, shop, cart) { storage.setItem(prefix + shop, JSON.stringify(cart)) }
export function clearCart(storage, shop) { storage.removeItem(prefix + shop) }
export function changeQuantity(cart, item, delta) {
  const current = Number(cart[item.item]?.quantity || 0)
  const next = current + Number(delta)
  if (!Number.isFinite(next) || !Number.isFinite(Number(delta)) || !delta) throw new Error('Invalid quantity change')
  const updated = { ...cart }
  if (next <= 0) {
    delete updated[item.item]
    return updated
  }
  if (item.rate == null || next > Number(item.available)) throw new Error('Quantity exceeds available stock')
  updated[item.item] = { ...item, quantity: next }
  return updated
}
export function loginUrl(path = '/store') {
  const safe = typeof path === 'string' && path.startsWith('/') && !path.startsWith('//') ? path : '/store'
  return '/local-commerce#/login?next=' + encodeURIComponent(safe)
}
