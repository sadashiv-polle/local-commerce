<script setup>
import { inject, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import AuthChoices from './AuthChoices.vue'
import { call } from './api.js'
import MapView from './MapView.vue'

const session = inject('session')
const props = defineProps({ shop: { type: String, default: '' }, editable: Boolean })
const orders = ref([]), drivers = ref([]), selectedDrivers = ref({}), start = ref(0)
const error = ref(''), loading = ref(false), busy = ref(false), reasons = ref({})
const routes = ref({}), routeErrors = ref({})
const routeRequests = new Set()
const next = { Requested: 'Accepted', Accepted: 'Preparing', Preparing: 'Ready' }
const nextLabel = { Requested: 'Accept order', Accepted: 'Start preparing', Preparing: 'Mark ready' }
const cancellable = new Set(['Requested', 'Accepted', 'Preparing', 'Ready'])
const steps = ['Requested', 'Accepted', 'Preparing', 'Ready', 'Picked Up', 'Out for Delivery', 'Delivered']
let generation = 0
let refreshTimer

function money(value, currency) { return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(value) }
function mapPoints(order) {
  const points = []
  if (order.shop_location) points.push({ ...order.shop_location, kind: 'shop', label: order.shop_name })
  if (order.destination_location) points.push({ ...order.destination_location, kind: 'customer', label: order.recipient })
  if (order.driver_location) points.push({ ...order.driver_location, kind: 'rider', label: order.delivery_name || 'Rider' })
  return points
}
async function ensureRoute(order) {
  if (!['Picked Up', 'Out for Delivery'].includes(order.status) || routes.value[order.name] || routeErrors.value[order.name] || routeRequests.has(order.name)) return
  routeRequests.add(order.name)
  try {
    const result = await call('orders.delivery_route', { order: order.name })
    routes.value = { ...routes.value, [order.name]: result }
  } catch (e) { routeErrors.value = { ...routeErrors.value, [order.name]: e.message } }
  finally { routeRequests.delete(order.name) }
}
function loadRoutes(rows) { for (const order of rows) ensureRoute(order) }
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
      loadRoutes(result)
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
onMounted(() => { refreshTimer = window.setInterval(() => { if (!props.shop && !loading.value && !busy.value && orders.value.some(order => !['Delivered', 'Cancelled'].includes(order.status))) load() }, 10000) })
onBeforeUnmount(() => window.clearInterval(refreshTimer))
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
      <p class="payment-summary"><span><small>PAYMENT METHOD</small><strong>{{ order.payment_method }}</strong></span><span><small>PAYMENT STATUS</small><strong :class="{ paid: order.payment_status === 'Reconciled' }">{{ order.payment_status }}</strong></span></p>
      <section v-if="!shop && order.delivery_otp" class="customer-delivery-otp" aria-label="Delivery confirmation code"><div><span aria-hidden="true">✓</span><div><small>DELIVERY CONFIRMATION</small><strong>{{ order.delivery_otp }}</strong></div></div><p>Share this code with the rider only after you receive your order. It is shown here instead of being sent by email.</p></section>
      <details><summary>Delivery details</summary><p>{{ order.address.line1 }}<br>{{ order.address.city }} · {{ order.address.postal_code }}<br><a :href="`tel:${order.phone}`">{{ order.phone }}</a></p></details>
      <p v-if="order.delivery_instructions" class="delivery-instructions"><strong>Delivery note</strong>{{ order.delivery_instructions }}</p>
      <section v-if="order.destination_location && (shop || order.status === 'Out for Delivery')" class="order-tracking-panel"><div class="tracking-heading"><div><span class="eyebrow">{{ order.status === 'Out for Delivery' ? 'LIVE DELIVERY' : 'DELIVERY MAP' }}</span><h4>{{ order.status === 'Out for Delivery' ? 'Track your rider' : 'Delivery route' }}</h4></div><span v-if="routes[order.name]">{{ routes[order.name].distance_km }} km · about {{ routes[order.name].duration_minutes }} min</span><span v-else-if="order.delivery_distance_km != null">{{ Number(order.delivery_distance_km).toFixed(1) }} km from shop</span></div><MapView :config="order.map" :points="mapPoints(order)" :route="routes[order.name]?.points || []" height="250px" /><div class="map-legend"><span><i class="legend-shop"></i>Shop</span><span><i class="legend-customer"></i>Delivery</span><span v-if="order.driver_location"><i class="legend-rider"></i>Rider</span></div><small v-if="routes[order.name]" class="route-attribution"><a :href="routes[order.name].attribution_url" target="_blank" rel="noopener">{{ routes[order.name].attribution }}</a></small><p v-if="routeErrors[order.name]" class="route-error">{{ routeErrors[order.name] }}</p><p v-if="order.status === 'Out for Delivery' && order.driver_location" class="map-confirmation">Rider location updated {{ order.driver_location.updated_at }}</p><p v-else-if="order.status === 'Out for Delivery'" class="muted">Waiting for the rider to start live location sharing. This page refreshes automatically.</p></section>
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
