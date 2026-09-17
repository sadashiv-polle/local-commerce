<script setup>
import { computed, inject, nextTick, onMounted, ref } from 'vue'
import { call } from './api.js'
import SellingOptionsEditor from './SellingOptionsEditor.vue'
const props = defineProps({ shop: { type: String, required: true } })
const session = inject('session')
const data = ref(null), error = ref(''), success = ref(''), loading = ref(false), busy = ref(false)
const section = ref('stock'), selected = ref(null), modal = ref(null), form = ref({}), operation = ref('')
const report = ref(null), startDate = ref(localDate()), endDate = ref(localDate())
const pending = ref(null)
const storageKey = `lc-fish-pending:${session.value.user}:${props.shop}`
function localDate() { const date = new Date(); return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}` }
const names = computed(() => Object.fromEntries((data.value?.items || []).map(row => [row.name, row.item_name])))
const totals = computed(() => (data.value?.lots || []).reduce((sum, row) => ({
  fresh: sum.fresh + (row.expired ? 0 : row.free), expired: sum.expired + (row.expired ? row.free : 0), reserved: sum.reserved + row.reserved,
}), { fresh: 0, expired: 0, reserved: 0 }))
function money(value) { return new Intl.NumberFormat(undefined, { style: 'currency', currency: data.value?.currency || 'INR' }).format(Number(value || 0)) }
function kg(value) { return Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 6 }) }
function when(value) { return value ? String(value).replace('T', ' ').slice(0, 19) : '—' }
async function load() {
  loading.value = true; error.value = ''
  try { data.value = await call('fish.snapshot', { shop: props.shop }) }
  catch (e) { error.value = e.message }
  finally { loading.value = false }
}
async function loadReport() {
  section.value = 'reports'; loading.value = true; error.value = ''
  try { report.value = await call('fish.report', { shop: props.shop, start_date: startDate.value, end_date: endDate.value }) }
  catch (e) { error.value = e.message; report.value = null }
  finally { loading.value = false }
}
async function open(item, kind, lot = null) {
  if (busy.value || pending.value) return
  selected.value = item; operation.value = kind
  form.value = { quantity: lot ? lot.free : '', unit_cost: '', validity_hours: item.validity_hours || '', reason: kind === 'Wastage' ? 'Expired fish stock' : '', lot: lot?.name || '', price: item.price ?? '', selling_options: (item.selling_options || []).map(row => ({ ...row })) }
  await nextTick(); modal.value.showModal()
}
async function savePrice() {
  busy.value = true; error.value = ''
  try {
    const item = selected.value
    await call('owner.update_product', { shop: props.shop, item: item.name, modified: item.modified, item_name: item.item_name, description: item.lc_description || '', low_stock: item.lc_low_stock || 0, sold_out: Number(!!item.lc_sold_out), archived: Number(!!item.disabled), price: form.value.price, selling_options: form.value.selling_options, validity_hours: form.value.validity_hours }, true)
    modal.value.close(); await load(); success.value = 'Market prices saved. Existing orders keep their agreed prices.'
  } catch (e) { error.value = e.message }
  finally { busy.value = false }
}
async function execute(request) {
  busy.value = true; error.value = ''; success.value = ''
  try {
    if (!pending.value) { sessionStorage.setItem(storageKey, JSON.stringify(request)); pending.value = request }
    await call(pending.value.method, pending.value.payload, true)
    sessionStorage.removeItem(storageKey); pending.value = null; modal.value?.close()
    await load(); success.value = 'Fish stock recorded. ERPNext stock and valuation remain the accounting source.'
  } catch (e) {
    error.value = e.message
    if ([400, 403, 417].includes(e.status)) { sessionStorage.removeItem(storageKey); pending.value = null }
  } finally { busy.value = false }
}
async function saveStock() {
  const payload = { shop: props.shop, item: selected.value.name, request_key: crypto.randomUUID(), validity_hours: form.value.validity_hours }
  if (operation.value === 'Opening') await execute({ method: 'fish.adopt', payload })
  else await execute({ method: 'fish.adjust', payload: { ...payload, action: operation.value, quantity: form.value.quantity, unit_cost: form.value.unit_cost || 0, reason: form.value.reason, lot: form.value.lot } })
}
onMounted(() => {
  try { pending.value = JSON.parse(sessionStorage.getItem(storageKey) || 'null') } catch { error.value = 'Enable session storage to record stock safely.' }
  load()
})
</script>
<template>
  <section class="fish-workspace">
    <div class="section-title"><div><span class="eyebrow">FRESH STOCK, CLEAR NUMBERS</span><h2>Fish inventory</h2><p class="muted">Daily market prices, lot expiry and stock movements for this shop.</p></div><button :disabled="loading || busy" @click="section === 'reports' ? loadReport() : load()">Refresh</button></div>
    <p v-if="error" class="lc-notice" role="alert">{{ error }}</p><p v-if="success" class="success-note" role="status">{{ success }}</p><p v-if="loading" role="status">Loading fish inventory…</p>
    <div v-if="pending" class="setup-callout"><strong>A stock request needs confirmation</strong><p>Retry the saved request before recording another movement.</p><button :disabled="busy" @click="execute(pending)">Retry saved request</button></div>
    <nav class="panel-tabs" aria-label="Fish inventory sections"><button :aria-pressed="section === 'stock'" @click="section = 'stock'">Stock &amp; expiry</button><button :aria-pressed="section === 'prices'" @click="section = 'prices'">Market prices</button><button :aria-pressed="section === 'movements'" @click="section = 'movements'">Stock in &amp; out</button><button :aria-pressed="section === 'reports'" @click="loadReport">Reports</button></nav>
    <template v-if="data">
      <div v-if="section === 'stock'" class="fish-stock-section">
        <div class="inventory-metrics"><div><small>UNEXPIRED &amp; UNRESERVED</small><strong>{{ kg(totals.fresh) }} kg</strong></div><div><small>EXPIRED &amp; UNRESERVED</small><strong class="fish-danger">{{ kg(totals.expired) }} kg</strong></div><div><small>RESERVED FOR ORDERS</small><strong>{{ kg(totals.reserved) }} kg</strong></div></div>
        <div class="fish-product-list"><article v-for="item in data.items" :key="item.name" class="fish-product-card"><div><h3>{{ item.item_name }}</h3><p>{{ kg(item.stock.available) }} kg sellable · {{ kg(item.stock.actual) }} kg on hand</p><small>New receipt validity: {{ item.validity_hours ? `${item.validity_hours} hours` : 'Set when receiving stock' }}</small></div><div class="fish-card-actions"><button :disabled="busy || !!pending || item.disabled" @click="open(item, 'Add')">+ Receive stock</button><button :disabled="busy || !!pending || item.disabled" @click="open(item, 'Remove')">Remove stock</button><button v-if="item.stock.untracked > 0" :disabled="busy || !!pending" @click="open(item, 'Opening')">Track existing {{ kg(item.stock.untracked) }} kg</button></div></article></div>
        <p v-if="!data.items.length" class="lc-empty">Create a fish product with unit Kg in Products &amp; stock to begin.</p>
        <h3>Stock lots</h3><p class="muted">Fresh receipts keep separate expiry times. Expired stock cannot be used for new orders. Reserved expired stock requires cancelling or repacking its orders before wastage.</p>
        <p v-if="!data.lots.length" class="lc-empty">No remaining stock lots.</p>
        <article v-for="lot in data.lots" :key="lot.name" class="fish-lot-card" :class="{ expired: lot.expired }"><div><strong>{{ names[lot.item] }}</strong><span class="inventory-badge" :class="{ unavailable: lot.expired }">{{ lot.expired ? 'Expired' : 'Valid' }}</span><p>{{ kg(lot.remaining) }} kg remaining · {{ kg(lot.reserved) }} kg reserved</p><small>{{ lot.expired ? 'Expired' : 'Valid until' }} {{ when(lot.expires_at) }} · Receipt {{ when(lot.creation) }}</small><small>{{ lot.opening ? 'Tracked existing stock' : lot.stock_entry }} · Receipt cost {{ money(lot.unit_cost) }} / kg</small></div><button v-if="lot.expired" class="fish-waste-button" :disabled="busy || !!pending || lot.free <= 0 || !data.wastage_account" @click="open(data.items.find(item => item.name === lot.item), 'Wastage', lot)">Mark {{ kg(lot.free) }} kg as wastage</button></article>
        <p v-if="!data.wastage_account" class="lc-notice">A platform administrator must select a Company expense account in Shop settings before recording wastage.</p>
      </div>
      <div v-if="section === 'prices'"><p class="muted">Set today's market price per kg and per piece. Existing orders retain their original prices.</p><article v-for="item in data.items" :key="item.name" class="fish-product-card"><div><h3>{{ item.item_name }}</h3><strong>{{ money(item.price) }} / kg</strong><small>{{ item.selling_options.length }} configured options</small></div><button :disabled="busy || !!pending" @click="open(item, 'Price')">Edit market prices</button></article><h3>Price history</h3><article v-for="row in data.price_history" :key="row.name" class="history-row"><strong>{{ names[row.item] }} · {{ money(row.weight_price) }} / kg</strong><small>{{ when(row.creation) }} · {{ row.owner }}</small><small v-for="offer in JSON.parse(row.selling_options_json || '[]')" :key="offer.id">{{ offer.label }} · {{ offer.billing === 'Pieces' ? `${money(offer.piece_price)} / piece` : 'Price by packed weight' }} · {{ offer.enabled === false ? 'Hidden' : 'Shown' }}</small></article></div>
      <div v-if="section === 'movements'"><p class="muted">Latest 100 movements. Sales leave stock when picked up; revenue is recorded when invoiced.</p><article v-for="row in data.movements" :key="row.name" class="history-row"><strong>{{ names[row.item] }} · {{ row.kind }} · {{ ['Receipt', 'Opening'].includes(row.kind) ? '+' : '−' }}{{ kg(row.quantity) }} kg</strong><p>{{ row.reason }}</p><small>{{ when(row.creation) }} · {{ row.stock_entry || row.delivery_note || 'Existing stock tracking' }}</small></article></div>
      <section v-if="section === 'reports'" class="fish-reports"><form class="fish-report-dates" @submit.prevent="loadReport"><label>From<input v-model="startDate" type="date" required></label><label>Through<input v-model="endDate" type="date" required></label><button class="lc-primary" :disabled="loading">Show report</button></form><template v-if="report"><div class="inventory-metrics"><div><small>PRODUCT REVENUE</small><strong>{{ money(report.totals.revenue) }}</strong></div><div><small>COST OF INVOICED FISH</small><strong>{{ money(report.totals.cost) }}</strong></div><div><small>WASTAGE COST</small><strong class="fish-danger">{{ money(report.totals.wastage_cost) }}</strong></div><div><small>PROFIT AFTER STOCK LOSSES</small><strong>{{ money(report.totals.profit_after_stock_losses) }}</strong></div></div><p class="muted">{{ report.basis }}</p><p>Other stock removal cost: {{ money(report.totals.removal_cost) }} · Delivery revenue: {{ money(report.totals.delivery_revenue) }} · Closing stock value: {{ money(report.totals.closing_value) }}</p><div class="fish-report-table"><table><thead><tr><th>Fish</th><th>Opening kg</th><th>In kg</th><th>Out kg</th><th>Closing kg</th><th>Sold kg</th><th>Sold pieces</th><th>Revenue</th><th>Sales cost</th><th>Wasted kg</th><th>Waste cost</th><th>Removal cost</th><th>Profit after stock losses</th></tr></thead><tbody><tr v-for="row in report.items" :key="row.item"><th>{{ row.item_name }}</th><td>{{ kg(row.opening_kg) }}</td><td>{{ kg(row.stock_in_kg) }}</td><td>{{ kg(row.stock_out_kg) }}</td><td>{{ kg(row.closing_kg) }}</td><td>{{ kg(row.sold_kg) }}</td><td>{{ kg(row.sold_pieces) }}</td><td>{{ money(row.revenue) }}</td><td>{{ money(row.cost) }}</td><td>{{ kg(row.wastage_kg) }}</td><td>{{ money(row.wastage_cost) }}</td><td>{{ money(row.removal_cost) }}</td><td>{{ money(row.profit_after_stock_losses) }}</td></tr></tbody></table></div></template></section>
    </template>
    <dialog ref="modal" class="product-editor fish-editor"><template v-if="selected"><div class="product-editor-heading"><div><span class="eyebrow">{{ operation === 'Price' ? 'DAILY MARKET VALUE' : 'FISH STOCK' }}</span><h2>{{ selected.item_name }}</h2></div><button type="button" aria-label="Close editor" @click="modal.close()">×</button></div><p v-if="error" class="lc-notice" role="alert">{{ error }}</p><form v-if="operation === 'Price'" @submit.prevent="savePrice"><fieldset :disabled="busy"><label>Price per kg ({{ data.currency }})<input v-model="form.price" type="number" min="0.000001" step="0.01" required></label><label>Default validity for new receipts (hours)<input v-model="form.validity_hours" type="number" min="0.000001" max="8760" step="0.5" required></label><SellingOptionsEditor v-model="form.selling_options" uom="Kg" :disabled="busy" /><button class="lc-primary">Save market prices</button></fieldset></form><form v-else @submit.prevent="saveStock"><p v-if="operation === 'Opening'" class="muted">Track the existing {{ kg(selected.stock.untracked) }} kg in your warehouse. This does not receive stock again or create another accounting entry. Choose its remaining validity carefully.</p><p v-if="operation === 'Wastage'" class="lc-notice">This posts a stock issue to the configured wastage expense account. It preserves the stock and accounting history.</p><fieldset :disabled="busy || !!pending"><label v-if="operation !== 'Opening'">{{ operation }} quantity (kg)<input v-model="form.quantity" type="number" min="0.000001" step="0.001" required></label><label v-if="operation === 'Add'">Receipt cost per kg ({{ data.currency }})<input v-model="form.unit_cost" type="number" min="0.000001" step="0.01" required></label><label v-if="['Add', 'Opening'].includes(operation)">Stock validity from now (hours)<input v-model="form.validity_hours" type="number" min="0.000001" max="8760" step="0.5" required><small>Only this stock lot receives this expiry time.</small></label><label v-if="operation !== 'Opening'">Reason<textarea v-model="form.reason" minlength="3" maxlength="500" required /></label><button :class="operation === 'Wastage' ? 'fish-waste-button' : 'lc-primary'">{{ busy ? 'Recording…' : operation === 'Opening' ? 'Track existing stock' : operation === 'Wastage' ? 'Confirm wastage' : 'Record stock movement' }}</button></fieldset></form></template></dialog>
  </section>
</template>
