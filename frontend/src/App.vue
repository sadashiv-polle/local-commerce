<script setup>
import { computed, onBeforeUnmount, onMounted, provide, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { call, setCsrfToken } from './api.js'
import { activeCart, loginUrl } from './cart.js'
const session = ref(null), error = ref(''), loggingOut = ref(false), logoutError = ref('')
const route = useRoute(), router = useRouter()
const logoutDialog = ref(null), headerAddressMenu = ref(null)
const savedCart = ref(null)
const headerAddresses = ref([]), headerAddress = ref(null)
const savedCartLines = computed(() => Object.keys(savedCart.value?.cart || {}).length)
const savedCartTotal = computed(() => Object.values(savedCart.value?.cart || {}).reduce((sum, item) => sum + Number(item.rate) * Number(item.quantity), 0))
const savedCartCurrency = computed(() => Object.values(savedCart.value?.cart || {})[0]?.currency)
function syncSavedCart() {
  try { savedCart.value = activeCart(localStorage) } catch { savedCart.value = null }
}
function savedCartMoney() {
  if (!savedCartCurrency.value) return ''
  return new Intl.NumberFormat(undefined, { style: 'currency', currency: savedCartCurrency.value }).format(savedCartTotal.value)
}
async function openSavedCart() {
  if (!savedCart.value) return
  if (route.name === 'customer-shop' && route.params.shop === savedCart.value.shop) {
    window.dispatchEvent(new CustomEvent('lc-open-cart'))
    return
  }
  await router.push({ name: 'customer-shop', params: { shop: savedCart.value.shop }, query: { cart: '1' } })
}
function confirmLogout() { logoutError.value = ''; logoutDialog.value.showModal() }
function cancelLogout(event) {
  if (loggingOut.value) { event?.preventDefault(); return }
  logoutDialog.value.close()
}
const ownerView = computed(() => route.path === '/shop' || route.path.startsWith('/shop/'))
const deliveryView = computed(() => route.path === '/delivery')
const canManage = computed(() => session.value && (session.value.platform_admin || session.value.memberships.some(m => ['Owner', 'Staff'].includes(m.membership_role))))
const canDeliver = computed(() => session.value?.roles.includes('LC Delivery Person') && session.value.memberships.some(m => m.membership_role === 'Driver'))
provide('session', session)
async function loadHeaderAddress(preferred = '') {
  headerAddresses.value = []; headerAddress.value = null
  if (!session.value || session.value.user === 'Guest' || !session.value.roles.includes('LC Customer')) return
  try {
    headerAddresses.value = await call('customers.addresses')
    let remembered = preferred
    if (!remembered) try { remembered = localStorage.getItem(`lc-address:${session.value.user}`) || '' } catch { /* Use the server default. */ }
    headerAddress.value = headerAddresses.value.find(address => address.name === remembered) || headerAddresses.value.find(address => address.is_default) || headerAddresses.value[0] || null
  } catch { /* The storefront remains available without a header address. */ }
}
function syncHeaderAddress(event) {
  const name = typeof event.detail === 'string' ? event.detail : ''
  const existing = headerAddresses.value.find(address => address.name === name)
  if (existing) headerAddress.value = existing
  else loadHeaderAddress(name)
}
function chooseHeaderAddress(address) {
  headerAddress.value = address
  try { localStorage.setItem(`lc-address:${session.value.user}`, address.name) } catch { /* Selection still applies now. */ }
  window.dispatchEvent(new CustomEvent('lc-address-change', { detail: address.name }))
  headerAddressMenu.value?.removeAttribute('open')
}
async function addHeaderAddress() {
  headerAddressMenu.value?.removeAttribute('open')
  if (session.value?.user === 'Guest') { await router.push({ path: '/login', query: { next: '/account?add=1' } }); return }
  await router.push({ path: '/account', query: { add: '1' } })
  window.dispatchEvent(new CustomEvent('lc-add-address'))
}
function closeHeaderAddressMenu(event) {
  if (headerAddressMenu.value?.open && !headerAddressMenu.value.contains(event.target)) headerAddressMenu.value.removeAttribute('open')
}
async function load() {
  error.value = ''
  try {
    session.value = await call('session.context'); setCsrfToken(session.value.csrf_token)
    if (session.value.roles.includes('LC Customer')) {
      // Account linking is a POST; public browsing remains usable if setup needs attention.
      try { await call('customers.ensure', {}, true); await loadHeaderAddress() } catch { /* Account/checkout show actionable errors. */ }
    }
    if (route.path === '/') await router.replace(canManage.value ? '/shop' : canDeliver.value ? '/delivery' : '/store')
  } catch (e) { error.value = e.message }
}
async function logout() {
  if (loggingOut.value) return
  loggingOut.value = true; logoutError.value = ''
  try {
    await call('session.logout', {}, true)
    window.location.assign('/local-commerce#/store')
    window.location.reload()
  } catch { logoutError.value = 'Could not log out. Please retry.' }
  finally { loggingOut.value = false }
}
onMounted(() => {
  syncSavedCart()
  window.addEventListener('storage', syncSavedCart)
  window.addEventListener('lc-cart-change', syncSavedCart)
  window.addEventListener('lc-address-change', syncHeaderAddress)
  document.addEventListener('click', closeHeaderAddressMenu)
  load()
})
onBeforeUnmount(() => {
  window.removeEventListener('storage', syncSavedCart)
  window.removeEventListener('lc-cart-change', syncSavedCart)
  window.removeEventListener('lc-address-change', syncHeaderAddress)
  document.removeEventListener('click', closeHeaderAddressMenu)
})
</script>

<template>
  <div class="commerce-app" :class="{ 'owner-view': ownerView, 'delivery-view': deliveryView, 'customer-view': !ownerView && !deliveryView, 'has-global-cart': savedCartLines }">
    <header class="topbar">
      <div class="brand-stack"><RouterLink class="brand" to="/store">local<span>●</span><small v-if="ownerView || deliveryView">{{ ownerView ? 'BUSINESS' : 'DELIVERY' }}</small></RouterLink><details v-if="!ownerView && !deliveryView" ref="headerAddressMenu" class="header-address-menu"><summary class="header-delivery-address"><small>DELIVERING TO</small><strong v-if="headerAddress">{{ headerAddress.address_label }} · {{ headerAddress.line1 }}</strong><strong v-else>{{ session?.user === 'Guest' ? 'Choose delivery location' : 'Add delivery address' }}</strong><span aria-hidden="true">⌄</span></summary><div class="header-address-options"><span class="eyebrow">SAVED ADDRESSES</span><button v-for="address in headerAddresses" :key="address.name" type="button" :class="{ selected: address.name === headerAddress?.name }" @click="chooseHeaderAddress(address)"><span class="address-icon" aria-hidden="true">{{ address.address_type === 'Home' ? '⌂' : address.address_type === 'Work' ? '▦' : '⌖' }}</span><span><strong>{{ address.address_label }}</strong><small>{{ address.line1 }} · {{ address.city }}</small></span><b v-if="address.name === headerAddress?.name">✓</b></button><p v-if="!headerAddresses.length">No saved addresses yet.</p><button type="button" class="header-add-address" @click="addHeaderAddress">+ {{ session?.user === 'Guest' ? 'Login to add address' : 'Add address' }}</button></div></details></div>
      <div class="header-note"><span class="pin" aria-hidden="true">⌖</span><div><strong>{{ ownerView ? 'Your business workspace' : deliveryView ? 'Your rider workspace' : 'Good things start nearby' }}</strong><small>{{ ownerView ? 'A little more connected.' : deliveryView ? 'Every order, right on track.' : 'Delivery from your local shops' }}</small></div></div>
      <nav aria-label="Main navigation"><RouterLink v-if="canManage" :to="ownerView ? '/store' : '/shop'">{{ ownerView ? 'View storefront ↗' : 'Shop workspace ↗' }}</RouterLink><RouterLink v-if="canDeliver" to="/delivery">Deliveries</RouterLink><template v-if="session?.user === 'Guest'"><a :href="loginUrl(route.fullPath)">Login</a><RouterLink :to="{ path: '/signup', query: { next: route.fullPath } }">Sign Up / Create Account</RouterLink></template><RouterLink v-else-if="session" class="account" :to="session.roles.includes('LC Customer') ? '/account' : canDeliver ? '/delivery' : '/shop'"><span aria-hidden="true">{{ session.full_name?.slice(0, 1).toUpperCase() }}</span><span>{{ session.full_name }}</span></RouterLink><button v-if="session && session.user !== 'Guest'" class="logout-button" :disabled="loggingOut" aria-haspopup="dialog" @click="confirmLogout"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M9 4H5a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h4M14 8l4 4-4 4M9 12h10" stroke-linecap="round" stroke-linejoin="round" /></svg>Log out</button></nav>
    </header>
    <main>
      <div v-if="error" class="page-state" role="alert"><h1>Let's try that again.</h1><p>{{ error }}</p><button @click="load">Retry</button></div>
      <div v-else-if="!session" class="page-state" role="status"><span class="brand">local<span>●</span></span><p>Opening your neighbourhood…</p></div>
      <RouterView v-else />
    </main>
    <button v-if="savedCartLines" class="floating-cart-bar global-cart-bar" type="button" aria-label="Open saved cart" @click="openSavedCart"><span class="cart-bag" aria-hidden="true">▣</span><span><strong>{{ savedCartLines }} {{ savedCartLines === 1 ? 'item' : 'items' }}</strong><small>{{ savedCartMoney() }}</small></span><strong>View cart&nbsp; ›</strong></button>
    <dialog ref="logoutDialog" class="logout-dialog" aria-labelledby="logout-title" aria-describedby="logout-description" :aria-busy="loggingOut" @cancel="cancelLogout">
      <div class="logout-symbol" aria-hidden="true">↗</div>
      <span class="eyebrow">YOUR ACCOUNT</span>
      <h2 id="logout-title">Log out of Local?</h2>
      <p id="logout-description">You’ll return to the public store. Your cart will stay saved on this device.</p>
      <p v-if="logoutError" class="lc-notice" role="alert">{{ logoutError }}</p>
      <div class="logout-actions"><button :disabled="loggingOut" autofocus @click="cancelLogout">Stay logged in</button><button class="logout-confirm" :disabled="loggingOut" @click="logout">{{ loggingOut ? 'Logging out…' : 'Yes, log out' }}</button></div>
    </dialog>
    <footer class="app-footer"><span class="brand">local<span>●</span></span><span>A little closer to your neighbourhood.</span><small>Local Commerce</small></footer>
  </div>
</template>
