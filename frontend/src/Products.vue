<script setup>
import { computed, inject, nextTick, onMounted, ref } from 'vue'
import { call } from './api.js'
const props = defineProps({ shop: { type: String, required: true }, editable: Boolean })
const items = ref([]), total = ref(0), summary = ref({ products: 0, paused: 0, archived: 0 })
const choices = ref({ groups: [], uoms: [] }), config = ref({ warehouses: [], accounts: [], cost_centers: [] })
const loading = ref(false), saving = ref(false), error = ref(''), success = ref(''), start = ref(0)
const search = ref(''), status = ref('All'), warehouse = ref(''), configured = ref(false)
const showSetup = ref(false), showCreate = ref(false), form = ref({ item_name: '', item_group: '', stock_uom: '' })
const selected = ref(null), edit = ref({}), panel = ref('details'), editor = ref(null)
const historyRows = ref([]), historyStart = ref(0), historyLoading = ref(false)
const adjustment = ref({ action: 'Add', quantity: '', unit_cost: '', reason: '' })
const pending = ref(null)
const session = inject('session')
const pendingStorageKey = `lc-stock-pending:${session.value.user}:${props.shop}`
function savePending(value) {
  if (value) sessionStorage.setItem(pendingStorageKey, JSON.stringify(value))
  else sessionStorage.removeItem(pendingStorageKey)
  pending.value = value
}
const lowCount = computed(() => items.value.filter(i => i.stock.available <= Number(i.lc_low_stock || 0) && !i.disabled).length)
let sequence = 0
function key() { return Array.from(crypto.getRandomValues(new Uint8Array(24)), b => b.toString(16).padStart(2, '0')).join('') }
const creationKey = ref(key())
function money(value, currency) { return value == null ? 'Not priced' : new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(value) }
async function load(reset = false) {
  if (reset) start.value = 0
  const request = ++sequence
  loading.value = true; error.value = ''
  try {
    const result = await call('owner.catalog', { shop: props.shop, start: start.value, search: search.value, status: status.value })
    if (request !== sequence) return
    items.value = result.items; total.value = result.total; summary.value = result.summary
    warehouse.value = result.warehouse; configured.value = result.configured
  } catch (e) { if (request === sequence) error.value = e.message }
  finally { if (request === sequence) loading.value = false }
}
async function init() {
  try { pending.value = JSON.parse(sessionStorage.getItem(pendingStorageKey) || 'null') }
  catch { error.value = 'Browser storage is unavailable. Stock adjustments require retry storage.' }
  await load()
  if (props.editable) {
    try {
      const [options, settings] = await Promise.all([call('products.options', { shop: props.shop }), call('owner.setup_options', { shop: props.shop })])
      choices.value = options; config.value = settings
    } catch (e) { error.value = e.message }
  }
}
async function configure() {
  saving.value = true; error.value = ''
  try {
    config.value = await call('owner.configure', { shop: props.shop, warehouse: config.value.warehouse, account: config.value.account, cost_center: config.value.cost_center }, true)
    showSetup.value = false; await load(); success.value = 'Inventory and pricing setup saved.'
  } catch (e) { error.value = e.message }
  finally { saving.value = false }
}
async function create() {
  saving.value = true; error.value = ''; success.value = ''
  try {
    const item = await call('products.create_item', { shop: props.shop, ...form.value, request_key: creationKey.value }, true)
    creationKey.value = key(); form.value.item_name = ''; showCreate.value = false
    await load(true); success.value = `${item.item_name} created. Add a selling price and stock to get it ready.`
  } catch (e) { error.value = e.message; if (e.status === 417) creationKey.value = key() }
  finally { saving.value = false }
}
function applyItem(item) {
  selected.value = item
  edit.value = { item_name: item.item_name, description: item.lc_description || '', low_stock: item.lc_low_stock || 0, sold_out: !!item.lc_sold_out, archived: !!item.disabled, price: item.price ?? '' }
}
async function open(item) {
  if (pending.value && pending.value.item !== item.name) { error.value = 'Resolve the pending stock adjustment before opening another product.'; return }
  error.value = ''; saving.value = true
  try {
    applyItem(await call('owner.detail', { shop: props.shop, item: item.name }))
    panel.value = pending.value ? 'stock' : 'details'; historyRows.value = []; historyStart.value = 0
    adjustment.value = { action: 'Add', quantity: '', unit_cost: '', reason: '' }
    await nextTick(); editor.value.showModal()
  } catch (e) { error.value = e.message }
  finally { saving.value = false }
}
async function saveProduct() {
  saving.value = true; error.value = ''
  try {
    applyItem(await call('owner.update_product', { shop: props.shop, item: selected.value.name, modified: selected.value.modified, ...edit.value, sold_out: Number(edit.value.sold_out), archived: Number(edit.value.archived) }, true))
    await load(); success.value = 'Product updated.'; editor.value.close()
  } catch (e) { error.value = e.message }
  finally { saving.value = false }
}
async function moveStock() {
  saving.value = true; error.value = ''; success.value = ''
  try {
    if (!pending.value) savePending({ shop: props.shop, item: selected.value.name, ...adjustment.value, unit_cost: adjustment.value.action === 'Add' ? adjustment.value.unit_cost : 0, request_key: key() })
    const result = await call('owner.adjust_stock', pending.value, true)
    savePending(null)
    applyItem(await call('owner.detail', { shop: props.shop, item: selected.value.name }))
    await load(); success.value = `Stock updated · ${result.stock_entry}`; editor.value.close()
  } catch (e) {
    error.value = e.message
    if ([400, 403, 417].includes(e.status)) savePending(null)
  } finally { saving.value = false }
}
async function history(delta = 0) {
  panel.value = 'history'; historyStart.value = Math.max(0, historyStart.value + delta); historyLoading.value = true
  try { historyRows.value = await call('owner.history', { shop: props.shop, item: selected.value.name, start: historyStart.value }) }
  catch (e) { error.value = e.message }
  finally { historyLoading.value = false }
}
function close(event) { if (saving.value || pending.value) event?.preventDefault(); else editor.value.close() }
onMounted(init)
</script>

