<script setup>
import { computed, inject, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { call } from './api.js'
import ProfileAvatar from './ProfileAvatar.vue'
import AuthChoices from './AuthChoices.vue'
import MapView from './MapView.vue'

const session = inject('session')
const route = useRoute(), router = useRouter()
const data = ref(null), error = ref(''), saved = ref(''), loading = ref(false), busy = ref(false), locating = ref(false)
const editing = ref(false), editor = ref(null)
let locationGeneration = 0
const emptyAddress = () => ({ name: '', address_type: 'Home', address_label: 'Home', recipient: session.value?.full_name || '', phone: '', line1: '', city: '', postal_code: '', latitude: '', longitude: '', is_default: false })
const form = ref(emptyAddress()), selectedAddress = ref('')
const addressPoints = computed(() => form.value.latitude != null && form.value.longitude != null && form.value.latitude !== '' && form.value.longitude !== '' && Number.isFinite(Number(form.value.latitude)) && Number.isFinite(Number(form.value.longitude)) ? [{ ...form.value, kind: 'customer', label: form.value.address_label || 'Saved address' }] : [])
function syncSelection(event) { selectedAddress.value = typeof event.detail === 'string' ? event.detail : '' }
onMounted(() => window.addEventListener('lc-address-change', syncSelection))
onBeforeUnmount(() => window.removeEventListener('lc-address-change', syncSelection))
function notifyAddress(name = '') { window.dispatchEvent(new CustomEvent('lc-address-change', { detail: name })) }

async function load() {
  loading.value = true; error.value = ''
  try { data.value = await call('customers.account', {}, true); selectedAddress.value = sessionStorage.getItem(`lc-selected-address:${session.value.user}`) || '' }
  catch (e) { error.value = e.message }
  finally { loading.value = false }
}
function openNewAddress() { router.push({ path: '/account', query: { add: '1' } }) }
function editAddress(address) { router.push({ path: '/account', query: { edit: address.name } }) }
function cancelEdit() {
  locationGeneration++; locating.value = false
  editing.value = false; form.value = emptyAddress()
  router.replace({ path: '/account' })
}
async function syncEditor() {
  if (!data.value) return
  locationGeneration++; locating.value = false
  const address = data.value.addresses.find(row => row.name === route.query.edit)
  if (address || route.query.add === '1') {
    form.value = address ? { ...address } : emptyAddress()
    editing.value = true; saved.value = ''; error.value = ''
    await nextTick()
    window.scrollTo({ top: 0, behavior: 'instant' })
    editor.value?.querySelector('h2')?.focus({ preventScroll: true })
  } else {
    editing.value = false; form.value = emptyAddress()
    if (route.query.edit) error.value = 'This saved address is no longer available.'
  }
}
watch([() => route.query.edit, () => route.query.add, data], syncEditor)
function pickLocation(point) {
  form.value.latitude = point.latitude; form.value.longitude = point.longitude; error.value = ''
  if (point.address_line1) form.value.line1 = point.address_line1
  if (point.city) form.value.city = point.city
  if (point.postal_code) form.value.postal_code = point.postal_code
}
function useLocation() {
  error.value = ''
  if (!navigator.geolocation) { error.value = 'Location is unavailable. Tap the map to choose the location.'; return }
  const request = ++locationGeneration
  locating.value = true
  navigator.geolocation.getCurrentPosition(
    position => { if (request === locationGeneration && editing.value) { pickLocation(position.coords); locating.value = false } },
    () => { if (request !== locationGeneration || !editing.value) return; error.value = window.isSecureContext ? 'Location access failed. Allow it or tap the map.' : 'Automatic location needs HTTPS. Tap the map to place the pin.'; locating.value = false },
    { enableHighAccuracy: true, timeout: 12000, maximumAge: 30000 },
  )
}
async function saveAddress() {
  busy.value = true; error.value = ''; saved.value = ''
  try {
    const useForDelivery = form.value.is_default
    const result = await call('customers.save_address', form.value, true)
    if (useForDelivery) try { sessionStorage.setItem(`lc-selected-address:${session.value.user}`, result.name) } catch { /* Server default remains available. */ }
    await load(); notifyAddress(useForDelivery ? result.name : selectedAddress.value); cancelEdit(); saved.value = 'Address saved.'
  }
  catch (e) { error.value = e.message }
  finally { busy.value = false }
}
async function setDefault(address) {
  busy.value = true; error.value = ''
  try { await call('customers.save_address', { ...address, is_default: 1 }, true); try { sessionStorage.setItem(`lc-selected-address:${session.value.user}`, address.name) } catch { /* Server default remains available. */ } await load(); notifyAddress(address.name); saved.value = `${address.address_label} is now your delivery address.` }
  catch (e) { error.value = e.message }
  finally { busy.value = false }
}
async function archiveAddress(address) {
  if (!window.confirm(`Remove ${address.address_label} from your saved addresses? Existing orders will keep their delivery details.`)) return
  busy.value = true; error.value = ''
  try { await call('customers.archive_address', { name: address.name }, true); if (selectedAddress.value === address.name) sessionStorage.removeItem(`lc-selected-address:${session.value.user}`); await load(); notifyAddress(selectedAddress.value); saved.value = 'Address removed.' }
  catch (e) { error.value = e.message }
  finally { busy.value = false }
}
onMounted(async () => {
  window.addEventListener('lc-add-address', openNewAddress)
  if (session.value.user !== 'Guest') await load()
  await syncEditor()
})
onBeforeUnmount(() => { locationGeneration++; window.removeEventListener('lc-add-address', openNewAddress) })
</script>

<template>
  <div class="store-page account-page">
    <AuthChoices v-if="session.user === 'Guest'" />
    <template v-else>
      <header v-if="!editing" class="account-hero">
        <ProfileAvatar :name="session.full_name" :image="session.user_image" />
        <div><span class="eyebrow">YOUR ACCOUNT</span><h1>{{ session.full_name || 'Welcome to Local' }}</h1><p>{{ session.user }}</p><small v-if="session.username">Username: <strong>{{ session.username }}</strong> · {{ session.username_login_enabled ? 'You can use this to log in' : 'Log in with your email' }}</small></div>
      </header>
      <nav v-if="!editing" class="account-shortcuts" aria-label="Account shortcuts">
        <RouterLink to="/orders"><span aria-hidden="true">▤</span><div><strong>My orders</strong><small>Track deliveries & buy again</small></div><b aria-hidden="true">›</b></RouterLink>
        <RouterLink to="/favourites"><span aria-hidden="true">♡</span><div><strong>Favourites</strong><small>Your saved products</small></div><b aria-hidden="true">›</b></RouterLink>
        <RouterLink to="/store"><span aria-hidden="true">⌂</span><div><strong>Continue shopping</strong><small>Explore your local shops</small></div><b aria-hidden="true">›</b></RouterLink>
      </nav>
      <p v-if="loading" role="status">Loading account…</p>
      <p v-if="error" class="lc-notice" role="alert">{{ error }} <button v-if="!data" @click="load()">Retry</button></p>
      <p v-if="saved" class="success-note" role="status">{{ saved }}</p>
      <template v-if="data">
        <section v-if="!editing" class="address-book">
          <div class="section-title"><div><span class="eyebrow">DELIVERY LOCATIONS</span><h2>Saved addresses <small class="address-count">{{ data.addresses.length }}</small></h2><p>Choose where nearby shops should deliver.</p></div><button class="lc-primary" :disabled="busy" @click="openNewAddress">+ Add address</button></div>
          <div v-if="data.addresses.length" class="address-grid">
            <article v-for="address in data.addresses" :key="address.name" class="address-card" :class="{ default: address.name === selectedAddress }"><header><span class="address-icon" aria-hidden="true">{{ address.address_type === 'Home' ? '⌂' : address.address_type === 'Work' ? '▦' : '⌖' }}</span><div><span class="eyebrow">{{ address.address_type }}</span><h3>{{ address.address_label }}</h3></div><span v-if="address.name === selectedAddress" class="status-pill">Selected</span></header><strong>{{ address.recipient }}</strong><p>{{ address.line1 }}<br>{{ address.city }} · {{ address.postal_code }}</p><small>{{ address.phone }}</small><footer><button :disabled="busy" @click="editAddress(address)">Edit</button><button v-if="address.name !== selectedAddress" :disabled="busy" @click="setDefault(address)">Use for delivery</button><button class="text-danger" :disabled="busy" @click="archiveAddress(address)">Remove</button></footer></article>
          </div>
          <p v-else class="lc-empty">Add Home, Work, or another address to discover shops that deliver nearby.</p>
        </section>
        <form v-if="editing" ref="editor" class="address-editor address-editor-page" @submit.prevent="saveAddress">
          <button type="button" class="address-editor-back" :disabled="busy" @click="cancelEdit">← Back to saved addresses</button>
          <div class="section-title"><div><span class="eyebrow">{{ form.name ? 'EDIT ADDRESS' : 'NEW ADDRESS' }}</span><h2 tabindex="-1">{{ form.name ? `Edit ${form.address_label}` : 'Where should we deliver?' }}</h2></div><button type="button" :disabled="busy" @click="cancelEdit">Close</button></div>
          <fieldset :disabled="busy"><div class="form-columns"><label>Type<select v-model="form.address_type" required><option>Home</option><option>Work</option><option>Other</option></select></label><label>Label<input v-model="form.address_label" required maxlength="80" placeholder="Home"></label></div><div class="form-columns"><label>Recipient<input v-model="form.recipient" required maxlength="140" autocomplete="name"></label><label>Phone<input v-model="form.phone" required maxlength="30" type="tel" autocomplete="tel"></label></div><label>Street address<input v-model="form.line1" required maxlength="140" autocomplete="street-address"></label><div class="form-columns"><label>City<input v-model="form.city" required maxlength="100" autocomplete="address-level2"></label><label>Postal code<input v-model="form.postal_code" required maxlength="20" autocomplete="postal-code"></label></div><div class="location-heading"><div><strong>Map location</strong><small>Tap the map to place your delivery pin.</small></div><button type="button" :disabled="locating" @click="useLocation">{{ locating ? 'Finding…' : 'Use my location' }}</button></div><MapView :config="data.map" :points="addressPoints" editable @pick="pickLocation" /><label class="check-label"><input v-model="form.is_default" type="checkbox"><span>Use as my delivery address<small>Nearby shops will be sorted for this location.</small></span></label><button class="lc-primary account-save-address">{{ busy ? 'Saving…' : 'Save address' }}</button></fieldset>
        </form>
      </template>
    </template>
  </div>
</template>

<style>
#lc-app .account-page { max-width: 1100px; margin-inline: auto; }
#lc-app .account-hero { display: flex; align-items: center; gap: 20px; padding: 26px; border: 1px solid #dce6dc; border-radius: 22px; background: linear-gradient(120deg, #edf5e9, #fafbf7); }
#lc-app .account-hero > div { min-width: 0; }
#lc-app .account-hero .profile-photo-avatar { display: grid; place-items: center; width: 76px; height: 76px; flex-shrink: 0; border-radius: 50%; color: #176547; background: #fff; border: 3px solid white; font-size: 32px; font-weight: 750; }
#lc-app .account-hero h1 { margin: 6px 0; font-size: clamp(23px, 3vw, 32px); line-height: 1.2; overflow-wrap: anywhere; }
#lc-app .account-hero p { margin: 4px 0; font-size: 14px; overflow-wrap: anywhere; }
#lc-app .account-hero small { font-size: 12px; color: #657869; overflow-wrap: anywhere; }
#lc-app .account-shortcuts { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin: 18px 0 30px; }
#lc-app .account-shortcuts a { display: flex; align-items: center; gap: 12px; padding: 16px; border: 1px solid #dce6dc; border-radius: 16px; background: white; text-decoration: none; color: #214a36; }
#lc-app .account-shortcuts a > span { font-size: 25px; }
#lc-app .account-shortcuts a > div { display: grid; flex: 1; min-width: 0; }
#lc-app .account-shortcuts small { font-size: 12px; color: #687a6d; }
#lc-app .account-shortcuts a:hover { border-color: #7eaf91; background: #f7faf5; }
#lc-app .account-page .address-count { display: inline-grid; place-items: center; min-width: 26px; height: 26px; padding: 0 7px; font-size: 13px; border-radius: 20px; background: #edf4e9; vertical-align: middle; }
#lc-app .account-page .address-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
#lc-app .account-page .address-card { padding: 20px; border-radius: 18px; display: flex; flex-direction: column; min-width: 0; background: white; }
#lc-app .account-page .address-card.default { border-color: #35805b; background: #f5faf3; }
#lc-app .account-page .address-card p, #lc-app .account-page .address-card strong { overflow-wrap: anywhere; }
#lc-app .account-page .address-card footer { margin-top: auto; padding-top: 16px; display: flex; flex-wrap: wrap; gap: 8px; }
#lc-app .account-page .address-card footer button { min-height: 44px; padding: 9px 12px; font-size: 13px; border-radius: 10px; }
#lc-app .account-page .address-editor-page { max-width: 760px; margin-inline: auto; border-radius: 20px; }
#lc-app .account-page .account-save-address { min-height: 48px; margin-top: 16px; }
@media(max-width:600px) {
  #lc-app .account-hero { padding: 18px; gap: 12px; border-radius: 18px; align-items: flex-start; }
  #lc-app .account-hero .profile-photo-avatar { width: 54px; height: 54px; font-size: 25px; }
  #lc-app .account-shortcuts { grid-template-columns: 1fr; gap: 8px; margin: 14px 0 24px; }
  #lc-app .account-shortcuts a { padding: 12px 14px; }
  #lc-app .account-page .address-grid { grid-template-columns: minmax(0, 1fr); }
  #lc-app .account-page .address-book > .section-title { flex-wrap: wrap; gap: 12px; }
  #lc-app .account-page .address-book h2 { font-size: 22px; }
  #lc-app .account-page .address-card { padding: 16px; }
  #lc-app .account-page .account-save-address { width: 100%; }
}
</style>
