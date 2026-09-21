<script setup>
import { computed, inject, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { call } from './api.js'
import MapView from './MapView.vue'
import ScheduledRoute from './ScheduledRoute.vue'
import { forgetTracking, rememberTracking, savedTracking } from './tracking.js'

const session = inject('session')
const batchSlots = ref([])
async function openBatchOrder(name) {
  try { const order = await call('orders.detail', { order: name }); assignments.value = [order, ...assignments.value.filter(row => row.name !== name)]; await nextTick(); document.getElementById(`delivery-${name}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' }) } catch(e) { error.value = e.message }
}
const profile = ref(null), assignments = ref([]), view = ref('active'), start = ref(0)
const loading = ref(false), error = ref(''), busyOrder = ref('')
const paymentDialog = ref(null), collectingOrder = ref(null)
const collectedAmount = ref(''), collectionNote = ref(''), collectionError = ref('')
const deliveryOtp = ref('')
const trackingOrder = ref(''), locationMessage = ref(''), locationError = ref('')
const routes = ref({}), routeErrors = ref({})
const routeRequests = new Set()
let locationWatch = null, locationTimer = null, latestPosition = null, sendingLocation = false
const allowed = computed(() => session.value.roles.includes('LC Delivery Person') && session.value.memberships.some(member => member.membership_role === 'Delivery Person'))
const collectionVariance = computed(() => collectingOrder.value ? Number(collectedAmount.value || 0) - Number(collectingOrder.value.total) : 0)
const next = { Ready: 'Picked Up', 'Picked Up': 'Out for Delivery', 'Out for Delivery': 'Delivered' }
const labels = { Ready: 'Confirm pickup', 'Picked Up': 'Start delivery', 'Out for Delivery': 'Confirm delivered' }

function money(value, currency) { return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(value) }
function orderLabel(value) { const name = String(value || ''); return name.length > 12 ? `#${name.slice(0, 8).toUpperCase()}` : name }
function deliveredAt(value) { return value ? String(value).split('.')[0].replace(' ', ' · ') : '' }
function mapPoints(order) {
  const points = []
  if (order.shop_location) points.push({ ...order.shop_location, kind: 'shop', label: order.shop_name })
  if (order.destination_location) points.push({ ...order.destination_location, kind: 'customer', label: order.recipient })
  if (order.driver_location) points.push({ ...order.driver_location, kind: 'rider', label: 'Your live location' })
  return points
}
function navigationLink(order) {
  const target = order.status === 'Ready' ? order.shop_location : order.destination_location
  if (!target) return '#'
  return `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(`${target.latitude},${target.longitude}`)}&travelmode=driving&dir_action=navigate`
}
async function ensureRoute(order) {
  if (!['Picked Up', 'Out for Delivery'].includes(order.status) || routes.value[order.name] || routeErrors.value[order.name] || routeRequests.has(order.name)) return
  routeRequests.add(order.name)
  try {
    const result = await call('orders.delivery_route', { order: order.name })
    routes.value = { ...routes.value, [order.name]: result }
    const currentErrors = { ...routeErrors.value }; delete currentErrors[order.name]; routeErrors.value = currentErrors
  } catch (e) { routeErrors.value = { ...routeErrors.value, [order.name]: e.message } }
  finally { routeRequests.delete(order.name) }
}
function loadRoutes(rows) { for (const order of rows) ensureRoute(order) }
async function load(delta = 0) {
  if (!allowed.value) return false
  start.value = Math.max(0, start.value + delta); loading.value = true; error.value = ''
  try {
    assignments.value = await call('orders.delivery_assignments', { start: start.value, view: view.value })
    batchSlots.value = view.value === 'active' ? (await call('scheduled.rider_batches')).map(row => row.scheduled_slot) : []
    loadRoutes(assignments.value)
    return true
  } catch (e) { error.value = e.message; return false }
  finally { loading.value = false }
}
async function loadProfile() {
  if (!allowed.value) return
  try { profile.value = await call('orders.delivery_profile') }
  catch (e) { error.value = e.message }
}
async function refresh() { await Promise.all([load(), loadProfile()]) }
async function switchView(target) { view.value = target; start.value = 0; await load() }
async function advance(order, payment = {}, showCollectionError = false) {
  busyOrder.value = order.name; error.value = ''
  try {
    const target = next[order.status]
    const result = await call('orders.delivery_change', { order: order.name, target, ...payment }, true)
    if (target === 'Delivered' && trackingOrder.value === order.name) stopTracking('Location sharing stopped after delivery.')
    await refresh()
    return result
  } catch (e) {
    if (showCollectionError) collectionError.value = e.message
    else error.value = e.message
    return null
  }
  finally { busyOrder.value = '' }
}
function stopTracking(message = 'Live location sharing stopped.', clearSaved = true) {
  if (locationWatch != null) navigator.geolocation.clearWatch(locationWatch)
  if (locationTimer != null) window.clearInterval(locationTimer)
  locationWatch = null; locationTimer = null; latestPosition = null
  trackingOrder.value = ''; locationMessage.value = message; sendingLocation = false
  if (clearSaved) forgetTracking(window.localStorage, session.value.user)
}
async function sendLocation(order, position) {
  if (!position || sendingLocation || trackingOrder.value !== order.name) return
  if (Date.now() - position.timestamp > 30000) { locationMessage.value = 'Waiting for a fresh GPS position…'; return }
  if (position.coords.accuracy > 5000) { locationMessage.value = ''; locationError.value = 'GPS is too approximate to share. Enable precise location and move outdoors. Tracking will retry automatically.'; return }
  sendingLocation = true
  try {
    const result = await call('orders.update_driver_location', { order: order.name, latitude: position.coords.latitude, longitude: position.coords.longitude, accuracy: position.coords.accuracy || 0 }, true)
    if (trackingOrder.value !== order.name) return
    if (result.accepted) {
      const current = assignments.value.find(row => row.name === order.name)
      locationMessage.value = 'Location shared with the customer · updating every 12 seconds.'; locationError.value = ''
      if (current) current.driver_location = { latitude: result.latitude, longitude: result.longitude, accuracy: result.accuracy, updated_at: result.updated_at }
    }
  } catch (e) { locationMessage.value = ''; locationError.value = e.message }
  finally { sendingLocation = false }
}
function startTracking(order, initialPosition = null) {
  locationError.value = ''; locationMessage.value = ''
  if (!window.isSecureContext) { locationError.value = 'Live GPS needs HTTPS. Ask the administrator to enable HTTPS for this site.'; return }
  if (!navigator.geolocation) { locationError.value = 'This device does not provide browser location.'; return }
  if (locationWatch != null || locationTimer != null) stopTracking('')
  trackingOrder.value = order.name
  rememberTracking(window.localStorage, session.value.user, order.name)
  latestPosition = initialPosition
  locationMessage.value = 'Finding your GPS position… Keep this page open.'
  if (latestPosition) sendLocation(order, latestPosition)
  locationWatch = navigator.geolocation.watchPosition(position => {
    latestPosition = position
    sendLocation(order, position)
  }, error => {
    if (error.code === 1) {
      stopTracking('', false)
      locationError.value = 'Location permission is blocked. Allow precise location, then tap Resume live tracking.'
    } else {
      locationMessage.value = 'Waiting for GPS signal… Tracking is still on.'
      locationError.value = 'Keep this page open and move outdoors. GPS will retry automatically.'
    }
  }, { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 })
  locationTimer = window.setInterval(() => sendLocation(order, latestPosition), 12000)
}
function getCurrentPosition() {
  return new Promise((resolve, reject) => navigator.geolocation.getCurrentPosition(resolve, reject, { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 }))
}
async function beginDelivery(order) {
  locationError.value = ''; locationMessage.value = 'Checking your live location…'; busyOrder.value = order.name
  if (!window.isSecureContext || !navigator.geolocation) { busyOrder.value = ''; startTracking(order); return }
  try {
    const position = await getCurrentPosition()
    const updated = await advance(order)
    if (updated?.status === 'Out for Delivery') startTracking(updated, position)
    else locationMessage.value = ''
  } catch { busyOrder.value = ''; locationMessage.value = ''; locationError.value = 'Allow precise location to start delivery and share the bike position with the customer.' }
}
function requestAdvance(order) {
  if (order.status === 'Picked Up' && order.live_tracking_enabled) { beginDelivery(order); return }
  if (order.status !== 'Out for Delivery') { advance(order); return }
  collectingOrder.value = order
  collectedAmount.value = String(order.total)
  collectionNote.value = ''
  deliveryOtp.value = ''
  collectionError.value = ''
  paymentDialog.value.showModal()
}
function cancelCollection() { paymentDialog.value.close(); collectingOrder.value = null; collectionNote.value = ''; deliveryOtp.value = ''; collectionError.value = '' }
async function confirmCollection() {
  const order = collectingOrder.value
  const amount = Number(collectedAmount.value)
  if (!Number.isFinite(amount) || amount < 0) { collectionError.value = 'Enter the cash amount you received.'; return }
  if (collectionVariance.value !== 0 && collectionNote.value.trim().length < 3) { collectionError.value = 'Add a short note explaining the cash difference.'; return }
  if (!/^\d{6}$/.test(deliveryOtp.value)) { collectionError.value = 'Enter the six-digit OTP shown on the customer’s order.'; return }
  collectionError.value = ''
  const result = await advance(order, { collected_amount: amount, note: collectionNote.value.trim(), delivery_otp: deliveryOtp.value }, true)
  if (!result) return
  paymentDialog.value.close()
  collectingOrder.value = null
  collectionNote.value = ''
  deliveryOtp.value = ''
}
async function initialize() {
  const [loaded] = await Promise.all([load(), loadProfile()])
  if (!loaded) return
  const savedOrder = savedTracking(window.localStorage, session.value.user)
  if (!savedOrder) return
  let order = assignments.value.find(row => row.name === savedOrder)
  if (!order) {
    try { order = await call('orders.detail', { order: savedOrder }) }
    catch (e) { locationError.value = `Live tracking could not resume: ${e.message}`; return }
  }
  if (order.status === 'Out for Delivery' && order.live_tracking_enabled) startTracking(order)
  else forgetTracking(window.localStorage, session.value.user)
}
onMounted(initialize)
onBeforeUnmount(() => stopTracking('', false))
</script>

<template>
  <section v-if="!allowed" class="lc-empty delivery-empty"><h2>Delivery access is not configured</h2><p>Your account needs the LC Delivery Person role and an enabled Delivery Person membership for a shop.</p></section>
  <section v-else class="delivery-page">
    <header class="delivery-hero"><div><span class="eyebrow">RIDER WORKSPACE</span><h1>Hello, {{ session.full_name.split(' ')[0] }}.</h1><p>Your profile, assigned shops, and every delivery in one place.</p></div><div class="rider-avatar" aria-hidden="true">{{ session.full_name.slice(0, 1).toUpperCase() }}</div></header>

    <div class="rider-dashboard-grid">
      <aside class="rider-profile-card">
        <div class="profile-avatar"><img v-if="profile?.profile.user_image" :src="profile.profile.user_image" :alt="`${profile.profile.full_name} profile`"><span v-else aria-hidden="true">{{ session.full_name.slice(0, 1).toUpperCase() }}</span></div>
        <span class="online-badge">● Ready for delivery</span>
        <h2>{{ profile?.profile.full_name || session.full_name }}</h2>
        <p class="profile-role">Delivery person</p>
        <dl class="profile-details">
          <div><dt>Email</dt><dd>{{ profile?.profile.email || session.user }}</dd></div>
          <div><dt>Mobile</dt><dd>{{ profile?.profile.mobile_no || 'Not added' }}</dd></div>
        </dl>
        <div class="assigned-shops"><span class="eyebrow">ASSIGNED SHOPS</span><p v-if="!profile?.shops.length">No enabled shops</p><span v-for="shop in profile?.shops || []" :key="shop.name" class="shop-chip">{{ shop.shop_name }} <small>{{ shop.status }}</small></span></div>
        <small class="profile-note">Your contact details come from your login account.</small>
      </aside>

      <div class="rider-workspace">
        <div class="rider-metrics">
          <div><span>ACTIVE</span><strong>{{ profile?.metrics.active ?? '—' }}</strong><small>to complete</small></div>
          <div><span>DELIVERED</span><strong>{{ profile?.metrics.delivered ?? '—' }}</strong><small>successful</small></div>
          <div><span>CASH HANDOVER</span><strong>{{ profile?.metrics.awaiting_handover ?? '—' }}</strong><small>waiting for shop</small></div>
          <div><span>SHOPS</span><strong>{{ profile?.metrics.shops ?? '—' }}</strong><small>connected</small></div>
        </div>
        <div v-if="profile?.cash_pending.length" class="rider-cash-summary"><div><span aria-hidden="true">₹</span><div><strong>Cash to hand over</strong><small>Give each amount to its shop owner.</small></div></div><div class="rider-cash-lines"><p v-for="cash in profile.cash_pending" :key="`${cash.shop}:${cash.currency}`"><small>{{ cash.shop_name }}</small>{{ money(cash.amount, cash.currency) }}</p></div></div>

        <div class="delivery-section-heading"><div><span class="eyebrow">YOUR ROUTE</span><h2>{{ view === 'active' ? 'Active deliveries' : 'Delivery history' }}</h2></div><button :disabled="loading || busyOrder" @click="refresh">Refresh</button></div>
        <div class="delivery-tabs" role="tablist" aria-label="Delivery lists"><button role="tab" :aria-selected="view === 'active'" @click="switchView('active')">Active <span>{{ profile?.metrics.active || 0 }}</span></button><button role="tab" :aria-selected="view === 'history'" @click="switchView('history')">History <span>{{ profile?.metrics.delivered || 0 }}</span></button></div>
        <p v-if="error" class="lc-notice" role="alert">{{ error }}</p>
        <p v-if="loading" role="status">Loading your deliveries…</p>
        <p v-else-if="!assignments.length" class="lc-empty">{{ view === 'active' ? 'No active deliveries right now.' : 'No completed deliveries yet.' }}</p>
        <div v-else class="delivery-list">
          <ScheduledRoute v-for="slot in batchSlots" :key="slot" :slot-name="slot" manageable @open-order="openBatchOrder" /><article v-for="order in assignments" :id="`delivery-${order.name}`" :key="order.name" class="delivery-card" :class="{ finished: ['Delivered', 'Cancelled'].includes(order.status) }">
            <header><div><span class="eyebrow" :title="order.name">{{ order.shop_name }} · {{ orderLabel(order.name) }}</span><h2>{{ order.recipient }}</h2></div><span class="status-pill">{{ order.status }}</span></header>
            <div class="delivery-address"><span aria-hidden="true">⌖</span><div><strong>{{ order.address.line1 }}</strong><p>{{ order.address.city }} · {{ order.address.postal_code }}</p><a :href="`tel:${order.phone}`">Call {{ order.phone }}</a></div></div>
            <div v-if="order.destination_location" class="delivery-map-panel"><MapView :config="order.map" :points="mapPoints(order)" :route="routes[order.name]?.points || []" height="235px" /><div class="map-legend"><span><i class="legend-shop"></i>Shop</span><span><i class="legend-customer"></i>Customer</span><span v-if="order.driver_location"><i class="legend-rider"></i>You</span><span v-if="routes[order.name]" class="route-summary">{{ routes[order.name].distance_km }} km · about {{ routes[order.name].duration_minutes }} min</span><a :href="navigationLink(order)" target="_blank" rel="noopener">{{ order.status === 'Ready' ? 'Navigate to shop' : 'Start navigation' }} ↗</a></div><small v-if="routes[order.name]" class="route-attribution"><a :href="routes[order.name].attribution_url" target="_blank" rel="noopener">{{ routes[order.name].attribution }}</a></small><p v-if="routeErrors[order.name]" class="route-error">{{ routeErrors[order.name] }}</p></div>
            <p v-if="order.delivery_instructions" class="delivery-instructions"><strong>Delivery note</strong>{{ order.delivery_instructions }}</p>
            <details><summary>{{ order.items.length }} product{{ order.items.length === 1 ? '' : 's' }} · {{ money(order.total, order.currency) }}</summary><ul><li v-for="(item, index) in order.items" :key="index">{{ item.quantity }} {{ item.uom }} · {{ item.name }}</li></ul></details>
            <div v-if="order.status === 'Out for Delivery' && order.live_tracking_enabled" class="tracking-controls"><button v-if="trackingOrder !== order.name" type="button" @click="startTracking(order)">Resume live tracking</button><button v-else type="button" class="tracking-stop" @click="stopTracking()">Stop sharing</button><small>Your bike updates for the customer every 12 seconds and is removed after delivery.</small></div>
            <button v-if="next[order.status]" class="delivery-action" :disabled="!!busyOrder" @click="requestAdvance(order)">{{ busyOrder === order.name ? 'Updating…' : order.status === 'Out for Delivery' ? 'Collect cash & confirm delivered' : labels[order.status] }} <span>›</span></button>
            <p v-else-if="order.status === 'Delivered'" class="delivery-complete">✓ Delivered · Cash {{ order.payment_status === 'Reconciled' ? 'handed over' : 'awaiting handover' }}{{ order.delivered_at ? ` · ${deliveredAt(order.delivered_at)}` : '' }}</p>
            <p v-else-if="order.status === 'Cancelled'" class="muted">This order was cancelled.</p>
          </article>
        </div>
        <p v-if="locationMessage" class="success-note" role="status">{{ locationMessage }}</p><p v-if="locationError" class="lc-notice" role="alert">{{ locationError }}</p>
        <div class="lc-pagination"><button :disabled="!start || loading || busyOrder" @click="load(-20)">Previous</button><span>Page {{ start / 20 + 1 }}</span><button :disabled="assignments.length < 20 || loading || busyOrder" @click="load(20)">Next</button></div>
      </div>
    </div>
    <dialog ref="paymentDialog" class="payment-dialog" aria-labelledby="payment-title">
      <div class="cash-symbol" aria-hidden="true">₹</div><span class="eyebrow">CASH ON DELIVERY</span><h2 id="payment-title">Confirm cash collection</h2>
      <p v-if="collectingOrder">Collect <strong>{{ money(collectingOrder.total, collectingOrder.currency) }}</strong> from {{ collectingOrder.recipient }} before completing this delivery.</p>
      <label class="cash-field">Cash received<input v-model="collectedAmount" type="number" min="0" step="0.01" inputmode="decimal" required></label>
      <p v-if="collectingOrder && collectionVariance" class="variance-note" :class="{ shortage: collectionVariance < 0 }">{{ collectionVariance < 0 ? 'Short' : 'Extra' }} by {{ money(Math.abs(collectionVariance), collectingOrder.currency) }}</p>
      <label v-if="collectionVariance" class="cash-field">Reason for difference<textarea v-model="collectionNote" maxlength="500" placeholder="Explain why the amount is different" required></textarea></label>
      <label class="cash-field delivery-otp-field">Customer delivery OTP<input v-model="deliveryOtp" type="text" inputmode="numeric" autocomplete="one-time-code" maxlength="6" pattern="[0-9]{6}" placeholder="000000" required @input="deliveryOtp = deliveryOtp.replace(/\D/g, '').slice(0, 6)"><small>Ask the customer for the code shown in My orders. It is not sent by email.</small></label>
      <p v-if="collectionError" class="lc-notice" role="alert">{{ collectionError }}</p>
      <p class="muted">The shop owner will confirm your cash handover later. This step records the amount you received and submits the Sales Invoice.</p>
      <div class="logout-actions"><button :disabled="!!busyOrder" @click="cancelCollection">Go back</button><button class="logout-confirm" :disabled="!!busyOrder" @click="confirmCollection">{{ busyOrder ? 'Verifying…' : 'Verify OTP & deliver' }}</button></div>
    </dialog>
  </section>
</template>
