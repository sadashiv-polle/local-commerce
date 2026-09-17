<script setup>
import { inject, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { call } from './api.js'
import { readCart, writeCart, changeQuantity } from './cart.js'
import AuthChoices from './AuthChoices.vue'
import { setFavourite } from './favourites-state.js'
const session = inject('session'), items = ref([]), loading = ref(false), busy = ref(false), error = ref(''), message = ref('')
const router = useRouter()
function money(item) { return item.rate == null ? 'Unavailable' : new Intl.NumberFormat(undefined, { style: 'currency', currency: item.currency }).format(item.rate) }
async function load() { loading.value = true; error.value = ''; try { items.value = await call('favourites.list_items') } catch (e) { error.value = e.message } finally { loading.value = false } }
async function remove(item) { busy.value = true; try { await call('favourites.toggle', { shop: item.shop, item: item.item, saved: 0 }, true); setFavourite(item.item, false); items.value = items.value.filter(row => row.item !== item.item) } catch (e) { error.value = e.message } finally { busy.value = false } }
async function add(item) {
  busy.value = true; error.value = ''; message.value = ''
  try {
    if (sessionStorage.getItem(`lc-delivery:${session.value.user}:${item.shop}`)) throw new Error('Resolve your unconfirmed order request in this shop before changing its cart.')
    const current = await call('orders.product', { shop: item.shop, item: item.item })
    if (current.selling_options?.length) { await router.push({ name: 'customer-shop', params: { shop: item.shop }, query: { item: item.item } }); return }
    const cart = changeQuantity(readCart(localStorage, item.shop), current, 1)
    if (Object.keys(cart).length > 30) throw new Error('Your cart can contain up to 30 different items.')
    writeCart(localStorage, item.shop, cart)
    message.value = `${current.item_name} added to your ${item.shop_name} cart.`
    Object.assign(item, current)
  } catch (e) { error.value = e.message } finally { busy.value = false }
}
onMounted(() => { if (session.value.user !== 'Guest') load() })
</script>
<template>
  <div class="store-page favourites-page"><AuthChoices v-if="session.user === 'Guest'" /><template v-else><div class="section-title"><div><span class="eyebrow">SAVED FOR LATER</span><h1>Your favourites</h1><p class="muted">Your everyday favourites, with current prices and stock.</p></div><button :disabled="loading || busy" @click="load">Refresh</button></div><RouterLink to="/store">← Browse shops</RouterLink><p v-if="loading" role="status">Loading favourites…</p><p v-if="error" class="lc-notice" role="alert">{{ error }}</p><p v-if="message" class="success-note" role="status">{{ message }}</p><p v-if="!loading && !error && !items.length" class="lc-empty">Tap the heart on a product to save it here.</p><div class="home-search-grid"><article v-for="item in items" :key="item.item" class="lc-card home-search-product"><RouterLink v-if="!item.unavailable" :to="{ name: 'customer-shop', params: { shop: item.shop }, query: { item: item.item } }" class="product-art"><img v-if="item.image" :src="item.image" :alt="item.item_name" loading="lazy" @error="item.image = ''"><span v-else aria-hidden="true">{{ item.item_name.slice(0, 1) }}</span></RouterLink><small class="search-shop-name">{{ item.shop_name }}</small><h3>{{ item.item_name }}</h3><strong>{{ money(item) }}</strong><small>{{ item.unavailable ? 'No longer available' : item.available > 0 ? `${item.available} ${item.uom} available` : 'Sold out' }}</small><div class="favourite-actions"><button class="add-item-button" :disabled="busy || item.unavailable || item.available <= 0 || item.rate == null" @click="add(item)">ADD +</button><button :disabled="busy" @click="remove(item)">Remove</button></div></article></div></template></div>
</template>
