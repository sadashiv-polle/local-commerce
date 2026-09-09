<script setup>
import { computed, inject, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { call } from './api.js'
import AuthChoices from './AuthChoices.vue'
import { readCart, writeCart, clearCart } from './cart.js'
const route = useRoute(), router = useRouter(), session = inject('session')
const catalog = ref(null), quantities = ref({}), error = ref(''), loading = ref(false), busy = ref(false), start = ref(0)
const cart = ref({}), pending = ref(null), checkout = ref(false)
const address = ref({ recipient: '', phone: '', line1: '', city: '', postal_code: '' })
const storageKey = computed(() => `lc-delivery:${session.value.user}:${route.params.shop}`)
const subtotal = computed(() => Object.values(cart.value).reduce((sum, row) => sum + row.rate * Number(row.quantity), 0))
function money(value) { return new Intl.NumberFormat(undefined, { style: 'currency', currency: catalog.value.currency }).format(value) }
async function load(delta = 0) {
  loading.value = true; error.value = ''; start.value = Math.max(0, start.value + delta)
  try { catalog.value = await call('orders.catalog', { shop: route.params.shop, start: start.value }) }
  catch (e) { error.value = e.message }
  finally { loading.value = false }
}
function add(item) {
  const quantity = Number(quantities.value[item.item] || 1)
  if (!Number.isFinite(quantity) || quantity <= 0 || quantity > item.available) { error.value = 'Choose a quantity within available stock.'; return }
  cart.value[item.item] = { ...item, quantity }
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
      pending.value = { shop: route.params.shop, items: Object.values(cart.value).map(i => ({ item: i.item, quantity: i.quantity })), address: { ...address.value }, request_key: Array.from(bytes, b => b.toString(16).padStart(2, '0')).join('') }
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
  start.value = 0; quantities.value = {}; pending.value = null
  try { cart.value = readCart(localStorage, route.params.shop) } catch { cart.value = {}; error.value = 'Your saved cart could not be read.' }
  try { pending.value = JSON.parse(sessionStorage.getItem(storageKey.value) || 'null') } catch { /* Server validates recovered payloads. */ }
  load()
}, { immediate: true })
watch(cart, value => {
  try { writeCart(localStorage, route.params.shop, value) } catch { error.value = 'Your browser could not save this cart. Enable local storage before logging in.' }
}, { deep: true })
</script>
<template>
  <div class="store-page">
    <RouterLink to="/store">← All shops</RouterLink> · <RouterLink to="/orders">My orders</RouterLink>
    <p v-if="error" class="lc-notice" role="alert">{{ error }}</p><p v-if="loading" role="status">Loading products…</p>
    <template v-if="catalog">
      <h1>{{ catalog.shop_name }}</h1><p>Delivery requests · Shop confirmation required</p>
      <p class="muted">Delivery postal codes: {{ catalog.postal_codes }} · Delivery fee: {{ money(catalog.delivery_fee) }}</p>
      <p v-if="pending" class="lc-notice">Your last request is not confirmed. Retry it below before starting another.</p>
      <fieldset :disabled="busy || !!pending">
        <div class="lc-grid product-grid">
          <article v-for="item in catalog.items" :key="item.item" class="lc-card">
            <h3>{{ item.item_name }}</h3><p>{{ item.description }}</p><strong>{{ money(item.rate) }} / {{ item.uom }}</strong><p>{{ item.available }} {{ item.uom }} available</p>
            <label>Quantity<input v-model="quantities[item.item]" type="number" min="0.000001" step="0.000001" :max="item.available" placeholder="1"></label>
            <button :disabled="item.available <= 0" @click="add(item)">{{ item.available > 0 ? 'Add to cart' : 'Sold out' }}</button>
          </article>
        </div>
        <p v-if="!catalog.items.length" class="lc-empty">No priced products on this page.</p>
        <div class="lc-pagination"><button :disabled="!start || loading" @click="load(-20)">Previous</button><button :disabled="!catalog.has_more || loading" @click="load(20)">Next</button></div>
      </fieldset>
      <AuthChoices v-if="checkout && session.user === 'Guest'" />
      <form v-if="Object.keys(cart).length || pending" class="inventory-form" @submit.prevent="place">
        <h2>Your delivery request</h2>
        <fieldset :disabled="busy || !!pending">
          <ul><li v-for="item in cart" :key="item.item">{{ item.item_name }} · {{ item.quantity }} {{ item.uom }} <button type="button" @click="delete cart[item.item]">Remove</button></li></ul>
          <p>Products {{ money(subtotal) }} + delivery {{ money(catalog.delivery_fee) }}. ERPNext calculates applicable taxes when the request is saved. This is a request for shop confirmation; no payment is taken.</p>
          <template v-if="session.user !== 'Guest'">
            <div class="form-columns"><label>Recipient<input v-model="address.recipient" required maxlength="140" autocomplete="name"></label><label>Phone<input v-model="address.phone" required maxlength="30" type="tel" autocomplete="tel"></label></div>
            <label>Street address<input v-model="address.line1" required maxlength="140" autocomplete="address-line1"></label>
            <div class="form-columns"><label>City<input v-model="address.city" required maxlength="100" autocomplete="address-level2"></label><label>Postal code<input v-model="address.postal_code" required maxlength="20" autocomplete="postal-code"></label></div>
          </template>
        </fieldset>
        <button class="lc-primary" :disabled="busy">{{ busy ? 'Sending…' : pending ? 'Retry same request' : session.user === 'Guest' ? 'Order / Checkout' : 'Send delivery request' }}</button>
      </form>
    </template>
  </div>
</template>
