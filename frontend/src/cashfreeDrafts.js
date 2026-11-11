// Refresh payment history without discarding unsaved settings in other shops.
export function mergeShopDrafts(fresh, drafts = [], savedShop = '') {
  return fresh.map(shop => {
    const draft = drafts?.find(row => row.name === shop.name)
    const result = { ...shop }
    if (draft && shop.name !== savedShop) {
      for (const [key, value] of Object.entries(draft)) {
        if (key.startsWith('cashfree_')) result[key] = value
      }
    }
    for (const key of Object.keys(result)) {
      if (key.startsWith('cashfree_') && result[key] == null) result[key] = ''
    }
    result.cashfree_enabled = Number(result.cashfree_enabled) === 1
    result.cashfree_auto_reconcile = Number(result.cashfree_auto_reconcile) === 1
    result.cashfree_settlement_mode ||= 'Easy Split'
    result.cashfree_commission_type ||= 'Percentage'
    return result
  })
}