<template>
  <section class="products-panel">
    <div class="inventory-heading"><div><span class="eyebrow">YOUR SHOP, IN STOCK</span><h2>Products & inventory</h2><p class="muted">Keep your shelves ready for the neighbourhood.</p></div><div class="button-row"><button v-if="editable" :disabled="saving" @click="showSetup = !showSetup">Inventory setup</button><button v-if="editable" class="lc-primary" :disabled="saving" @click="showCreate = !showCreate">＋ Add product</button></div></div>
    <div class="inventory-metrics"><div><small>YOUR PRODUCTS</small><strong>{{ summary.products }}</strong><span>Across your shop</span></div><div><small>MANUALLY SOLD OUT</small><strong>{{ summary.paused }}</strong><span>Availability paused</span></div><div><small>NEEDS ATTENTION</small><strong>{{ lowCount }}</strong><span>Low stock on this page</span></div><div><small>ARCHIVED</small><strong>{{ summary.archived }}</strong><span>Safely kept in history</span></div></div>
    <p v-if="error && !editor?.open" class="lc-notice" role="alert">{{ error }}</p>
    <p v-if="success" class="success-note" role="status">✓ {{ success }}</p>
    <div v-if="pending && !editor?.open" class="setup-callout"><strong>A stock adjustment needs confirmation</strong><p>Resume the saved request to confirm its result without recording it twice.</p><button @click="open({ name: pending.item })">Resume adjustment</button></div>
    <div v-if="!configured" class="setup-callout"><strong>Get your inventory ready</strong><p>Select your Company warehouse and adjustment accounts to start recording stock. A dedicated selling price list will be created for this shop.</p><button v-if="editable" @click="showSetup = true">Complete setup →</button></div>
    <form v-if="showSetup && editable" class="inventory-form" @submit.prevent="configure">
      <h3>Inventory & pricing setup</h3><p class="muted">Only locations and accounts belonging to your shop's Company are available.</p>
      <div class="form-columns"><label>Warehouse<select v-model="config.warehouse" required :disabled="saving"><option value="">Select warehouse</option><option v-for="w in config.warehouses" :key="w">{{ w }}</option></select></label><label>Stock adjustment account<select v-model="config.account" required :disabled="saving"><option value="">Select account</option><option v-for="a in config.accounts" :key="a">{{ a }}</option></select></label><label>Cost center<select v-model="config.cost_center" required :disabled="saving"><option value="">Select cost center</option><option v-for="c in config.cost_centers" :key="c">{{ c }}</option></select></label></div>
      <p v-if="!config.warehouses?.length || !config.accounts?.length || !config.cost_centers?.length" class="muted">Ask your ERPNext administrator to create the missing warehouse, Stock Adjustment account or cost center for this Company.</p>
      <button class="lc-primary" :disabled="saving">{{ saving ? 'Saving…' : 'Save setup' }}</button>
    </form>
    <form v-if="showCreate && editable" class="inventory-form" @submit.prevent="create">
      <h3>A new addition to your shelves</h3><div class="form-columns"><label>Product name<input v-model="form.item_name" required maxlength="140" placeholder="e.g. Whole wheat bread" :disabled="saving"></label><label>Category<select v-model="form.item_group" required :disabled="saving"><option value="">Select category</option><option v-for="g in choices.groups" :key="g">{{ g }}</option></select></label><label>Unit<select v-model="form.stock_uom" required :disabled="saving"><option value="">Select unit</option><option v-for="u in choices.uoms" :key="u">{{ u }}</option></select></label></div><button class="lc-primary" :disabled="saving">{{ saving ? 'Creating…' : 'Create product' }}</button>
    </form>
    <form class="inventory-toolbar" @submit.prevent="load(true)"><label class="search-label"><span class="sr-only">Search product names</span><input v-model="search" type="search" placeholder="Search your products…" maxlength="140"></label><select v-model="status" aria-label="Filter products" @change="load(true)"><option>All</option><option>Active</option><option>Sold out</option><option>Archived</option></select><button :disabled="loading">Search</button><button type="button" :disabled="loading" @click="load()">Refresh</button></form>
    <div class="warehouse-caption"><span>{{ warehouse || 'No warehouse configured' }}</span><span>{{ total }} matching products</span></div>
    <p v-if="loading" role="status" class="lc-empty">Loading your inventory…</p>
    <div v-else-if="!items.length" class="inventory-empty"><span aria-hidden="true">▦</span><h3>Your shelves have room for something good.</h3><p>Add a product or change your search to get started.</p></div>
    <div v-else class="inventory-table-wrap"><table class="inventory-table"><thead><tr><th>Product</th><th>Selling price</th><th>Available stock</th><th>Status</th><th><span class="sr-only">Actions</span></th></tr></thead><tbody><tr v-for="item in items" :key="item.name"><td><div class="product-identity"><span class="product-letter" aria-hidden="true">{{ item.item_name.slice(0, 1).toUpperCase() }}</span><div><strong>{{ item.item_name }}</strong><small>{{ item.item_group }} · {{ item.stock_uom }}</small></div></div></td><td>{{ money(item.price, item.currency) }}<small>per {{ item.stock_uom }}</small></td><td><strong>{{ item.stock.available }}</strong> {{ item.stock_uom }}<small>{{ item.stock.actual }} on hand · {{ item.stock.reserved }} reserved</small><span v-if="item.stock.available <= Number(item.lc_low_stock || 0) && !item.disabled" class="low-stock">Low stock</span></td><td><span class="inventory-badge" :class="{ unavailable: item.availability !== 'In stock' }">{{ item.availability }}</span></td><td><button :disabled="saving" @click="open(item)">{{ editable ? 'Manage →' : 'View →' }}</button></td></tr></tbody></table></div>
    <div class="lc-pagination"><span>Page {{ Math.floor(start / 20) + 1 }}</span><button :disabled="loading || !start" @click="start -= 20; load()">Previous</button><button :disabled="loading || start + 20 >= total" @click="start += 20; load()">Next</button></div>
    <dialog ref="editor" class="product-dialog" aria-labelledby="product-dialog-title" @cancel="close">
      <template v-if="selected">
        <div class="dialog-heading"><div><span class="eyebrow">PRODUCT WORKSPACE</span><h2 id="product-dialog-title">{{ selected.item_name }}</h2></div><button aria-label="Close product" :disabled="saving || !!pending" @click="close">✕</button></div>
        <div class="panel-tabs"><button :aria-pressed="panel === 'details'" :disabled="saving || !!pending" @click="panel = 'details'">Details & price</button><button :aria-pressed="panel === 'stock'" :disabled="saving || !!pending" @click="panel = 'stock'">Adjust stock</button><button :aria-pressed="panel === 'history'" :disabled="saving || !!pending" @click="history()">History</button></div>
        <p v-if="error" class="lc-notice" role="alert">{{ error }}</p>
        <form v-if="panel === 'details'" @submit.prevent="saveProduct"><fieldset :disabled="!editable || saving"><label>Product name<input v-model="edit.item_name" required maxlength="140"></label><label>Description<textarea v-model="edit.description" maxlength="5000" rows="3"></textarea></label><div class="form-columns"><label>Selling price ({{ selected.currency }})<input v-model="edit.price" type="number" min="0" step="0.000001" placeholder="Not priced"></label><label>Low-stock threshold ({{ selected.stock_uom }})<input v-model="edit.low_stock" type="number" min="0" step="0.000001" required></label></div><label class="check-label"><input v-model="edit.sold_out" type="checkbox"><span>Mark as sold out<small>Pause availability without changing physical stock.</small></span></label><label class="check-label"><input v-model="edit.archived" type="checkbox"><span>Archive product<small>Disable the item; preserve stock and transaction history. Uncheck to restore.</small></span></label><p class="muted">Stock unit stays {{ selected.stock_uom }}. Taxes are calculated by the future checkout workflow.</p><button v-if="editable" class="lc-primary" :disabled="saving">{{ saving ? 'Saving…' : 'Save product' }}</button></fieldset></form>
        <form v-else-if="panel === 'stock'" @submit.prevent="moveStock"><div class="stock-total"><span>AVAILABLE IN {{ selected.warehouse || 'UNCONFIGURED WAREHOUSE' }}</span><strong>{{ selected.stock.available }} <small>{{ selected.stock_uom }}</small></strong></div><p class="muted">Record received stock or remove damaged, wasted or missing stock. Sales must go through orders and invoices.</p><fieldset :disabled="!editable || saving || !!pending"><label>Operation<select v-model="adjustment.action"><option>Add</option><option>Remove</option></select></label><div class="form-columns"><label>Quantity ({{ selected.stock_uom }})<input v-model="adjustment.quantity" type="number" min="0.000001" step="0.000001" required></label><label v-if="adjustment.action === 'Add'">Unit cost ({{ selected.currency }})<input v-model="adjustment.unit_cost" type="number" min="0.000001" step="0.000001" required></label></div><label>Reason<textarea v-model="adjustment.reason" required minlength="3" maxlength="500" placeholder="e.g. Received stock, damaged packaging or stock count shortage"></textarea></label></fieldset><p v-if="pending" class="lc-notice">The result is not confirmed. Retry this same adjustment before starting another one.</p><button v-if="editable" class="lc-primary" :disabled="saving || !configured">{{ saving ? 'Recording…' : pending ? 'Retry same adjustment' : 'Record stock adjustment' }}</button></form>
        <section v-else><p class="muted">Adjustments made through this workspace. Each entry links to an ERPNext stock transaction.</p><p v-if="historyLoading" role="status">Loading history…</p><p v-else-if="!historyRows.length" class="lc-empty">No adjustments on this page.</p><article v-for="row in historyRows" :key="row.name" class="history-row"><strong>{{ row.action === 'Add' ? '+' : '−' }}{{ row.quantity }} {{ selected.stock_uom }}</strong><p>{{ row.reason }}</p><small>{{ row.creation }} · {{ row.owner }}</small><small>{{ row.stock_entry }} · {{ row.warehouse }}</small></article><div class="lc-pagination"><button :disabled="historyLoading || !historyStart" @click="history(-20)">Previous</button><button :disabled="historyLoading || historyRows.length < 20" @click="history(20)">Next</button></div></section>
      </template>
    </dialog>
  </section>
</template>
