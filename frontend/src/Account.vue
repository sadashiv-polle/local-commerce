<script setup>
import { computed, inject, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { call } from './api.js'
import AuthChoices from './AuthChoices.vue'
import MapView from './MapView.vue'

const session = inject('session')
const route = useRoute()
const data = ref(null), error = ref(''), saved = ref(''), loading = ref(false), busy = ref(false), locating = ref(false), start = ref(0)
const editing = ref(false), editor = ref(null)
const emptyAddress = () => ({ name: '', address_type: 'Home', address_label: 'Home', recipient: session.value?.full_name || '', phone: '', line1: '', city: '', postal_code: '', latitude: '', longitude: '', is_default: false })
const form = ref(emptyAddress())
const addressPoints = computed(() => form.value.latitude !== '' && form.value.longitude !== '' && Number.isFinite(Number(form.value.latitude)) && Number.isFinite(Number(form.value.longitude)) ? [{ ...form.value, kind: 'customer', label: form.value.address_label || 'Saved address' }] : [])
function notifyAddress(name = '') { window.dispatchEvent(new CustomEvent('lc-address-change', { detail: name })) }

async function load(delta = 0) {
  start.value = Math.max(0, start.value + delta)
  loading.value = true; error.value = ''
  try { data.value = await call('customers.account', { start: start.value }, true) }
  catch (e) { error.value = e.message }
  finally { loading.value = false }
}
function newAddress() { form.value = emptyAddress(); editing.value = true; saved.value = ''; error.value = '' }
async function openNewAddress() { newAddress(); await nextTick(); editor.value?.scrollIntoView({ behavior: 'smooth', block: 'start' }) }
function editAddress(address) { form.value = { ...address }; editing.value = true; saved.value = ''; error.value = '' }
function cancelEdit() { editing.value = false; form.value = emptyAddress() }
function pickLocation(point) { form.value.latitude = point.latitude; form.value.longitude = point.longitude; error.value = '' }
function useLocation() {
  error.value = ''
  if (!navigator.geolocation) { error.value = 'Location is unavailable. Tap the map to choose the location.'; return }
  locating.value = true
  navigator.geolocation.getCurrentPosition(
    position => { pickLocation(position.coords); locating.value = false },
    () => { error.value = window.isSecureContext ? 'Location access failed. Allow it or tap the map.' : 'Automatic location needs HTTPS. Tap the map to place the pin.'; locating.value = false },
    { enableHighAccuracy: true, timeout: 12000, maximumAge: 30000 },
  )
}
async function saveAddress() {
  busy.value = true; error.value = ''; saved.value = ''
  try {
    const result = await call('customers.save_address', form.value, true)
    if (result.is_default) try { localStorage.setItem(`lc-address:${session.value.user}`, result.name) } catch { /* Server default remains available. */ }
    await load(); notifyAddress(result.is_default ? result.name : ''); editing.value = false; form.value = emptyAddress(); saved.value = 'Address saved.'
  }
  catch (e) { error.value = e.message }
  finally { busy.value = false }
}
async function setDefault(address) {
  busy.value = true; error.value = ''
  try { await call('customers.save_address', { ...address, is_default: 1 }, true); try { localStorage.setItem(`lc-address:${session.value.user}`, address.name) } catch { /* Server default remains available. */ } await load(); notifyAddress(address.name); saved.value = `${address.address_label} is now your delivery address.` }
  catch (e) { error.value = e.message }
  finally { busy.value = false }
}
async function archiveAddress(address) {
  busy.value = true; error.value = ''
  try { await call('customers.archive_address', { name: address.name }, true); await load(); notifyAddress(data.value.addresses.find(row => row.is_default)?.name || ''); saved.value = 'Address removed.' }
  catch (e) { error.value = e.message }
  finally { busy.value = false }
}
onMounted(async () => {
  window.addEventListener('lc-add-address', openNewAddress)
  if (session.value.user !== 'Guest') await load()
  if (route.query.add === '1') await openNewAddress()
})
onBeforeUnmount(() => window.removeEventListener('lc-add-address', openNewAddress))
</script>

<template>
  <div class="store-page account-page">
    <AuthChoices v-if="session.user === 'Guest'" />
    <template v-else>
      <header class="account-heading"><div><span class="eyebrow">YOUR LOCAL ACCOUNT</span><h1>Hello, {{ session.full_name.split(' ')[0] }}.</h1><p>{{ session.user }}</p></div><RouterLink class="primary" to="/orders">My orders →</RouterLink></header>
      <p v-if="loading" role="status">Loading account…</p>
      <p v-if="error" class="lc-notice" role="alert">{{ error }} <button v-if="!data" @click="load()">Retry</button></p>
      <p v-if="saved" class="success-note" role="status">{{ saved }}</p>
      <template v-if="data">
        <section class="address-book">
          <div class="section-title"><div><span class="eyebrow">DELIVERY LOCATIONS</span><h2>Saved addresses</h2><p>Choose where nearby shops should deliver.</p></div><button class="lc-primary" :disabled="busy" @click="newAddress">+ Add address</button></div>
          <div v-if="data.addresses.length" class="address-grid">
            <article v-for="address in data.addresses" :key="address.name" class="address-card" :class="{ default: address.is_default }"><header><span class="address-icon" aria-hidden="true">{{ address.address_type === 'Home' ? '⌂' : address.address_type === 'Work' ? '▦' : '⌖' }}</span><div><span class="eyebrow">{{ address.address_type }}</span><h3>{{ address.address_label }}</h3></div><span v-if="address.is_default" class="status-pill">Selected</span></header><strong>{{ address.recipient }}</strong><p>{{ address.line1 }}<br>{{ address.city }} · {{ address.postal_code }}</p><small>{{ address.phone }}</small><footer><button :disabled="busy" @click="editAddress(address)">Edit</button><button v-if="!address.is_default" :disabled="busy" @click="setDefault(address)">Use for delivery</button><button class="text-danger" :disabled="busy" @click="archiveAddress(address)">Remove</button></footer></article>
          </div>
          <p v-else class="lc-empty">Add Home, Work, or another address to discover shops that deliver nearby.</p>
        </section>
        <form v-if="editing" ref="editor" class="address-editor" @submit.prevent="saveAddress">
          <div class="section-title"><div><span class="eyebrow">{{ form.name ? 'EDIT ADDRESS' : 'NEW ADDRESS' }}</span><h2>{{ form.name ? form.address_label : 'Where should we deliver?' }}</h2></div><button type="button" :disabled="busy" @click="cancelEdit">Close</button></div>
          <fieldset :disabled="busy"><div class="form-columns"><label>Type<select v-model="form.address_type" required><option>Home</option><option>Work</option><option>Other</option></select></label><label>Label<input v-model="form.address_label" required maxlength="80" placeholder="Home"></label></div><div class="form-columns"><label>Recipient<input v-model="form.recipient" required maxlength="140" autocomplete="name"></label><label>Phone<input v-model="form.phone" required maxlength="30" type="tel" autocomplete="tel"></label></div><label>Street address<input v-model="form.line1" required maxlength="140" autocomplete="street-address"></label><div class="form-columns"><label>City<input v-model="form.city" required maxlength="100" autocomplete="address-level2"></label><label>Postal code<input v-model="form.postal_code" required maxlength="20" autocomplete="postal-code"></label></div><div class="location-heading"><div><strong>Map location</strong><small>Tap the map to place your delivery pin.</small></div><button type="button" :disabled="locating" @click="useLocation">{{ locating ? 'Finding…' : 'Use my location' }}</button></div><MapView :config="data.map" :points="addressPoints" editable @pick="pickLocation" /><label class="check-label"><input v-model="form.is_default" type="checkbox"><span>Use as my delivery address<small>Nearby shops will be sorted for this location.</small></span></label><button class="lc-primary">{{ busy ? 'Saving…' : 'Save address' }}</button></fieldset>
        </form>
        <section class="account-history"><span class="eyebrow">PURCHASES</span><h2>Recent order history</h2><p v-if="!data.orders.length" class="lc-empty">No previous sales orders.</p><article v-for="order in data.orders" :key="order.name" class="order-card"><strong>{{ order.name }}</strong><p>{{ order.transaction_date }} · {{ order.status }}</p><span>{{ order.currency }} {{ order.grand_total }}</span></article><div class="lc-pagination"><button :disabled="loading || !start" @click="load(-20)">Previous</button><span>Page {{ start / 20 + 1 }}</span><button :disabled="loading || data.orders.length < 20" @click="load(20)">Next</button></div></section>
      </template>
    </template>
  </div>
</template>
