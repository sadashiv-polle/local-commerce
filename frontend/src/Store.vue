<script setup>
import { computed, inject, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { call } from './api.js'
import FavouriteButton from './FavouriteButton.vue'
const session = inject('session')
const featured = ref({ title: '', items: [] }), featuredRow = ref(null)
onMounted(async () => { try { featured.value = await call('storefront.featured') } catch { /* Shop browsing stays available. */ } })
const productSearch = ref(''), productResults = ref([]), productLoading = ref(false), productError = ref(''), productStart = ref(0), productMore = ref(false)
let searchTimer, searchGeneration = 0
function money(value, currency) { return value == null ? 'Price coming soon' : new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(value) }
async function findProducts(delta = 0) {
  const current = ++searchGeneration
  productStart.value = Math.max(0, productStart.value + delta)
  if (productSearch.value.trim().length < 2) { productResults.value = []; productLoading.value = false; productMore.value = false; return }
  productLoading.value = true; productError.value = ''
  try {
    const result = await call('orders.search_products', { search: productSearch.value, start: productStart.value, ...(activeAddress.value?.latitude != null && activeAddress.value?.longitude != null ? { latitude: activeAddress.value.latitude, longitude: activeAddress.value.longitude } : {}) })
    if (current === searchGeneration) { productResults.value = result.items; productMore.value = result.has_more }
  } catch (e) { if (current === searchGeneration) productError.value = e.message }
  finally { if (current === searchGeneration) productLoading.value = false }
}
function scheduleProductSearch() {
  window.clearTimeout(searchTimer); searchGeneration++; productStart.value = 0; productResults.value = []; productError.value = ''; productMore.value = false
  productLoading.value = productSearch.value.trim().length >= 2
  searchTimer = window.setTimeout(() => findProducts(), 350)
}
watch(productSearch, scheduleProductSearch)
onBeforeUnmount(() => { window.clearTimeout(searchTimer); searchGeneration++ })
const shops = ref([]), addresses = ref([]), selectedAddress = ref(''), error = ref(''), start = ref(0), loading = ref(false), hasMore = ref(false)
const activeAddress = computed(() => addresses.value.find(address => address.name === selectedAddress.value))
async function load(delta = 0) {
  start.value = Math.max(0, start.value + delta); loading.value = true; error.value = ''
  try {
    if (selectedAddress.value) {
      const result = await call('customers.nearby', { address: selectedAddress.value, start: start.value })
      shops.value = result.shops; hasMore.value = result.has_more
    } else {
      shops.value = await call('orders.shops', { start: start.value }); hasMore.value = shops.value.length === 20
    }
  } catch(e) { error.value = e.message }
  finally { loading.value = false }
}
async function loadAddresses() {
  if (session.value.user === 'Guest' || !session.value.roles.includes('LC Customer')) { await load(); return }
  try {
    addresses.value = await call('customers.addresses')
    const key = `lc-address:${session.value.user}`
    let remembered = ''
    try { remembered = localStorage.getItem(key) || '' } catch { /* Use the server default. */ }
    selectedAddress.value = addresses.value.some(address => address.name === remembered) ? remembered : addresses.value.find(address => address.is_default)?.name || addresses.value[0]?.name || ''
  } catch { addresses.value = []; selectedAddress.value = '' }
  await load()
}
async function selectAddress() {
  start.value = 0
  try { localStorage.setItem(`lc-address:${session.value.user}`, selectedAddress.value) } catch { /* Selection still works for this page. */ }
  window.dispatchEvent(new CustomEvent('lc-address-change', { detail: selectedAddress.value }))
  await load()
}
watch(activeAddress, scheduleProductSearch)
onMounted(loadAddresses)
const browse = ref(null)
</script>

<template>
  <div class="store-page">
    <section class="store-hero">
      <div><span class="eyebrow">GOOD THINGS, CLOSE TO HOME</span><h1>Your neighbourhood.<br>Your everyday essentials.</h1><p>Fresh finds and familiar favourites.<br>Discover a better way to shop local.</p><button class="primary" @click="browse?.scrollIntoView()">Explore the neighbourhood <span>↗</span></button></div>
      <div class="hero-art" aria-hidden="true"><span class="art-label">FRESH · LOCAL · EVERYDAY</span><div class="produce">🥬<span>🍊</span>🥖</div><div class="market-bag">local<span>good things inside.</span></div><span class="art-sticker">A little<br>closer.</span></div>
    </section>
    <section class="home-product-search" aria-label="Search products across shops">
      <label class="product-search"><span aria-hidden="true">⌕</span><input v-model="productSearch" type="search" maxlength="140" placeholder="Search Bangda, milk, vegetables…" aria-label="Search products across shops"><button v-if="productSearch" type="button" aria-label="Clear product search" @click="productSearch = ''">×</button></label>
      <template v-if="productSearch.trim().length >= 2"><div class="section-title"><h2>Products from local shops</h2><small>{{ activeAddress ? 'Sorted by delivery availability and distance' : 'Choose an address to check nearby delivery' }}</small></div><p v-if="productLoading" role="status">Finding products…</p><p v-if="productError" role="alert" class="lc-notice">{{ productError }}</p><p v-if="!productLoading && !productError && !productResults.length" class="lc-empty">No matching products. Try another name.</p><div class="home-search-grid"><div v-for="item in productResults" :key="`${item.shop}:${item.item}`" class="home-search-product-wrap"><FavouriteButton :item="item.item" :shop="item.shop" /><RouterLink class="lc-card home-search-product" :to="{ name: 'customer-shop', params: { shop: item.shop }, query: { item: item.item } }"><div class="product-art"><img v-if="item.image" :src="item.image" :alt="item.item_name" loading="lazy" @error="item.image = ''"><span v-else aria-hidden="true">{{ item.item_name.slice(0, 1).toUpperCase() }}</span></div><small class="search-shop-name">{{ item.shop_name }}{{ item.distance_km != null ? ` · ${Number(item.distance_km).toFixed(1)} km` : '' }}</small><h3>{{ item.item_name }}</h3><strong>{{ money(item.rate, item.currency) }} <small>/ {{ item.uom }}</small></strong><p class="search-stock">{{ item.available > 0 ? 'In stock' : 'Sold out' }}</p><small class="serviceability-line" :class="{ available: item.serviceable }">{{ item.serviceability_message }}</small><span class="lc-card-link">View item →</span></RouterLink></div></div><div v-if="productResults.length" class="lc-pagination"><button :disabled="!productStart || productLoading" @click="findProducts(-20)">Previous</button><button :disabled="!productMore || productLoading" @click="findProducts(20)">Next</button></div></template>
    </section>
    <RouterLink v-if="session.platform_admin" class="storefront-admin-link" to="/store-settings">Manage featured products →</RouterLink>
    <section v-if="featured.items.length" class="featured-section"><div class="section-title"><div><span class="eyebrow">FROM YOUR LOCAL SHOPS</span><h2>{{ featured.title }}</h2></div><div class="featured-arrows"><button aria-label="Previous featured products" @click="featuredRow.scrollBy({ left: -300, behavior: 'smooth' })">←</button><button aria-label="Next featured products" @click="featuredRow.scrollBy({ left: 300, behavior: 'smooth' })">→</button></div></div><div ref="featuredRow" class="featured-product-row"><div v-for="item in featured.items" :key="item.item" class="home-search-product-wrap"><FavouriteButton :item="item.item" :shop="item.shop" /><RouterLink class="lc-card home-search-product" :to="{ name: 'customer-shop', params: { shop: item.shop }, query: { item: item.item } }"><div class="product-art"><img v-if="item.image" :src="item.image" :alt="item.item_name" loading="lazy" @error="item.image = ''"><span v-else aria-hidden="true">{{ item.item_name.slice(0, 1) }}</span></div><small class="search-shop-name">{{ item.shop_name }}</small><h3>{{ item.item_name }}</h3><strong>{{ money(item.rate, item.currency) }}<small> / {{ item.uom }}</small></strong><small>{{ item.available > 0 ? 'In stock' : 'Sold out' }}</small><span class="lc-card-link">View item →</span></RouterLink></div></div></section>
    <section ref="browse" class="browse-section">
      <div class="section-title"><h2>Explore local shops</h2><RouterLink to="/orders">My orders →</RouterLink></div>
      <div>
        <div v-if="addresses.length" class="delivery-location-bar"><span class="address-icon" aria-hidden="true">⌖</span><label><small>DELIVERING TO</small><select v-model="selectedAddress" :disabled="loading" @change="selectAddress"><option v-for="address in addresses" :key="address.name" :value="address.name">{{ address.address_label }} · {{ address.line1 }}</option></select></label><RouterLink to="/account">Manage</RouterLink></div>
        <div v-else class="delivery-location-bar"><span class="address-icon" aria-hidden="true">⌖</span><div><strong>Choose your delivery location</strong><small>Save an address to see shops that deliver nearby.</small></div><RouterLink :to="session.user === 'Guest' ? '/login?next=/account' : '/account'">{{ session.user === 'Guest' ? 'Login' : 'Add address' }} →</RouterLink></div>
        <p v-if="activeAddress" class="nearby-summary">Showing shops near <strong>{{ activeAddress.address_label }}</strong>, sorted by delivery availability and distance.</p>
        <p v-if="error" role="alert" class="lc-notice">{{ error }}</p><p v-if="loading" role="status">Loading shops…</p>
        <div class="lc-grid"><RouterLink v-for="shop in shops" :key="shop.name" class="lc-card nearby-shop-card" :class="{ unavailable: activeAddress && !shop.serviceable }" :to="{ name: 'customer-shop', params: { shop: shop.name } }"><div class="shop-card-badges"><span v-if="shop.location" class="shop-location-badge">⌖ {{ shop.city || 'Map location available' }}</span><span v-if="shop.distance_km != null" class="distance-badge">{{ Number(shop.distance_km).toFixed(1) }} km</span></div><h3>{{ shop.shop_name }}</h3><p><span class="shop-open-status" :class="{ closed: !shop.accepting_orders }">{{ shop.availability.label }}</span> {{ shop.availability.message }}</p><p>{{ shop.description }}</p><small v-if="shop.address_line1" class="shop-card-address">{{ shop.address_line1 }}{{ shop.city ? `, ${shop.city}` : '' }}</small><span v-if="activeAddress" class="serviceability-line" :class="{ available: shop.serviceable }">{{ shop.serviceable ? '✓' : '●' }} {{ shop.serviceability_message }}</span><span class="lc-card-link">Browse products →</span></RouterLink></div>
        <p v-if="!loading && !shops.length" class="lc-empty">No active shops are available yet.</p>
        <div class="lc-pagination"><button :disabled="!start || loading" @click="load(-20)">Previous</button><button :disabled="!hasMore || loading" @click="load(20)">Next</button><button :disabled="loading" @click="load()">Refresh</button></div>
      </div>
    </section>
    <div class="values"><div><strong>Local at heart</strong><p>Your neighbourhood businesses, together.</p></div><div><strong>Everyday made easier</strong><p>One place for the things you need.</p></div><div><strong>More choice, closer by</strong><p>From fresh produce to familiar favourites.</p></div></div>
  </div>
</template>
