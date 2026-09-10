<script setup>
import { computed, inject, onBeforeUnmount, onMounted, ref } from 'vue'
import { call } from './api.js'
import MapView from './MapView.vue'

const session = inject('session')
const profile = ref(null), assignments = ref([]), view = ref('active'), start = ref(0)
const loading = ref(false), error = ref(''), busyOrder = ref('')
const paymentDialog = ref(null), collectingOrder = ref(null)
const collectedAmount = ref(''), collectionNote = ref(''), collectionError = ref('')
const trackingOrder = ref(''), locationMessage = ref(''), locationError = ref('')
const manualLocations = ref({})
let locationWatch = null, sendingLocation = false, lastLocationSent = 0
const allowed = computed(() => session.value.roles.includes('LC Delivery Person') && session.value.memberships.some(member => member.membership_role === 'Driver'))
const collectionVariance = computed(() => collectingOrder.value ? Number(collectedAmount.value || 0) - Number(collectingOrder.value.total) : 0)
const next = { Ready: 'Picked Up', 'Picked Up': 'Out for Delivery', 'Out for Delivery': 'Delivered' }
const labels = { Ready: 'Confirm pickup', 'Picked Up': 'Start delivery', 'Out for Delivery': 'Confirm delivered' }

function money(value, currency) { return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(value) }
function mapPoints(order) {
  const points = []
  if (order.shop_location) points.push({ ...order.shop_location, kind: 'shop', label: order.shop_name })
  if (order.destination_location) points.push({ ...order.destination_location, kind: 'customer', label: order.recipient })
  if (order.driver_location) points.push({ ...order.driver_location, kind: 'rider', label: 'Your live location' })
  return points
}
function mapLink(location) { return `https://www.openstreetmap.org/?mlat=${encodeURIComponent(location.latitude)}&mlon=${encodeURIComponent(location.longitude)}#map=18/${encodeURIComponent(location.latitude)}/${encodeURIComponent(location.longitude)}` }
async function load(delta = 0) {
  if (!allowed.value) return
  start.value = Math.max(0, start.value + delta); loading.value = true; error.value = ''
  try {
    assignments.value = await call('orders.delivery_assignments', { start: start.value, view: view.value })
    for (const order of assignments.value) {
      if (!manualLocations.value[order.name]) manualLocations.value[order.name] = { latitude: '', longitude: '' }
    }
  }
  catch (e) { error.value = e.message }
  finally { loading.value = false }
}
async function loadProfile() {
  if (!allowed.value) return
  try { profile.value = await call('orders.delivery_profile') }
  catch (e) { error.value = e.message }
}
async function refresh() { await Promise.all([load(), loadProfile()]) }
async function switchView(target) { view.value = target; start.value = 0; await load() }
async function advance(order, payment = {}) {
  busyOrder.value = order.name; error.value = ''
  try {
    await call('orders.delivery_change', { order: order.name, target: next[order.status], ...payment }, true)
    if (next[order.status] === 'Delivered' && trackingOrder.value === order.name) stopTracking('Location sharing stopped after delivery.')
    await refresh()
  } catch (e) { error.value = e.message }
  finally { busyOrder.value = '' }
}
function stopTracking(message = 'Live location sharing stopped.') {
  if (locationWatch != null) navigator.geolocation.clearWatch(locationWatch)
  locationWatch = null; trackingOrder.value = ''; locationMessage.value = message; sendingLocation = false
}
function startTracking(order) {
  locationError.value = ''; locationMessage.value = ''
  if (!window.isSecureContext) { locationError.value = 'Live GPS needs HTTPS. Ask the administrator to enable HTTPS for this site.'; return }
  if (!navigator.geolocation) { locationError.value = 'This device does not provide browser location.'; return }
  if (trackingOrder.value && trackingOrder.value !== order.name) stopTracking('')
  trackingOrder.value = order.name
  locationWatch = navigator.geolocation.watchPosition(async position => {
    const now = Date.now()
    if (sendingLocation || now - lastLocationSent < 7000) return
    sendingLocation = true; lastLocationSent = now
    try {
      await call('orders.update_driver_location', { order: order.name, latitude: position.coords.latitude, longitude: position.coords.longitude, accuracy: position.coords.accuracy || 0 }, true)
      locationMessage.value = 'Live location shared just now.'; locationError.value = ''
      const current = assignments.value.find(row => row.name === order.name)
      if (current) current.driver_location = { latitude: position.coords.latitude, longitude: position.coords.longitude, accuracy: position.coords.accuracy || 0, updated_at: new Date().toISOString() }
    } catch (e) { locationError.value = e.message }
    finally { sendingLocation = false }
  }, () => { locationError.value = 'Location access failed. Allow precise location in your browser and try again.'; stopTracking('') }, { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 })
}
async function shareManualLocation(order) {
  const location = manualLocations.value[order.name]
  locationError.value = ''; locationMessage.value = ''
  if (!location || !Number.isFinite(Number(location.latitude)) || !Number.isFinite(Number(location.longitude)) || location.latitude === '' || location.longitude === '') { locationError.value = 'Enter valid latitude and longitude.'; return }
  busyOrder.value = order.name
  try {
    const saved = await call('orders.update_driver_location', { order: order.name, latitude: location.latitude, longitude: location.longitude, accuracy: 0 }, true)
    order.driver_location = { latitude: Number(location.latitude), longitude: Number(location.longitude), accuracy: 0, updated_at: saved.updated_at }
    locationMessage.value = 'Manual rider location shared with the customer.'
  } catch (e) { locationError.value = e.message }
  finally { busyOrder.value = '' }
}
function requestAdvance(order) {
  if (order.status !== 'Out for Delivery') { advance(order); return }
  collectingOrder.value = order
  collectedAmount.value = String(order.total)
  collectionNote.value = ''
  collectionError.value = ''
  paymentDialog.value.showModal()
}
function cancelCollection() { paymentDialog.value.close(); collectingOrder.value = null; collectionNote.value = ''; collectionError.value = '' }
async function confirmCollection() {
  const order = collectingOrder.value
  const amount = Number(collectedAmount.value)
  if (!Number.isFinite(amount) || amount < 0) { collectionError.value = 'Enter the cash amount you received.'; return }
  if (collectionVariance.value !== 0 && collectionNote.value.trim().length < 3) { collectionError.value = 'Add a short note explaining the cash difference.'; return }
  paymentDialog.value.close()
  collectingOrder.value = null
  await advance(order, { collected_amount: amount, note: collectionNote.value.trim() })
}
onMounted(refresh)
onBeforeUnmount(() => stopTracking(''))
</script>

