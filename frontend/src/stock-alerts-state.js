import { ref } from 'vue'
import { call } from './api.js'
export const stockAlerts = ref(new Set())
let account, pending, generation = 0
export function resetStockAlerts(user) {
  if (account !== user) { account = user; generation++; pending = null; stockAlerts.value = new Set() }
}
export async function loadStockAlerts(user) {
  resetStockAlerts(user)
  if (!user || user === 'Guest') return
  if (!pending) {
    const current = generation
    pending = call('stock_alerts.ids').then(ids => {
      if (generation === current) stockAlerts.value = new Set(ids)
    }).finally(() => { if (generation === current) pending = null })
  }
  return pending
}
export function setStockAlert(user, item, saved) {
  if (account !== user) return
  generation++; pending = null
  const next = new Set(stockAlerts.value)
  if (saved) next.add(item); else next.delete(item)
  stockAlerts.value = next
}
