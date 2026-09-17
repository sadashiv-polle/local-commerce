export function displayPrice(product) {
  const offers = (product.selling_options || []).filter(row => row.enabled !== false)
  if (!offers.length) return { rate: product.rate, unit: product.uom, from: false }
  const prices = offers.map(row => row.billing === 'Pieces'
    ? Number(row.piece_price) * Number(row.quantity)
    : product.rate == null ? null : Number(product.rate) * Number(row.estimated_weight))
    .filter(value => value != null && Number.isFinite(value))
  return { rate: prices.length ? Math.min(...prices) : null, unit: 'Choose option', from: true }
}