<template>
  <section v-if="!allowed" class="lc-empty delivery-empty"><h2>Delivery access is not configured</h2><p>Your account needs the LC Delivery Person role and an enabled Driver membership for a shop.</p></section>
  <section v-else class="delivery-page">
    <header class="delivery-hero"><div><span class="eyebrow">RIDER WORKSPACE</span><h1>Hello, {{ session.full_name.split(' ')[0] }}.</h1><p>Your profile, assigned shops, and every delivery in one place.</p></div><div class="rider-avatar" aria-hidden="true">{{ session.full_name.slice(0, 1).toUpperCase() }}</div></header>

    <div class="rider-dashboard-grid">
      <aside class="rider-profile-card">
        <div class="profile-avatar"><img v-if="profile?.profile.user_image" :src="profile.profile.user_image" :alt="`${profile.profile.full_name} profile`"><span v-else aria-hidden="true">{{ session.full_name.slice(0, 1).toUpperCase() }}</span></div>
        <span class="online-badge">● Ready for delivery</span>
        <h2>{{ profile?.profile.full_name || session.full_name }}</h2>
        <p class="profile-role">Delivery partner</p>
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
          <article v-for="order in assignments" :key="order.name" class="delivery-card" :class="{ finished: ['Delivered', 'Cancelled'].includes(order.status) }">
            <header><div><span class="eyebrow">{{ order.shop_name }} · {{ order.name }}</span><h2>{{ order.recipient }}</h2></div><span class="status-pill">{{ order.status }}</span></header>
            <div class="delivery-address"><span aria-hidden="true">⌖</span><div><strong>{{ order.address.line1 }}</strong><p>{{ order.address.city }} · {{ order.address.postal_code }}</p><a :href="`tel:${order.phone}`">Call {{ order.phone }}</a></div></div>
            <div v-if="order.destination_location" class="delivery-map-panel"><MapView :config="order.map" :points="mapPoints(order)" height="235px" /><div class="map-legend"><span><i class="legend-shop"></i>Shop</span><span><i class="legend-customer"></i>Customer</span><span v-if="order.driver_location"><i class="legend-rider"></i>You</span><a :href="mapLink(order.destination_location)" target="_blank" rel="noopener">Open destination ↗</a></div></div>
            <p v-if="order.delivery_instructions" class="delivery-instructions"><strong>Delivery note</strong>{{ order.delivery_instructions }}</p>
            <details><summary>{{ order.items.length }} product{{ order.items.length === 1 ? '' : 's' }} · {{ money(order.total, order.currency) }}</summary><ul><li v-for="(item, index) in order.items" :key="index">{{ item.quantity }} {{ item.uom }} · {{ item.name }}</li></ul></details>
            <div v-if="order.status === 'Out for Delivery' && order.live_tracking_enabled" class="tracking-controls"><button v-if="trackingOrder !== order.name" type="button" @click="startTracking(order)">Share live location</button><button v-else type="button" class="tracking-stop" @click="stopTracking()">Stop sharing</button><small>Location is visible only to this customer and is removed after delivery.</small></div>
            <div v-if="order.status === 'Out for Delivery' && order.live_tracking_enabled && manualLocations[order.name]" class="manual-rider-location"><strong>Enter location manually</strong><div class="manual-coordinate-fields"><label>Latitude<input v-model.number="manualLocations[order.name].latitude" type="number" min="-90" max="90" step="0.000001" inputmode="decimal" placeholder="15.490900"></label><label>Longitude<input v-model.number="manualLocations[order.name].longitude" type="number" min="-180" max="180" step="0.000001" inputmode="decimal" placeholder="73.827800"></label></div><button type="button" :disabled="!!busyOrder" @click="shareManualLocation(order)">Update customer map</button><small>Use this HTTP testing option until the site has HTTPS for automatic GPS.</small></div>
            <button v-if="next[order.status]" class="delivery-action" :disabled="!!busyOrder" @click="requestAdvance(order)">{{ busyOrder === order.name ? 'Updating…' : order.status === 'Out for Delivery' ? 'Collect cash & confirm delivered' : labels[order.status] }} <span>›</span></button>
            <p v-else-if="order.status === 'Delivered'" class="delivery-complete">✓ Delivered · Cash {{ order.payment_status === 'Reconciled' ? 'handed over' : 'awaiting handover' }}{{ order.delivered_at ? ` · ${order.delivered_at}` : '' }}</p>
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
      <p v-if="collectionError" class="lc-notice" role="alert">{{ collectionError }}</p>
      <p class="muted">The shop owner will confirm your cash handover later. This step records the amount you received and submits the Sales Invoice.</p>
      <div class="logout-actions"><button @click="cancelCollection">Go back</button><button class="logout-confirm" @click="confirmCollection">Cash received</button></div>
    </dialog>
  </section>
</template>
