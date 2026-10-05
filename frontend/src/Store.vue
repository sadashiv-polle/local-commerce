<script setup>
import StockAlertButton from './StockAlertButton.vue'
import { displayPrice } from './product-price.js'
import { computed, inject, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { call } from './api.js'
import { useRoute, useRouter } from 'vue-router'
import ActiveOrderShortcut from './ActiveOrderShortcut.vue'
import FavouriteButton from './FavouriteButton.vue'
import PromotionSlider from './PromotionSlider.vue'
import HomeShopCard from './HomeShopCard.vue'
const session = inject('session'), route = useRoute(), router = useRouter()
const shopsOnly = computed(() => route.query.browse === 'shops')
const featured = ref({ sections: [] }), featuredRows = ref({}), customerPicks = ref(null)
const displayedSections = computed(() => [...(customerPicks.value?.items?.length ? [customerPicks.value] : []), ...featured.value.sections])
let picksGeneration = 0
async function loadCustomerPicks() {
  const current = ++picksGeneration
  customerPicks.value = null
  if (session.value.user === 'Guest' || !session.value.roles.includes('LC Customer')) return
  try {
    const result = await call('storefront.recommendations', { address: selectedAddress.value })
    if (current === picksGeneration) customerPicks.value = result
  } catch { /* Suggestions never block browsing. */ }
}
const categoryMenu = ref({ categories: [] }), activeCategory = ref('')
const categoryLabel = computed(() => categoryMenu.value.categories.find(row => row.item_group === activeCategory.value)?.label || 'Products from local shops')
function categoryIcon(group) {
  return ({ Fish: '🐟', Seafood: '🦐', Rice: '🍚', Groceries: '🛒', Fruits: '🍎', Vegetables: '🥬', 'Meat & Poultry': '🍗', 'Dairy & Eggs': '🥛', Bakery: '🥖', 'Fast Food': '🍔', Snacks: '🍿', Beverages: '🧃', 'Household Essentials': '🧹', 'Personal Care': '🧴' })[group] || '🛍️'
}
async function chooseCategory(group) {
  activeCategory.value = group; productStart.value = 0; productResults.value = []
  await findProducts()
  productBrowse.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
const productBrowse = ref(null)
onMounted(async () => { try { categoryMenu.value = await call('storefront.category_menu', { available_only: 1 }) } catch { /* Product search remains available. */ } })
onMounted(async () => { try { featured.value = await call('storefront.featured') } catch { /* Shop browsing stays available. */ } })
const productSearch = ref(''), productResults = ref([]), productLoading = ref(false), productError = ref(''), productStart = ref(0), productMore = ref(false)
let searchTimer, searchGeneration = 0
function money(value, currency) { return value == null ? 'Price coming soon' : new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(value) }
async function findProducts(delta = 0) {
  if (shopsOnly.value) return
  const current = ++searchGeneration
  productStart.value = Math.max(0, productStart.value + delta)
  if (productSearch.value.trim().length < 2 && !activeCategory.value) { productResults.value = []; productLoading.value = false; productMore.value = false; return }
  productLoading.value = true; productError.value = ''
  try {
    const result = await call('orders.search_products', { search: productSearch.value, category: activeCategory.value, start: productStart.value, ...(activeAddress.value?.latitude != null && activeAddress.value?.longitude != null ? { latitude: activeAddress.value.latitude, longitude: activeAddress.value.longitude } : {}) })
    if (current === searchGeneration) { productResults.value = result.items; productMore.value = result.has_more }
  } catch (e) { if (current === searchGeneration) productError.value = e.message }
  finally { if (current === searchGeneration) productLoading.value = false }
}
function scheduleProductSearch() {
  window.clearTimeout(searchTimer); searchGeneration++; productStart.value = 0; productResults.value = []; productError.value = ''; productMore.value = false
  productLoading.value = productSearch.value.trim().length >= 2 || !!activeCategory.value
  searchTimer = window.setTimeout(() => { findProducts(); start.value = 0; load() }, 350)
}
watch(productSearch, scheduleProductSearch)
onBeforeUnmount(() => { window.clearTimeout(searchTimer); searchGeneration++; picksGeneration++; shopGeneration++ })
const shops = ref([]), addresses = ref([]), selectedAddress = ref(''), error = ref(''), start = ref(0), loading = ref(false), hasMore = ref(false)
let shopGeneration = 0
const activeAddress = computed(() => addresses.value.find(address => address.name === selectedAddress.value))
async function load(delta = 0) {
  const current = ++shopGeneration
  start.value = Math.max(0, start.value + delta); loading.value = true; error.value = ''
  try {
    const result = await call('storefront.discover', { address: selectedAddress.value, search: productSearch.value.trim(), start: start.value })
    if (current === shopGeneration) { shops.value = result.shops; hasMore.value = result.has_more }
  } catch(e) { if (current === shopGeneration) error.value = e.message }
  finally { if (current === shopGeneration) loading.value = false }
}
async function loadAddresses() {
  picksGeneration++; customerPicks.value = null
  if (session.value.user === 'Guest' || !session.value.roles.includes('LC Customer')) { addresses.value = []; selectedAddress.value = ''; await load(); return }
  try {
    addresses.value = await call('customers.addresses')
    const key = `lc-selected-address:${session.value.user}`
    let remembered = ''
    try { remembered = sessionStorage.getItem(key) || '' } catch { /* Leave the address unselected. */ }
    selectedAddress.value = addresses.value.some(address => address.name === remembered) ? remembered : ''
  } catch { addresses.value = []; selectedAddress.value = '' }
  await load()
  await loadCustomerPicks()
}
watch(activeAddress, scheduleProductSearch)
watch(() => session.value.user, loadAddresses)
onMounted(() => { loadAddresses(); window.addEventListener('lc-address-change', loadAddresses) })
onBeforeUnmount(() => window.removeEventListener('lc-address-change', loadAddresses))
function clearCategory() {
  activeCategory.value = ''; scheduleProductSearch()
  const query = { ...route.query }; delete query.category
  router.replace({ path: route.path, query })
}
watch(() => route.query.category, group => {
  if (typeof group === 'string' && group) chooseCategory(group)
  else if (activeCategory.value) { activeCategory.value = ''; scheduleProductSearch() }
}, { immediate: true })
const browse = ref(null)
watch(shopsOnly, async () => {
  searchGeneration++; productResults.value = []; productSearch.value = ''; activeCategory.value = ''
  start.value = 0; await load()
  await nextTick()
  window.scrollTo({ top: 0, behavior: 'auto' })
})
</script>

<template>
  <div class="store-page home-discovery-page">
    <section v-if="!shopsOnly" class="home-shortcuts" aria-label="Shopping shortcuts">
      <div class="home-shortcuts-intro"><h2>{{ session.user !== 'Guest' && session.roles.includes('LC Customer') ? 'Welcome back' : 'Explore your neighbourhood' }}</h2></div>
      <nav class="home-shortcut-links" aria-label="Quick links">
        <RouterLink v-if="session.user !== 'Guest' && session.roles.includes('LC Customer')" to="/orders" class="home-shortcut home-shortcut-orders"><span class="home-shortcut-icon"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 7h14l1 13H4L5 7Z" /><path d="M8 8V6a4 4 0 0 1 8 0v2m-8 6 3 3 5-5" /></svg></span><span class="home-shortcut-copy"><strong>My orders</strong></span><span class="home-shortcut-arrow" aria-hidden="true">↗</span></RouterLink>
        <RouterLink to="/store/map" class="home-shortcut home-shortcut-map"><span class="home-shortcut-icon"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m3 5 6-2 6 2 6-2v16l-6 2-6-2-6 2V5Zm6-2v16m6-14v16" /></svg></span><span class="home-shortcut-copy"><strong>Explore map</strong></span><span class="home-shortcut-arrow" aria-hidden="true">↗</span></RouterLink>
      </nav>
    </section>
    <ActiveOrderShortcut v-if="!shopsOnly" />
    <p v-if="!shopsOnly && session.user === 'Guest'" class="home-welcome-note">Find fresh favourites and everyday essentials from shops near you.</p>
    <section ref="productBrowse" class="home-product-search" aria-label="Search shops and products">
      <label class="product-search"><span aria-hidden="true">⌕</span><input v-model="productSearch" type="search" maxlength="140" :placeholder="shopsOnly ? 'Search shops…' : 'Search shops, Kingfish, groceries…'" :aria-label="shopsOnly ? 'Search shops' : 'Search shops and products'"><button v-if="productSearch" type="button" aria-label="Clear product search" @click="productSearch = ''">×</button></label>
      <div v-if="activeCategory" class="selected-category"><strong>{{ categoryLabel }}</strong><button type="button" @click="clearCategory">Clear category ×</button></div>
      <template v-if="!shopsOnly && (productSearch.trim().length >= 2 || activeCategory)"><div class="section-title"><h2>{{ categoryLabel }}</h2><small>{{ activeAddress ? 'Sorted by delivery availability and distance' : 'Choose an address to check nearby delivery' }}</small></div><p v-if="productLoading" role="status">Finding products…</p><p v-if="productError" role="alert" class="lc-notice">{{ productError }}</p><p v-if="!productLoading && !productError && !productResults.length" class="lc-empty">No matching products. Try another name.</p><div class="home-search-grid"><div v-for="item in productResults" :key="`${item.shop}:${item.item}`" class="home-search-product-wrap"><FavouriteButton :item="item.item" :shop="item.shop" /><RouterLink class="lc-card home-search-product" :to="{ name: 'customer-shop', params: { shop: item.shop }, query: { item: item.item } }"><div class="product-art"><img v-if="item.image" :src="item.image" :alt="item.item_name" loading="lazy" @error="item.image = ''"><span v-else aria-hidden="true">{{ item.item_name.slice(0, 1).toUpperCase() }}</span></div><small class="search-shop-name">{{ item.shop_name }}{{ item.distance_km != null ? ` · ${Number(item.distance_km).toFixed(1)} km` : '' }}</small><h3>{{ item.item_name }}</h3><strong>{{ displayPrice(item).from ? 'From ' : '' }}{{ money(displayPrice(item).rate, item.currency) }} <small>{{ displayPrice(item).from ? 'Choose option' : ` / ${item.uom}` }}</small></strong><p class="search-stock">{{ item.available > 0 ? 'In stock' : 'Sold out' }}</p><small class="serviceability-line" :class="{ available: item.serviceable }">{{ item.serviceability_message }}</small><span class="lc-card-link">View item →</span></RouterLink><StockAlertButton v-if="item.available <= 0" :shop="item.shop" :item="item.item" /></div></div><div v-if="productResults.length" class="lc-pagination"><button :disabled="!productStart || productLoading" @click="findProducts(-20)">Previous</button><button :disabled="!productMore || productLoading" @click="findProducts(20)">Next</button></div></template>
    </section>
    <PromotionSlider v-if="!shopsOnly" />
    <section v-if="!shopsOnly && categoryMenu.categories.length" class="compact-category-menu" aria-label="Shop by category">
      <header><h2>Shop by category</h2><RouterLink to="/categories">View all <span aria-hidden="true">›</span></RouterLink></header>
      <div class="compact-category-row"><button v-for="category in categoryMenu.categories" :key="category.item_group" type="button" class="category-tile" :class="{ selected: activeCategory === category.item_group }" @click="chooseCategory(category.item_group)"><span class="category-tile-art"><img v-if="category.image" :src="category.image" alt="" loading="lazy" @error="category.image = ''"><span v-else aria-hidden="true">{{ categoryIcon(category.item_group) }}</span></span><strong>{{ category.label }}</strong></button></div>
    </section>
    <section id="home-shops" ref="browse" class="browse-section">
      <div class="section-title"><div><span class="eyebrow">YOUR NEIGHBOURHOOD</span><h2>{{ productSearch.trim() ? 'Matching shops' : 'Explore local shops' }}</h2></div><nav class="home-view-switch" aria-label="Shop view"><span aria-current="page">▦ List</span><RouterLink to="/store/map">⌖ Map</RouterLink></nav></div>
      <div>
        <p v-if="activeAddress" class="nearby-summary">Showing shops near <strong>{{ activeAddress.address_label }}</strong>, sorted by delivery availability and distance.</p>
        <p v-if="error" role="alert" class="lc-notice">{{ error }}</p><p v-if="loading" role="status">Loading shops…</p>
        <div class="home-shop-grid"><HomeShopCard v-for="shop in shops" :key="shop.name" :shop="shop" :has-address="!!activeAddress" /></div>
        <p v-if="!loading && !shops.length" class="lc-empty">{{ productSearch.trim() ? 'No shops match this search. Try another name.' : 'No active shops are available yet.' }}</p>
        <div class="lc-pagination"><button :disabled="!start || loading" @click="load(-20)">Previous</button><button :disabled="!hasMore || loading" @click="load(20)">Next</button><button :disabled="loading" @click="load()">Refresh</button></div>
      </div>
    </section>
    <section v-for="section in (shopsOnly ? [] : displayedSections)" :key="section.name" class="featured-section"><div class="section-title"><div><span class="eyebrow">FROM YOUR LOCAL SHOPS</span><h2>{{ section.title }}</h2></div><div class="featured-arrows"><button aria-label="Previous featured products" @click="featuredRows[section.name]?.scrollBy({ left: -300, behavior: 'smooth' })">←</button><button aria-label="Next featured products" @click="featuredRows[section.name]?.scrollBy({ left: 300, behavior: 'smooth' })">→</button></div></div><div :ref="element => { if (element) featuredRows[section.name] = element; else delete featuredRows[section.name] }" class="featured-product-row"><div v-for="item in section.items" :key="item.item" class="home-search-product-wrap"><FavouriteButton :item="item.item" :shop="item.shop" /><RouterLink class="lc-card home-search-product" :to="{ name: 'customer-shop', params: { shop: item.shop }, query: { item: item.item } }"><div class="product-art"><img v-if="item.image" :src="item.image" :alt="item.item_name" loading="lazy" @error="item.image = ''"><span v-else aria-hidden="true">{{ item.item_name.slice(0, 1) }}</span></div><small class="search-shop-name">{{ item.shop_name }}</small><h3>{{ item.item_name }}</h3><strong>{{ displayPrice(item).from ? 'From ' : '' }}{{ money(displayPrice(item).rate, item.currency) }}<small> {{ displayPrice(item).from ? 'Choose option' : ` / ${item.uom}` }}</small></strong><small>{{ item.available > 0 ? 'In stock' : 'Sold out' }}</small><span class="lc-card-link">View item →</span></RouterLink><StockAlertButton v-if="item.available <= 0" :shop="item.shop" :item="item.item" /></div></div></section>
    <div v-if="!shopsOnly" class="values"><div><strong>Local at heart</strong><p>Your neighbourhood businesses, together.</p></div><div><strong>Everyday made easier</strong><p>One place for the things you need.</p></div><div><strong>More choice, closer by</strong><p>From fresh produce to familiar favourites.</p></div></div>
  </div>
</template>
