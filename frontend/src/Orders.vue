<script setup>
import { inject, ref, watch } from 'vue'
import AuthChoices from './AuthChoices.vue'
import { call } from './api.js'

const session = inject('session')
const props = defineProps({ shop: { type: String, default: '' }, editable: Boolean })
const orders = ref([]), drivers = ref([]), selectedDrivers = ref({}), start = ref(0)
const error = ref(''), loading = ref(false), busy = ref(false), reasons = ref({})
const next = { Requested: 'Accepted', Accepted: 'Preparing', Preparing: 'Ready' }
const nextLabel = { Requested: 'Accept order', Accepted: 'Start preparing', Preparing: 'Mark ready' }
const cancellable = new Set(['Requested', 'Accepted', 'Preparing', 'Ready'])
const steps = ['Requested', 'Accepted', 'Preparing', 'Ready', 'Picked Up', 'Out for Delivery', 'Delivered']
let generation = 0

function money(value, currency) { return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(value) }
async function load(delta = 0) {
  if (session.value.user === 'Guest') return
  const current = ++generation
  start.value = Math.max(0, start.value + delta); loading.value = true; error.value = ''
  try {
    const requests = [call('orders.list_orders', { ...(props.shop ? { shop: props.shop } : {}), start: start.value })]
    if (props.shop && props.editable) requests.push(call('orders.drivers', { shop: props.shop }))
    const [result, availableDrivers = []] = await Promise.all(requests)
    if (current === generation) {
      orders.value = result
      drivers.value = availableDrivers
      selectedDrivers.value = Object.fromEntries(result.map(order => [order.name, order.delivery_user || '']))
    }
  } catch (e) { if (current === generation) error.value = e.message }
  finally { if (current === generation) loading.value = false }
}
async function change(order, target) {
  busy.value = true; error.value = ''
  try { await call('orders.change', { order: order.name, target, reason: reasons.value[order.name] || '' }, true); await load() }
  catch (e) { error.value = e.message }
  finally { busy.value = false }
}
async function assign(order) {
  const deliveryUser = selectedDrivers.value[order.name]
  if (!deliveryUser) return
  busy.value = true; error.value = ''
  try { await call('orders.assign_driver', { order: order.name, delivery_user: deliveryUser }, true); await load() }
  catch (e) { error.value = e.message }
  finally { busy.value = false }
}
watch(() => props.shop, () => { start.value = 0; load() }, { immediate: true })
</script>

<template>
  <AuthChoices v-if="session.user === 'Guest'" />
  <section v-else class="orders-page">
    <div class="inventory-heading"><div><span class="eyebrow">DELIVERY ORDERS</span><h2>{{ shop ? 'Your orders' : 'My orders' }}</h2><p>{{ shop ? 'Prepare each order, assign a rider, and follow it through delivery.' : 'Track every step from shop confirmation to delivery.' }}</p></div><button :disabled="loading || busy" @click="load()">Refresh orders</button></div>
    <p v-if="error" class="lc-notice" role="alert">{{ error }}</p>
    <p v-if="loading" role="status">Loading orders…</p>
    <p v-else-if="!orders.length" class="lc-empty">No delivery orders yet.</p>
    <article v-for="order in orders" :key="order.name" class="order-card">
      <div class="workspace-heading"><div><span class="eyebrow">{{ order.shop_name }} · {{ order.name }}</span><h3>{{ order.recipient }}</h3><small>{{ order.created }}</small></div><span class="status-pill">{{ order.status }}</span></div>
      <div class="delivery-progress" :aria-label="`Order status: ${order.status}`"><span v-for="step in steps" :key="step" :class="{ complete: steps.indexOf(step) <= steps.indexOf(order.status) }">{{ step }}</span></div>
      <ul><li v-for="(item, index) in order.items" :key="index">{{ item.quantity }} {{ item.uom }} · {{ item.name }} <strong>{{ money(item.amount, order.currency) }}</strong></li></ul>
      <p><strong>Order total {{ money(order.total, order.currency) }}</strong><br><small>Includes {{ money(order.taxes_and_charges, order.currency) }} in configured taxes and delivery charges. Payment is not collected online yet.</small></p>
      <details><summary>Delivery details</summary><p>{{ order.address.line1 }}<br>{{ order.address.city }} · {{ order.address.postal_code }}<br><a :href="`tel:${order.phone}`">{{ order.phone }}</a></p></details>
      <p v-if="order.delivery_user" class="rider-summary"><span aria-hidden="true">●</span><strong>{{ order.delivery_name }}</strong> is assigned to this delivery.</p>
      <p v-if="order.reason">Cancellation: {{ order.reason }}</p>
      <p v-if="order.status === 'Requested'" class="muted">The shop will check stock before accepting this order.</p>
      <p v-else-if="order.status === 'Ready' && !order.delivery_user" class="muted">Packed and ready. Waiting for the shop to assign a delivery person.</p>
      <p v-else-if="order.status === 'Ready'" class="muted">Your order is ready and assigned for pickup.</p>
      <p v-else-if="order.status === 'Delivered'" class="success-note">Delivered successfully{{ order.delivered_at ? ` on ${order.delivered_at}` : '' }}.</p>
      <div v-if="shop && editable && order.status === 'Ready'" class="driver-assignment">
        <label>Delivery person<select v-model="selectedDrivers[order.name]" :disabled="busy || !drivers.length"><option value="" disabled>Select a rider</option><option v-for="driver in drivers" :key="driver.user" :value="driver.user">{{ driver.full_name }}</option></select></label>
        <button class="lc-primary" :disabled="busy || !selectedDrivers[order.name] || selectedDrivers[order.name] === order.delivery_user" @click="assign(order)">{{ order.delivery_user ? 'Reassign rider' : 'Assign rider' }}</button>
        <small v-if="!drivers.length">No drivers are assigned to this shop. A platform administrator can add a Driver membership in Desk.</small>
      </div>
      <div v-if="(shop && editable) || (!shop && order.status === 'Requested')" class="order-actions">
        <button v-if="shop && next[order.status]" class="lc-primary" :disabled="busy" @click="change(order, next[order.status])">{{ nextLabel[order.status] }}</button>
        <details v-if="cancellable.has(order.status)"><summary>Cancel order</summary><label>Reason<input v-model="reasons[order.name]" minlength="3" maxlength="500"></label><button :disabled="busy || (reasons[order.name] || '').trim().length < 3" @click="change(order, 'Cancelled')">Confirm cancellation</button></details>
      </div>
    </article>
    <div class="lc-pagination"><button :disabled="!start || loading || busy" @click="load(-20)">Previous</button><span>Page {{ start / 20 + 1 }}</span><button :disabled="orders.length < 20 || loading || busy" @click="load(20)">Next</button></div>
  </section>
</template>
