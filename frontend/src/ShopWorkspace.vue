<script setup>
import ManualUpiSettings from './ManualUpiSettings.vue'
import { computed, inject, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { call } from './api.js'
import Products from './Products.vue'
import ScheduledDelivery from './ScheduledDelivery.vue'
import FishInventory from './FishInventory.vue'
import Dashboard from './Dashboard.vue'
import Orders from './Orders.vue'
import CashReconciliation from './CashReconciliation.vue'
import MapView from './MapView.vue'
const session = inject('session'), route = useRoute()
const shop = ref(null), loading = ref(false), error = ref(''), saved = ref(''), saving = ref(false)
const expenseAccounts = ref([])
const payment = ref(null), paymentSaved = ref(''), paymentSaving = ref(false)
const hoursSaving = ref(false), hoursSaved = ref('')
const tab = ref('overview'), orderRefresh = ref(0)
const tabs = new Set(['overview', 'orders', 'cash', 'inventory', 'fish', 'settings'])
const locationError = ref(''), locating = ref(false)
const timeOptions = Array.from({ length: 48 }, (_, index) => `${String(Math.floor(index / 2)).padStart(2, '0')}:${index % 2 ? '30' : '00'}`)
function timeLabel(value) { const [hour, minute] = value.split(':').map(Number); return `${hour % 12 || 12}:${String(minute).padStart(2, '0')} ${hour < 12 ? 'AM' : 'PM'}` }
const canEdit = computed(() => shop.value && (session.value.platform_admin || session.value.memberships.some(m => m.shop === shop.value.name && m.membership_role === 'Owner')))
const canSchedule = computed(() => session.value.platform_admin || (canEdit.value && session.value.roles.includes('LC Scheduled Delivery Manager')))
const canEditLocation = computed(() => shop.value && session.value.platform_admin)
const shopPoints = computed(() => {
  const latitude = shop.value?.latitude, longitude = shop.value?.longitude
  return latitude !== '' && longitude !== '' && latitude != null && longitude != null && Number.isFinite(Number(latitude)) && Number.isFinite(Number(longitude)) ? [{ kind: 'shop', label: shop.value.shop_name, latitude, longitude }] : []
})
let request = 0
async function load() {
  const current = ++request
  shop.value = null; payment.value = null; loading.value = true; error.value = ''; saved.value = ''; tab.value = tabs.has(route.query.tab) ? route.query.tab : 'overview'
  try {
    const result = await call('shops.get_shop', { shop: route.params.shop })
    if (current === request) {
      shop.value = result
      if (session.value.platform_admin) expenseAccounts.value = await call('fish.expense_accounts', { shop: result.name })
      if (!canEdit.value && tab.value === 'overview') tab.value = 'inventory'
      if (session.value.platform_admin || session.value.memberships.some(m => m.shop === result.name && m.membership_role === 'Owner')) payment.value = await call('orders.payment_options', { shop: result.name })
    }
  } catch (e) { if (current === request) error.value = e.message }
  finally { if (current === request) loading.value = false }
}
async function savePayment() {
  paymentSaving.value = true; error.value = ''; paymentSaved.value = ''
  try {
    payment.value = await call('orders.configure_cod', { shop: shop.value.name, enabled: payment.value.enabled, cash_account: payment.value.cash_account || '', mode_of_payment: payment.value.mode_of_payment || '' }, true)
    paymentSaved.value = 'Cash on Delivery settings saved.'
  } catch (e) { error.value = e.message }
  finally { paymentSaving.value = false }
}
async function saveHours() {
  hoursSaving.value = true; hoursSaved.value = ''; error.value = ''
  try {
    const result = await call('shops.update_hours', { shop: shop.value.name, accepting_orders: shop.value.accepting_orders ? 1 : 0, opening_hours: shop.value.opening_hours }, true)
    shop.value.opening_hours = result.opening_hours
    shop.value.accepting_orders = result.accepting_orders
    shop.value.availability = result.availability
    hoursSaved.value = 'Opening hours saved.'
  } catch (e) { error.value = e.message }
  finally { hoursSaving.value = false }
}
async function save() {
  saving.value = true; error.value = ''; saved.value = ''
  const current = request
  try {
    const s = shop.value
    const values = { shop: s.name, shop_name: s.shop_name, status: s.status, description: s.description || '', order_response_minutes: s.order_response_minutes || 10, accepting_orders: s.accepting_orders ? 1 : 0, opening_hours: s.opening_hours }
    if (canEditLocation.value) Object.assign(values, { address_line1: s.address_line1 || '', city: s.city || '', postal_code: s.postal_code || '', latitude: s.latitude ?? '', longitude: s.longitude ?? '', service_radius_km: s.service_radius_km || 5, live_tracking_enabled: s.live_tracking_enabled ? 1 : 0 })
    if (session.value.platform_admin) Object.assign(values, { shop_type: s.shop_type || 'General', fish_wastage_account: s.fish_wastage_account || '', minimum_order_amount: s.minimum_order_amount || 0, free_delivery_above: s.free_delivery_above || 0, delivery_fee_per_km: s.delivery_fee_per_km || 0, delivery_included_km: s.delivery_included_km || 0, delivery_fee: s.delivery_fee || 0 })
    const result = await call('shops.update_shop', values, true)
    if (current === request) { shop.value = result; saved.value = 'Shop settings saved.' }
  } catch (e) { if (current === request) error.value = e.message }
  finally { saving.value = false }
}
function pickShopLocation(point) {
  if (!canEditLocation.value) return
  shop.value.latitude = point.latitude; shop.value.longitude = point.longitude; locationError.value = ''
  if (point.address_line1) shop.value.address_line1 = point.address_line1
  if (point.city) shop.value.city = point.city
  if (point.postal_code) shop.value.postal_code = point.postal_code
}
function clearShopLocation() { shop.value.latitude = null; shop.value.longitude = null; locationError.value = '' }
function useShopLocation() {
  locationError.value = ''
  if (!navigator.geolocation) { locationError.value = 'Location is not available in this browser. Tap the map to place the shop pin.'; return }
  locating.value = true
  navigator.geolocation.getCurrentPosition(
    position => { pickShopLocation(position.coords); locating.value = false },
    () => { locationError.value = window.isSecureContext ? 'We could not read this device location. Allow location access or tap the map.' : 'Automatic location needs HTTPS. You can still tap the map to place the pin.'; locating.value = false },
    { enableHighAccuracy: true, timeout: 12000, maximumAge: 30000 },
  )
}
watch(() => route.params.shop, load, { immediate: true })
watch(() => route.query.tab, value => { if (tabs.has(value)) tab.value = value })
</script>

<template>
  <section class="owner-page">
    <aside class="owner-sidebar">
      <RouterLink class="workspace-back" to="/shop">← All shops</RouterLink>
      <span class="eyebrow">SHOP WORKSPACE</span>
      <strong>{{ shop?.shop_name || 'Your shop' }}</strong>
      <p>Everything you need to manage this shop, in one place.</p>
      <nav v-if="shop" class="workspace-nav" aria-label="Shop sections">
        <button v-if="canEdit" :class="{ 'sidebar-active': tab === 'overview' }" :aria-current="tab === 'overview' ? 'page' : undefined" @click="tab = 'overview'">Overview</button>
        <button :class="{ 'sidebar-active': tab === 'orders' }" :aria-current="tab === 'orders' ? 'page' : undefined" @click="tab = 'orders'">Orders</button>
        <button :class="{ 'sidebar-active': tab === 'cash' }" :aria-current="tab === 'cash' ? 'page' : undefined" @click="tab = 'cash'">Cash handover</button>
        <button :class="{ 'sidebar-active': tab === 'inventory' }" :aria-current="tab === 'inventory' ? 'page' : undefined" @click="tab = 'inventory'">Products &amp; stock</button>
        <button v-if="shop.shop_type === 'Fish' && canEdit" :class="{ 'sidebar-active': tab === 'fish' }" @click="tab = 'fish'">Fish inventory &amp; reports</button>
        <RouterLink v-if="session.platform_admin" class="workspace-storefront-link" to="/store-settings">Storefront settings ↗</RouterLink>
        <button :class="{ 'sidebar-active': tab === 'settings' }" :aria-current="tab === 'settings' ? 'page' : undefined" @click="tab = 'settings'">Shop settings</button>
      </nav>
      <div class="sidebar-bottom"><span class="status-pill">{{ canEdit ? 'Owner access' : 'Read-only access' }}</span><small>{{ session.user }}</small></div>
    </aside>
    <div class="owner-content">
      <p v-if="loading" role="status">Opening your shop…</p>
      <div v-if="error" class="lc-notice" role="alert">{{ error }} <button v-if="!shop" @click="load">Retry</button></div>
      <template v-if="shop">
        <header class="workspace-heading"><div><span class="eyebrow">YOUR SHOP</span><h1>{{ shop.shop_name }}</h1><p class="muted">{{ shop.company }}</p></div><span class="status-pill">{{ shop.status }}</span></header>
        <Dashboard v-if="tab === 'overview' && canEdit" :shop="shop.name" @open="tab = $event" />
        <ScheduledDelivery v-if="tab === 'orders' && canSchedule" :shop="shop.name" batches-only @changed="orderRefresh++" />
        <Orders v-if="tab === 'orders'" :key="orderRefresh" :shop="shop.name" :editable="canEdit" />
        <CashReconciliation v-if="tab === 'cash'" :shop="shop.name" :editable="canEdit" />
        <Products v-show="tab === 'inventory'" :key="`${shop.name}:${shop.shop_type}`" :shop="shop.name" :editable="canEdit" :fish-shop="shop.shop_type === 'Fish'" />
        <FishInventory v-if="tab === 'fish' && shop.shop_type === 'Fish' && canEdit" :shop="shop.name" />
        <ScheduledDelivery v-if="canSchedule && tab === 'settings'" :shop="shop.name" /><form v-show="tab === 'settings'" class="lc-form" @submit.prevent="save">
          <h2>Shop settings</h2><p class="muted">Keep your shop details and availability up to date.</p>
          <fieldset :disabled="!canEdit || saving" class="workspace-fields">
            <label>Name<input v-model="shop.shop_name" required></label>
            <label>Company<input :value="shop.company" disabled></label>
            <label>Shop type<select v-model="shop.shop_type" :disabled="!session.platform_admin"><option>General</option><option>Fish</option></select><small>Only Fish shops use stock expiry, market prices and wastage tracking.</small></label>
            <label v-if="shop.shop_type === 'Fish'">Wastage expense account<select v-model="shop.fish_wastage_account" :disabled="!session.platform_admin"><option value="">Select expense account</option><option v-if="shop.fish_wastage_account && !expenseAccounts.includes(shop.fish_wastage_account)">{{ shop.fish_wastage_account }}</option><option v-for="account in expenseAccounts" :key="account">{{ account }}</option></select><small>A platform administrator chooses an expense account from this Company.</small></label>
            <label>Status<select v-model="shop.status"><option>Draft</option><option>Active</option><option>Temporarily Closed</option><option>Disabled</option></select></label>
            <label>Description<textarea v-model="shop.description"></textarea></label>
            <section class="shop-hours"><span class="eyebrow">DELIVERY PRICING</span><h3>Order minimum &amp; delivery fees</h3><p v-if="!session.platform_admin" class="muted">A platform administrator manages these pricing rules.</p><div class="form-columns"><label>Minimum item subtotal<input v-model.number="shop.minimum_order_amount" :disabled="!session.platform_admin" type="number" min="0" step="0.01"><small>0 means no minimum.</small></label><label>Free delivery above<input v-model.number="shop.free_delivery_above" :disabled="!session.platform_admin" type="number" min="0" step="0.01"><small>0 disables free delivery.</small></label><label>Base delivery fee<input v-model.number="shop.delivery_fee" :disabled="!session.platform_admin" type="number" min="0" step="0.01"></label><label>Distance included (km)<input v-model.number="shop.delivery_included_km" :disabled="!session.platform_admin" type="number" min="0" step="0.1"></label><label>Fee per additional km<input v-model.number="shop.delivery_fee_per_km" :disabled="!session.platform_admin" type="number" min="0" step="0.01"><small>Uses straight-line distance. 0 keeps a flat fee.</small></label></div></section>
            <label>Order response time (minutes)<input v-model.number="shop.order_response_minutes" type="number" min="1" max="120" step="1" required><small>New orders cancel automatically if nobody responds within this time.</small></label>
            <label class="check-label"><input v-model="shop.accepting_orders" type="checkbox"><span>Accept new orders<small>Turn this off to pause checkout immediately. Active orders continue normally.</small></span></label>
            <section class="shop-hours"><div><span class="eyebrow">OPENING HOURS</span><h3>Weekly ordering schedule</h3><p class="muted">Customers can browse at any time. Checkout follows this schedule.</p></div><div v-for="day in shop.opening_hours" :key="day.day" class="shop-hours-row"><label class="check-label"><input v-model="day.enabled" type="checkbox"><span>{{ day.day }}</span></label><template v-if="day.enabled"><label><small>Opens</small><select v-model="day.opens" required><option v-for="time in timeOptions" :key="time" :value="time">{{ timeLabel(time) }}</option></select></label><span>to</span><label><small>Closes</small><select v-model="day.closes" required><option v-for="time in timeOptions" :key="time" :value="time">{{ timeLabel(time) }}</option></select></label></template><strong v-else>Closed all day</strong></div><div class="shop-hours-save"><button type="button" class="lc-primary" :disabled="hoursSaving" @click="saveHours">{{ hoursSaving ? 'Saving hours…' : 'Save opening hours' }}</button><span v-if="hoursSaved" role="status">✓ {{ hoursSaved }}</span></div></section>
            <section class="location-editor">
              <div class="location-heading"><div><span class="eyebrow">DELIVERY MAP</span><h3>Shop address &amp; service area</h3><p>{{ canEditLocation ? 'Place the shop pin and set how far your riders deliver.' : 'A platform administrator manages this shop location.' }}</p></div><button v-if="canEditLocation" type="button" :disabled="locating" @click="useShopLocation">{{ locating ? 'Finding…' : 'Use current location' }}</button></div>
              <label>Street address<input v-model="shop.address_line1" :disabled="!canEditLocation" maxlength="140" autocomplete="street-address"></label>
              <div class="form-columns"><label>City<input v-model="shop.city" :disabled="!canEditLocation" maxlength="140" autocomplete="address-level2"></label><label>Postal code<input v-model="shop.postal_code" :disabled="!canEditLocation" maxlength="140" autocomplete="postal-code"></label></div>
              <small class="coordinate-help">{{ canEditLocation ? "Search for a place or tap the map to place the shop pin. Save shop settings below to keep the location." : 'Contact the platform administrator to change the address or map pin.' }}</small>
              <MapView :config="shop.map" :points="shopPoints" :editable="canEditLocation" @pick="pickShopLocation" />
              <div class="coordinate-row"><span>{{ shopPoints.length ? 'Shop pin selected' : 'No map pin selected' }}</span><button v-if="canEditLocation && shopPoints.length" type="button" @click="clearShopLocation">Clear pin</button></div>
              <label>Delivery radius (km)<input v-model.number="shop.service_radius_km" :disabled="!canEditLocation" type="number" min="0.1" max="500" step="0.1" required></label>
              <label class="check-label"><input v-model="shop.live_tracking_enabled" :disabled="!canEditLocation" type="checkbox"><span>Allow live rider tracking<small>Customers can see the assigned rider while their order is out for delivery.</small></span></label>
              <p v-if="locationError" class="lc-notice" role="alert">{{ locationError }}</p>
            </section>
            <button v-if="canEdit" class="lc-primary">{{ saving ? 'Saving…' : 'Save settings' }}</button>
          </fieldset>
          <p v-if="saved" role="status">{{ saved }}</p>
        </form>
        <ManualUpiSettings v-if="tab === 'settings' && canEdit" :key="shop.name" :shop="shop.name" />
        <form v-if="tab === 'settings' && canEdit && payment" class="lc-form payment-settings" @submit.prevent="savePayment">
          <span class="eyebrow">PAYMENT</span><h2>Cash on Delivery</h2><p class="muted">The rider records the amount at delivery. The Payment Entry is created after the shop confirms the cash handover.</p>
          <fieldset :disabled="paymentSaving" class="workspace-fields">
            <label class="check-label"><input v-model="payment.enabled" type="checkbox"><span>Enable Cash on Delivery<small>Customers can place an order and pay the rider at delivery.</small></span></label>
            <label>Cash collection account<select v-model="payment.cash_account" :required="payment.enabled"><option value="">Select cash account</option><option v-for="account in payment.cash_accounts" :key="account" :value="account">{{ account }}</option></select></label>
            <label>Mode of payment<select v-model="payment.mode_of_payment" :required="payment.enabled"><option value="">Select mode</option><option v-for="mode in payment.modes" :key="mode" :value="mode">{{ mode }}</option></select></label>
            <button class="lc-primary">{{ paymentSaving ? 'Saving…' : 'Save payment settings' }}</button>
          </fieldset>
          <p v-if="paymentSaved" class="success-note" role="status">{{ paymentSaved }}</p>
        </form>
      </template>
    </div>
  </section>
</template>
