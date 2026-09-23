<script setup>
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { computed, inject, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { call } from './api.js'
const session = inject('session')
const container = ref(null), shops = ref([]), selected = ref(''), busy = ref(false), error = ref(''), more = ref(false), locating = ref(false)
const current = computed(() => shops.value.find(shop => shop.name === selected.value))
const detail = ref(null), filter = ref('')
const matches = computed(() => shops.value.filter(shop => `${shop.shop_name} ${shop.city || ''}`.toLowerCase().includes(filter.value.toLowerCase())))
const attribution = ref({ attribution: '© OpenStreetMap contributors', attribution_url: 'https://www.openstreetmap.org/copyright' })
let map, tiles, layer, timer, generation = 0, disposed = false
async function selectShop(shop) { selected.value = shop.name; await nextTick(); detail.value?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }) }
function paint() {
  if (!layer) return
  layer.clearLayers()
  for (const shop of matches.value) {
    const marker = L.marker([shop.location.latitude, shop.location.longitude], {
      icon: L.divIcon({ className: 'discovery-shop-marker', html: '<svg aria-hidden="true" viewBox="0 0 24 24" width="25" height="25" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 10v10h16V10M3 10l2-6h14l2 6M3 10h18M8 20v-6h5v6M8 4v6m8-6v6"/></svg>', iconSize: [42, 42], iconAnchor: [21, 42] }),
      title: shop.shop_name, alt: shop.shop_name, keyboard: true,
    }).addTo(layer)
    const label = document.createElement('span')
    label.textContent = shop.shop_name
    marker.bindTooltip(label, { permanent: true, direction: 'top', offset: [0, -42], className: 'discovery-shop-label' })
    marker.on('click', () => selectShop(shop))
  }
}
async function loadArea() {
  if (!map) return
  const request = ++generation, bounds = map.getBounds()
  busy.value = true; error.value = ''
  try {
    const result = await call('orders.map_shops', { south: Math.max(-90, bounds.getSouth()), north: Math.min(90, bounds.getNorth()), west: Math.max(-180, bounds.getWest()), east: Math.min(180, bounds.getEast()) })
    if (disposed || request !== generation) return
    shops.value = result.shops; more.value = result.has_more
    if (!shops.value.some(shop => shop.name === selected.value)) selected.value = ''
    attribution.value = result.map
    if (result.map.tile_url) tiles.setUrl(result.map.tile_url)
    paint()
  } catch (e) { if (request === generation && !disposed) error.value = e.message }
  finally { if (request === generation && !disposed) busy.value = false }
}
function moved() { clearTimeout(timer); generation++; timer = setTimeout(loadArea, 350) }
function useLocation() {
  if (!navigator.geolocation) { error.value = 'Location is unavailable. Move the map to your area.'; return }
  locating.value = true
  navigator.geolocation.getCurrentPosition(position => {
    if (disposed) return
    locating.value = false; map.setView([position.coords.latitude, position.coords.longitude], 13)
  }, () => { if (!disposed) { locating.value = false; error.value = 'Allow location access, or move the map to your area.' } }, { timeout: 12000, maximumAge: 60000 })
}
onMounted(async () => {
  map = L.map(container.value, { attributionControl: false, worldCopyJump: false, minZoom: 3, maxBounds: [[-85, -180], [85, 180]] }).setView([15.49, 73.83], 11)
  tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, noWrap: true }).addTo(map)
  layer = L.layerGroup().addTo(map)
  map.on('moveend', moved)
  loadArea()
  // Only use an address the customer explicitly selected in this login session.
  try {
    const name = sessionStorage.getItem(`lc-selected-address:${session.value.user}`)
    if (name && session.value.user !== 'Guest') {
      const addresses = await call('customers.addresses')
      const address = addresses.find(row => row.name === name)
      if (!disposed && address?.latitude != null && address?.longitude != null && (Number(address.latitude) || Number(address.longitude))) map.setView([address.latitude, address.longitude], 13)
    }
  } catch { /* The map remains browsable without a saved location. */ }
})
onBeforeUnmount(() => { disposed = true; generation++; clearTimeout(timer); map?.remove(); map = null })
</script>
<template>
  <section class="store-page shop-map-page">
    <header class="shop-map-heading"><div><RouterLink to="/store">← Store home</RouterLink><h1>Explore local shops</h1><p>Move the map to explore an area. Tap a shop to see its details.</p></div><button type="button" :disabled="locating" @click="useLocation">{{ locating ? 'Finding you…' : 'Use my location' }}</button></header>
    <div class="shop-discovery-layout">
      <div class="shop-discovery-map"><div ref="container" class="shop-discovery-canvas" aria-label="Map of shops in this area"></div><footer><a :href="attribution.attribution_url" target="_blank" rel="noopener">{{ attribution.attribution }}</a><span role="status">{{ busy ? 'Finding shops…' : `${shops.length} shops in this area` }}</span></footer></div>
      <aside class="shop-discovery-panel">
        <article v-if="current" ref="detail" class="shop-map-detail"><span class="eyebrow">YOUR LOCAL SHOP</span><h2>{{ current.shop_name }}</h2><span class="status-pill">{{ current.availability.label }}</span><p>{{ current.description || 'Explore products from this local shop.' }}</p><p>{{ current.address_line1 }}<br>{{ current.city }}</p><small>{{ current.availability.message }}. Delivery availability is checked for your address at checkout.</small><RouterLink class="lc-primary" :to="{ name: 'customer-shop', params: { shop: current.name } }">Open shop &amp; items →</RouterLink></article>
        <p v-if="error" class="lc-notice" role="alert">{{ error }} <button @click="loadArea">Retry</button></p>
        <label class="shop-map-search">Find a shop in this area<input v-model="filter" type="search" placeholder="Shop name or city" @input="paint"></label>
        <p v-if="more">Many shops here. Zoom in to see all shops in a smaller area.</p>
        <p v-if="!busy && !error && !matches.length" class="lc-empty">No matching shops here. Move or zoom out on the map to explore another area.</p>
        <div class="shop-map-results"><button v-for="shop in matches" :key="shop.name" :class="{ selected: selected === shop.name }" @click="selectShop(shop)"><strong>{{ shop.shop_name }}</strong><small>{{ shop.city }} · {{ shop.availability.label }}</small><span>View details →</span></button></div>
      </aside>
    </div>
  </section>
</template>
