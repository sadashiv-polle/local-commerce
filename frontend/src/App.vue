<script setup>
import { computed, onBeforeUnmount, onMounted, provide, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { call, setCsrfToken } from './api.js'
import { activeCart, loginUrl } from './cart.js'
const session = ref(null), error = ref(''), loggingOut = ref(false), logoutError = ref('')
const route = useRoute(), router = useRouter()
const logoutDialog = ref(null)
const savedCart = ref(null)
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
async function load() {
  error.value = ''
  try {
    session.value = await call('session.context'); setCsrfToken(session.value.csrf_token)
    if (session.value.roles.includes('LC Customer')) {
      // Account linking is a POST; public browsing remains usable if setup needs attention.
      try { await call('customers.ensure', {}, true) } catch { /* Account/checkout show actionable errors. */ }
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
  load()
})
onBeforeUnmount(() => {
  window.removeEventListener('storage', syncSavedCart)
  window.removeEventListener('lc-cart-change', syncSavedCart)
})
</script>

<template>
  <div class="commerce-app" :class="{ 'owner-view': ownerView, 'has-global-cart': savedCartLines }">
    <header class="topbar">
      <RouterLink class="brand" to="/store">local<span>●</span><small>{{ ownerView ? 'BUSINESS' : deliveryView ? 'DELIVERY' : 'YOUR NEIGHBOURHOOD, TOGETHER' }}</small></RouterLink>
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
