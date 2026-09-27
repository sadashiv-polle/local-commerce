// Keep existing cards and unchanged nested values stable during background polling.
export function reconcileOrders(current, incoming) {
  const existing = new Map(current.map(order => [order.name, order]))
  const next = incoming.map(update => {
    const order = existing.get(update.name)
    if (!order) return update
    for (const key of Object.keys(order)) {
      if (!(key in update)) delete order[key]
    }
    for (const [key, value] of Object.entries(update)) {
      if (JSON.stringify(order[key]) !== JSON.stringify(value)) order[key] = value
    }
    return order
  })
  return next.length === current.length && next.every((order, index) => order === current[index]) ? current : next
}
