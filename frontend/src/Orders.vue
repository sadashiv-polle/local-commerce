<script setup>
import ManualUpiPayment from './ManualUpiPayment.vue'
import OrderReference from './OrderReference.vue'
import { computed, inject, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { writeCart } from './cart.js'
import AuthChoices from './AuthChoices.vue'
import { call } from './api.js'
import MapView from './MapView.vue'

const session = inject('session'), router = useRouter(), route = useRoute()
const reorderDialog = ref(null), reorder = ref(null), reorderBusy = ref(false), reorderError = ref('')
async function reviewReorder(order) {
  reorderBusy.value = true; error.value = ''; reorderError.value = ''
  try {
    reorder.value = await call('orders.reorder_preview', { order: order.name })
    await nextTick()
    reorderDialog.value.showModal()
  } catch (e) { error.value = e.message }
  finally { reorderBusy.value = false }
}
function confirmReorder() {
  try {
    if (sessionStorage.getItem(`lc-delivery:${session.value.user}:${reorder.value.shop}`)) {
      reorderError.value = 'Your last order request is not confirmed. Open this shop and resolve it before replacing your cart.'
      return
    }
    const cart = Object.fromEntries(reorder.value.items.map(item => [item.item, item]))
    writeCart(localStorage, reorder.value.shop, cart)
    reorderDialog.value.close()
    router.push({ name: 'customer-shop', params: { shop: reorder.value.shop }, query: { cart: '1' } })
  } catch { reorderError.value = 'Your cart could not be saved. Please try again.' }
}
const props = defineProps({ shop: { type: String, default: '' }, editable: Boolean })
const deliveryTab = computed(() => route.query.order_type === 'scheduled' ? 'Scheduled' : 'Normal')
function selectDeliveryTab(mode) {
  if (busy.value || mode === deliveryTab.value) return
  router.replace({ query: { ...route.query, order_type: mode.toLowerCase() } })
}
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
    const focusedOrder = !props.shop && typeof route.query.order === 'string' ? route.query.order : ''
    const requests = [focusedOrder ? call('orders.detail', { order: focusedOrder }).then(order => [order]) : call('orders.list_orders', { ...(props.shop ? { shop: props.shop, delivery_mode: deliveryTab.value } : {}), start: start.value })]
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
function refreshOrders() { load() }
watch(() => [props.shop, props.shop ? deliveryTab.value : null, route.query.order], () => { start.value = 0; orders.value = []; load() }, { immediate: true })
onMounted(() => {
  window.addEventListener('lc-orders-change', refreshOrders)
  refreshTimer = window.setInterval(() => { if (!props.shop && !loading.value && !busy.value && orders.value.some(order => !['Delivered', 'Cancelled'].includes(order.status))) load() }, 10000)
})
onBeforeUnmount(() => {
  window.removeEventListener('lc-orders-change', refreshOrders)
  window.clearInterval(refreshTimer)
})
</script>

<template>
  <AuthChoices v-if="session.user === 'Guest'" />
  <section v-else class="orders-page">
    <div class="inventory-heading"><div><span class="eyebrow">DELIVERY ORDERS</span><h2>{{ shop ? 'Your orders' : 'My orders' }}</h2><p>{{ shop ? 'Prepare each order, assign a rider, and follow it through delivery.' : 'Track every step from shop confirmation to delivery.' }}</p></div><button :disabled="loading || busy" @click="load()">Refresh orders</button></div>
    <div v-if="shop" class="shop-order-tabs" role="group" aria-label="Delivery booking type">
      <button v-for="mode in ['Normal', 'Scheduled']" :key="mode" type="button" :class="{ active: deliveryTab === mode }" :aria-pressed="deliveryTab === mode" :disabled="busy" @click="selectDeliveryTab(mode)"><strong>{{ mode }} orders</strong><small>{{ mode === 'Normal' ? 'Individual deliveries' : 'Time slots & delivery batches' }}</small></button>
    </div>
    <template v-if="shop && deliveryTab === 'Scheduled'"><slot name="batches" :refresh="load" /><p class="muted">Accept each request below, then manage preparation and dispatch together using the batch controls.</p></template>
    <p v-if="error" class="lc-notice" role="alert">{{ error }}</p>
    <p v-if="loading" role="status">Loading orders…</p>
    <p v-else-if="!orders.length" class="lc-empty">{{ shop ? `No ${deliveryTab.toLowerCase()} orders yet.` : 'No delivery orders yet.' }}</p>
    <article v-for="order in orders" :key="order.name" class="order-card">
      <OrderReference :order-id="order.name" />
      <div class="workspace-heading"><div><span class="eyebrow">{{ order.shop_name }}</span><h3>{{ order.recipient }}</h3><small>{{ order.created }}</small></div><span class="status-pill">{{ order.status }}</span></div>
      <p v-if="order.scheduled_period" class="lc-notice">Scheduled · {{ order.scheduled_period.title }} · {{ order.scheduled_period.delivery_start }} – {{ order.scheduled_period.delivery_end }} · Free delivery</p><div class="delivery-progress" :aria-label="`Order status: ${order.status}`"><span v-for="step in steps" :key="step" :class="{ complete: steps.indexOf(step) <= steps.indexOf(order.status) }">{{ step }}</span></div>
      <ul><li v-for="(item, index) in order.items" :key="index">{{ item.quantity }} {{ item.uom }} · {{ item.name }} <strong>{{ money(item.amount, order.currency) }}</strong><small v-if="order.selling_lines?.[index]?.option_id" class="order-option-summary">{{ order.selling_lines[index].label }} × {{ order.selling_lines[index].packs }} · {{ order.selling_lines[index].preweighed ? `Pack weight ${order.selling_lines[index].actual_weight} kg` : order.selling_lines[index].actual_weight == null ? `Estimated stock weight ${order.selling_lines[index].estimated_weight} kg` : `Actual packed weight ${order.selling_lines[index].actual_weight} kg` }}</small></li></ul>
      <p><strong>{{ order.estimated ? 'Estimated total' : 'Order total' }} {{ money(order.total, order.currency) }}</strong><br><small>Includes {{ money(order.taxes_and_charges, order.currency) }} in configured taxes and delivery charges.</small></p>
      <ManualUpiPayment :order="order" :editable="!!shop && editable" @updated="load" />
      <p class="payment-summary"><span><small>PAYMENT METHOD</small><strong>{{ order.payment_method }}</strong></span><span><small>PAYMENT STATUS</small><strong :class="{ paid: ['Reconciled', 'Paid'].includes(order.payment_status) }">{{ order.payment_status }}</strong></span></p>
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
      <button v-if="!shop && ['Delivered', 'Cancelled'].includes(order.status)" type="button" class="reorder-button" :disabled="reorderBusy" aria-haspopup="dialog" @click="reviewReorder(order)">{{ reorderBusy ? 'Checking items…' : 'Order again ↗' }}</button>
      <div v-if="shop && editable && order.status === 'Ready'" class="driver-assignment">
        <label>Delivery person<select v-model="selectedDrivers[order.name]" :disabled="busy || !drivers.length"><option value="" disabled>Select a rider</option><option v-for="driver in drivers" :key="driver.user" :value="driver.user">{{ driver.full_name }}</option></select></label>
        <button class="lc-primary" :disabled="busy || !selectedDrivers[order.name] || selectedDrivers[order.name] === order.delivery_user" @click="assign(order)">{{ order.delivery_user ? 'Reassign rider' : 'Assign rider' }}</button>
        <small v-if="!drivers.length">No delivery people are assigned to this shop. A platform administrator can add a Delivery Person membership in Desk.</small>
      </div>
      <div v-if="(shop && editable) || (!shop && order.status === 'Requested')" class="order-actions">
        <button v-if="shop && next[order.status]" class="lc-primary" :disabled="busy" @click="change(order, next[order.status])">{{ nextLabel[order.status] }}</button>
        <details v-if="cancellable.has(order.status)"><summary>Cancel order</summary><label>Reason<input v-model="reasons[order.name]" minlength="3" maxlength="500"></label><button :disabled="busy || (reasons[order.name] || '').trim().length < 3" @click="change(order, 'Cancelled')">Confirm cancellation</button></details>
      </div>
    </article>
    <dialog ref="reorderDialog" class="reorder-dialog" aria-labelledby="reorder-title">
      <template v-if="reorder"><span class="eyebrow">{{ reorder.shop_name }}</span><h2 id="reorder-title">Order your favourites again</h2><p>Current prices and stock are shown below. This replaces the cart for this shop. Delivery charges and taxes are calculated at checkout.</p><ul v-if="reorder.notices.length" class="reorder-notices"><li v-for="notice in reorder.notices" :key="notice">{{ notice }}</li></ul><div class="reorder-lines"><article v-for="item in reorder.items" :key="item.item"><img v-if="item.image" :src="item.image" :alt="item.item_name"><div><strong>{{ item.item_name }}</strong><small>{{ item.quantity }} {{ item.uom }}</small></div><strong>{{ money(item.rate * item.quantity, item.currency) }}</strong></article></div><p v-if="!reorder.items.length">These items are currently unavailable. Browse the shop for alternatives.</p><p v-if="reorderError" role="alert" class="lc-notice">{{ reorderError }}</p><div class="logout-actions"><button type="button" autofocus @click="reorderDialog.close()">Cancel</button><button v-if="reorder.items.length" type="button" class="lc-primary" @click="confirmReorder">Review cart →</button><RouterLink v-else :to="{ name: 'customer-shop', params: { shop: reorder.shop } }" class="primary" @click="reorderDialog.close()">Browse shop →</RouterLink></div></template>
    </dialog>
    <RouterLink v-if="!shop && route.query.order" to="/orders">View all orders →</RouterLink>
    <div v-else class="lc-pagination"><button :disabled="!start || loading || busy" @click="load(-20)">Previous</button><span>Page {{ start / 20 + 1 }}</span><button :disabled="orders.length < 20 || loading || busy" @click="load(20)">Next</button></div>
  </section>
</template>
