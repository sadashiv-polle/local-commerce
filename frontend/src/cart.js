const prefix = 'lc-cart-v1:'
const activeKey = 'lc-cart-active-v1'
const metaPrefix = 'lc-cart-meta-v1:'
const cartLifetimeMs = 5 * 60 * 1000
export function cartKey(item) { return item.option_id ? `${item.item}::${item.option_id}` : item.item }
function notifyCart(shop) {
  if (typeof window !== 'undefined' && typeof window.dispatchEvent === 'function') {
    window.dispatchEvent(new CustomEvent('lc-cart-change', { detail: { shop } }))
  }
}
export function readCart(storage, shop) {
  const metaKey = metaPrefix + shop
  const savedAt = Number(storage.getItem(metaKey) || 0)
  if (savedAt && Date.now() - savedAt >= cartLifetimeMs) {
    storage.removeItem(prefix + shop)
    storage.removeItem(metaKey)
    if (storage.getItem(activeKey) === shop) storage.removeItem(activeKey)
    notifyCart(shop)
    return {}
  }
  let data
  try { data = JSON.parse(storage.getItem(prefix + shop) || '{}') } catch { data = {} }
  if (!data || Array.isArray(data) || typeof data !== 'object') return {}
  return Object.fromEntries(Object.entries(data).filter(([key, row]) =>
    row && cartKey(row) === key && typeof row.item_name === 'string' &&
    Number.isFinite(Number(row.quantity)) && Number(row.quantity) > 0 &&
    Number.isFinite(Number(row.rate)) && Number(row.rate) >= 0
  ).slice(0, 30))
}
export function writeCart(storage, shop, cart) {
  if (!Object.keys(cart).length) {
    clearCart(storage, shop)
    return
  }
  storage.setItem(prefix + shop, JSON.stringify(cart))
  storage.setItem(metaPrefix + shop, String(Date.now()))
  storage.setItem(activeKey, shop)
  notifyCart(shop)
}
export function clearCart(storage, shop) {
  storage.removeItem(prefix + shop)
  storage.removeItem(metaPrefix + shop)
  if (storage.getItem(activeKey) === shop) storage.removeItem(activeKey)
  notifyCart(shop)
}
export function clearAllCarts(storage) {
  const keys = []
  for (let index = 0; index < storage.length; index += 1) {
    const key = storage.key(index)
    if (key?.startsWith(prefix) || key?.startsWith(metaPrefix) || key === activeKey) keys.push(key)
  }
  keys.forEach(key => storage.removeItem(key))
  notifyCart(null)
}
export function activeCart(storage) {
  const shop = storage.getItem(activeKey)
  if (!shop) return null
  const cart = readCart(storage, shop)
  return Object.keys(cart).length ? { shop, cart } : null
}
export function changeQuantity(cart, item, delta) {
  if (item.selling_options?.length && !item.option_id) throw new Error('Choose a selling option first')
  const key = cartKey(item)
  const current = Number(cart[key]?.quantity || 0)
  const next = current + Number(delta)
  if (!Number.isFinite(next) || !Number.isFinite(Number(delta)) || !delta) throw new Error('Invalid quantity change')
  const updated = { ...cart }
  if (next <= 0) {
    delete updated[key]
    return updated
  }
  if (item.rate == null || next > Number(item.available)) throw new Error('Quantity exceeds available stock')
  if (item.option_id) {
    if (!Number.isInteger(next) || !Number.isFinite(Number(item.stock_per_pack)) || Number(item.stock_per_pack) <= 0) throw new Error('Invalid pack quantity')
    const otherStock = Object.entries(cart).reduce((total, [lineKey, row]) => total + (lineKey !== key && row.item === item.item ? Number(row.quantity) * Number(row.stock_per_pack || 1) : 0), 0)
    if (next * Number(item.stock_per_pack) + otherStock > Number(item.stock_available) + 1e-9) throw new Error('Quantity exceeds available stock')
  }
  updated[key] = { ...item, quantity: next }
  return updated
}
export function loginUrl(path = '/store') {
  const safe = typeof path === 'string' && path.startsWith('/') && !path.startsWith('//') ? path : '/store'
  return '/local-commerce#/login?next=' + encodeURIComponent(safe)
}
