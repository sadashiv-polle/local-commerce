<script setup>
import { computed, inject, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { call } from './api.js'
import AuthChoices from './AuthChoices.vue'
import MapView from './MapView.vue'
import { readCart, writeCart, clearCart, changeQuantity } from './cart.js'
import { distanceKm } from './location.js'
const route = useRoute(), router = useRouter(), session = inject('session')
const catalog = ref(null), error = ref(''), loading = ref(false), busy = ref(false), start = ref(0)
const cart = ref({}), pending = ref(null), checkout = ref(false), cartOpen = ref(false)
const address = ref({ recipient: '', phone: '', line1: '', city: '', postal_code: '', latitude: null, longitude: null, delivery_instructions: '' })
const savedAddresses = ref([]), selectedAddress = ref('')
const locationError = ref(''), locating = ref(false)
const storageKey = computed(() => `lc-delivery:${session.value.user}:${route.params.shop}`)
const subtotal = computed(() => Object.values(cart.value).reduce((sum, row) => sum + row.rate * Number(row.quantity), 0))
const estimatedTotal = computed(() => subtotal.value + Number(catalog.value?.delivery_fee || 0))
const deliveryDistance = computed(() => distanceKm(catalog.value?.shop_location, address.value))
const outsideDeliveryRange = computed(() => deliveryDistance.value != null && deliveryDistance.value > Number(catalog.value?.shop_location?.service_radius_km || 0))
const deliveryPoints = computed(() => {
  const points = []
  if (catalog.value?.shop_location) points.push({ ...catalog.value.shop_location, kind: 'shop', label: catalog.value.shop_name })
  if (address.value.latitude !== '' && address.value.longitude !== '' && address.value.latitude != null && address.value.longitude != null && Number.isFinite(Number(address.value.latitude)) && Number.isFinite(Number(address.value.longitude))) points.push({ ...address.value, kind: 'customer', label: 'Your delivery location' })
  return points
})
function money(value) { if (value == null) return 'Price coming soon'; return new Intl.NumberFormat(undefined, { style: 'currency', currency: catalog.value.currency }).format(value) }
async function load(delta = 0) {
  loading.value = true; error.value = ''; start.value = Math.max(0, start.value + delta)
  try { catalog.value = await call('orders.catalog', { shop: route.params.shop, start: start.value }) }
  catch (e) { error.value = e.message }
  finally { loading.value = false }
}
function updateQuantity(item, delta) {
  error.value = ''
  try { cart.value = changeQuantity(cart.value, item, delta) }
  catch { error.value = 'That quantity is not available right now.' }
}
function openCart() {
  checkout.value = false
  cartOpen.value = true
}
function openCartEvent() { openCart() }
function closeCart() {
  if (!busy.value) cartOpen.value = false
}
function pickDeliveryLocation(point) { address.value.latitude = point.latitude; address.value.longitude = point.longitude; locationError.value = ''; error.value = '' }
function useDeliveryLocation() {
  locationError.value = ''
  if (!navigator.geolocation) { locationError.value = 'Location is not available in this browser. Tap the map to place your pin.'; return }
  locating.value = true
  navigator.geolocation.getCurrentPosition(
    position => { pickDeliveryLocation(position.coords); locating.value = false },
    () => { locationError.value = window.isSecureContext ? 'We could not read your location. Allow location access or tap the map.' : 'Automatic location needs HTTPS. You can still tap the map to place your delivery pin.'; locating.value = false },
    { enableHighAccuracy: true, timeout: 12000, maximumAge: 30000 },
  )
}
function applySavedAddress() {
  const saved = savedAddresses.value.find(row => row.name === selectedAddress.value)
  if (!saved) return
  const instructions = address.value.delivery_instructions
  address.value = { ...address.value, ...saved, delivery_instructions: instructions }
  error.value = ''; locationError.value = ''
  try { localStorage.setItem(`lc-address:${session.value.user}`, saved.name) } catch { /* Selection still applies to checkout. */ }
  window.dispatchEvent(new CustomEvent('lc-address-change', { detail: saved.name }))
}
async function loadSavedAddresses() {
  savedAddresses.value = []; selectedAddress.value = ''
  if (session.value.user === 'Guest' || !session.value.roles.includes('LC Customer')) return
  try {
    savedAddresses.value = await call('customers.addresses')
    let remembered = ''
    try { remembered = localStorage.getItem(`lc-address:${session.value.user}`) || '' } catch { /* Use the server default. */ }
    selectedAddress.value = savedAddresses.value.some(row => row.name === remembered) ? remembered : savedAddresses.value.find(row => row.is_default)?.name || savedAddresses.value[0]?.name || ''
    applySavedAddress()
  } catch { /* Manual checkout remains available if the address book cannot load. */ }
}
async function place() {
  if (session.value.user === 'Guest') {
    try { writeCart(localStorage, route.params.shop, cart.value); checkout.value = true }
    catch { error.value = 'Enable local storage so your cart can be saved through login.' }
    return
  }
  busy.value = true; error.value = ''
  try {
    if (!pending.value) {
      const bytes = crypto.getRandomValues(new Uint8Array(20))
      pending.value = { shop: route.params.shop, items: Object.values(cart.value).map(i => ({ item: i.item, quantity: i.quantity })), address: { ...address.value }, payment_method: 'Cash on Delivery', request_key: Array.from(bytes, b => b.toString(16).padStart(2, '0')).join('') }
      try { sessionStorage.setItem(storageKey.value, JSON.stringify(pending.value)) }
      catch { pending.value = null; throw new Error('Enable session storage before sending an order request so retries are safe.') }
    }
    await call('orders.place', pending.value, true)
    sessionStorage.removeItem(storageKey.value); pending.value = null; clearCart(localStorage, route.params.shop); cart.value = {}
    await router.push('/orders')
  } catch (e) {
    error.value = e.message
    if ([400, 403, 417].includes(e.status)) { sessionStorage.removeItem(storageKey.value); pending.value = null }
  } finally { busy.value = false }
}
watch(() => route.params.shop, () => {
  start.value = 0; pending.value = null; cartOpen.value = false; checkout.value = false
  try {
    cart.value = readCart(localStorage, route.params.shop)
    if (Object.keys(cart.value).length) writeCart(localStorage, route.params.shop, cart.value)
  } catch { cart.value = {}; error.value = 'Your saved cart could not be read.' }
  try { pending.value = JSON.parse(sessionStorage.getItem(storageKey.value) || 'null') } catch { /* Server validates recovered payloads. */ }
  load()
  loadSavedAddresses()
  if (route.query.cart === '1') cartOpen.value = true
}, { immediate: true })
watch(cart, value => {
  try { writeCart(localStorage, route.params.shop, value) } catch { error.value = 'Your browser could not save this cart. Enable local storage before logging in.' }
  if (!Object.keys(value).length) cartOpen.value = false
}, { deep: true })
onMounted(() => window.addEventListener('lc-open-cart', openCartEvent))
onBeforeUnmount(() => window.removeEventListener('lc-open-cart', openCartEvent))
</script>
<template>
  <div class="store-page customer-shop">
    <RouterLink to="/store">← All shops</RouterLink> · <RouterLink to="/orders">My orders</RouterLink>
    <p v-if="error" class="lc-notice" role="alert">{{ error }}</p><p v-if="loading" role="status">Loading products…</p>
    <template v-if="catalog">
      <h1>{{ catalog.shop_name }}</h1><p>{{ catalog.accepting_orders ? 'Delivery requests · Shop confirmation required' : 'Browse our products · Ordering opens soon' }}</p>
      <p v-if="catalog.accepting_orders" class="muted">Delivery postal codes: {{ catalog.postal_codes }} · Delivery fee: {{ money(catalog.delivery_fee) }}</p>
      <p v-if="pending" class="lc-notice">Your last request is not confirmed. Retry it below before starting another.</p>
      <fieldset :disabled="busy || !!pending">
        <div class="lc-grid product-grid">
          <article v-for="item in catalog.items" :key="item.item" class="lc-card customer-product-card">
            <div class="product-art" aria-hidden="true">{{ item.item_name.slice(0, 1).toUpperCase() }}</div>
            <p class="product-availability">{{ item.available }} {{ item.uom }} available</p>
            <h3>{{ item.item_name }}</h3><p class="product-description">{{ item.description || 'Fresh from your local shop.' }}</p>
            <div class="product-buy-row">
              <strong>{{ money(item.rate) }}<small v-if="item.rate != null"> / {{ item.uom }}</small></strong>
              <div v-if="cart[item.item]" class="quantity-stepper" :aria-label="`${item.item_name} quantity`"><button type="button" :aria-label="`Remove one ${item.item_name}`" @click="updateQuantity(item, -1)">−</button><strong aria-live="polite">{{ cart[item.item].quantity }}</strong><button type="button" :disabled="cart[item.item].quantity >= item.available" :aria-label="`Add one ${item.item_name}`" @click="updateQuantity(item, 1)">+</button></div>
              <button v-else class="add-item-button" :disabled="item.available <= 0 || item.rate == null" @click="updateQuantity(item, 1)">{{ item.rate == null ? 'Soon' : item.available > 0 ? 'ADD' : 'Sold out' }}</button>
            </div>
          </article>
        </div>
        <p v-if="!catalog.items.length" class="lc-empty">No products on this page.</p>
        <div class="lc-pagination"><button :disabled="!start || loading" @click="load(-20)">Previous</button><button :disabled="!catalog.has_more || loading" @click="load(20)">Next</button></div>
      </fieldset>
      <div v-if="cartOpen" class="cart-backdrop" @click.self="closeCart">
        <aside class="cart-drawer" role="dialog" aria-modal="true" aria-labelledby="cart-title">
          <header class="cart-drawer-header"><div><span class="eyebrow">YOUR BASKET</span><h2 id="cart-title">My cart</h2></div><button type="button" aria-label="Close cart" :disabled="busy" @click="closeCart">×</button></header>
          <div class="delivery-promise"><span aria-hidden="true">✓</span><div><strong>From {{ catalog.shop_name }}</strong><small>{{ catalog.accepting_orders ? 'Delivery request subject to shop confirmation' : 'Ordering opens soon' }}</small></div></div>
          <div class="cart-line-list">
            <article v-for="item in cart" :key="item.item" class="cart-line"><div class="cart-line-art" aria-hidden="true">{{ item.item_name.slice(0, 1).toUpperCase() }}</div><div><strong>{{ item.item_name }}</strong><small>{{ money(item.rate) }} / {{ item.uom }}</small></div><div class="quantity-stepper"><button type="button" :disabled="busy || !!pending" :aria-label="`Remove one ${item.item_name}`" @click="updateQuantity(item, -1)">−</button><strong>{{ item.quantity }}</strong><button type="button" :disabled="busy || !!pending || item.quantity >= item.available" :aria-label="`Add one ${item.item_name}`" @click="updateQuantity(item, 1)">+</button></div><strong>{{ money(item.rate * item.quantity) }}</strong></article>
          </div>
          <section class="bill-details"><h3>Bill details</h3><p><span>Item total</span><strong>{{ money(subtotal) }}</strong></p><p><span>Delivery fee</span><strong>{{ money(catalog.delivery_fee) }}</strong></p><p class="bill-total"><span>Estimated total</span><strong>{{ money(estimatedTotal) }}</strong></p><small>ERPNext calculates applicable taxes when your request is saved.</small></section>
          <AuthChoices v-if="checkout && session.user === 'Guest'" />
          <form v-else class="cart-checkout-form" @submit.prevent="place">
            <fieldset v-if="session.user !== 'Guest'" :disabled="busy || !!pending">
              <h3>Delivery details</h3><div v-if="savedAddresses.length" class="saved-address-picker"><label>Saved address<select v-model="selectedAddress" @change="applySavedAddress"><option v-for="savedAddress in savedAddresses" :key="savedAddress.name" :value="savedAddress.name">{{ savedAddress.address_label }} · {{ savedAddress.line1 }}</option></select></label><RouterLink to="/account">Manage addresses</RouterLink></div><div class="form-columns"><label>Recipient<input v-model="address.recipient" required maxlength="140" autocomplete="name"></label><label>Phone<input v-model="address.phone" required maxlength="30" type="tel" autocomplete="tel"></label></div><label>Street address<input v-model="address.line1" required maxlength="140" autocomplete="address-line1"></label><div class="form-columns"><label>City<input v-model="address.city" required maxlength="100" autocomplete="address-level2"></label><label>Postal code<input v-model="address.postal_code" required maxlength="20" autocomplete="postal-code"></label></div>
              <section v-if="catalog.shop_location" class="checkout-location"><div class="location-heading"><div><strong>Pin your delivery location</strong><small>Inside {{ catalog.shop_location.service_radius_km }} km of the shop</small></div><button type="button" :disabled="locating" @click="useDeliveryLocation">{{ locating ? 'Finding…' : 'Use my location' }}</button></div><div class="manual-coordinate-fields"><label>Latitude<input v-model.number="address.latitude" required type="number" min="-90" max="90" step="0.000001" inputmode="decimal" placeholder="15.490900" @input="locationError = ''; error = ''"></label><label>Longitude<input v-model.number="address.longitude" required type="number" min="-180" max="180" step="0.000001" inputmode="decimal" placeholder="73.827800" @input="locationError = ''; error = ''"></label></div><small class="coordinate-help">You can copy latitude and longitude from any map app.</small><MapView :config="catalog.map" :points="deliveryPoints" editable height="220px" @pick="pickDeliveryLocation" /><p v-if="outsideDeliveryRange" class="range-warning" role="alert"><strong>Outside delivery range</strong>Your address is approximately {{ deliveryDistance.toFixed(1) }} km from this shop. This shop currently delivers within {{ Number(catalog.shop_location.service_radius_km).toFixed(1) }} km. Choose a closer address or another shop.</p><p v-else-if="deliveryDistance != null" class="map-confirmation">✓ Within range · approximately {{ deliveryDistance.toFixed(1) }} km from the shop</p><p v-if="locationError" class="lc-notice" role="alert">{{ locationError }}</p></section>
              <label>Delivery instructions <small>(optional)</small><textarea v-model="address.delivery_instructions" maxlength="500" placeholder="Landmark, gate, floor, or how to find you"></textarea></label>
              <div class="checkout-payment"><span aria-hidden="true">₹</span><div><strong>Cash on Delivery</strong><small>{{ catalog.payment_message }}</small></div><b>✓</b></div>
            </fieldset>
            <p v-if="error" class="checkout-error" role="alert">{{ error }}</p>
            <p v-if="!catalog.accepting_orders" class="muted">Your cart is saved. This shop is not accepting orders yet.</p>
            <button class="cart-checkout-button" :disabled="busy || outsideDeliveryRange || (!catalog.accepting_orders && !pending)"><span>{{ busy ? 'Sending…' : outsideDeliveryRange ? 'Address outside delivery range' : pending ? 'Retry request' : session.user === 'Guest' ? 'Login to order' : 'Send order request' }}</span><strong>{{ money(estimatedTotal) }} ›</strong></button>
          </form>
        </aside>
      </div>
    </template>
  </div>
</template>
