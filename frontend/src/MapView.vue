<script setup>
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { call } from './api.js'

const props = defineProps({
  config: { type: Object, default: () => ({}) },
  points: { type: Array, default: () => [] },
  route: { type: Array, default: () => [] },
  editable: Boolean,
  height: { type: String, default: '260px' },
})
const emit = defineEmits(['pick'])
const container = ref(null)
const expanded = ref(false)
const searchQuery = ref(''), searchResults = ref([]), searchError = ref(''), searching = ref(false)
let map
let layer
let routeLayer
const markers = new Map()

const markerStyles = {
  shop: ['<svg viewBox="0 0 24 24"><path d="M4 10v9h16v-9M3 10l2-5h14l2 5M8 19v-5h4v5M3 10c0 1.4 1.1 2.5 2.5 2.5S8 11.4 8 10c0 1.4 1.1 2.5 2.5 2.5S13 11.4 13 10c0 1.4 1.1 2.5 2.5 2.5S18 11.4 18 10c0 1.4 1.1 2.5 2.5 2.5"/></svg>', 'map-marker-shop'],
  customer: ['<svg viewBox="0 0 24 24"><path d="m4 11 8-7 8 7v9h-6v-6h-4v6H4z"/></svg>', 'map-marker-customer'],
  rider: ['<span class="map-bike-emoji">🛵</span>', 'map-marker-rider'],
}

function renderPoints() {
  if (!map || !layer || !routeLayer) return
  routeLayer.clearLayers()
  const bounds = []
  const route = props.route
    .map(point => [Number(point?.latitude), Number(point?.longitude)])
    .filter(point => point.every(Number.isFinite))
  if (route.length > 1) {
    L.polyline(route, { color: '#286dcc', weight: 6, opacity: .86, lineCap: 'round', lineJoin: 'round' }).addTo(routeLayer)
    L.polyline(route, { color: '#fff', weight: 2, opacity: .82, dashArray: '2 10', lineCap: 'round' }).addTo(routeLayer)
    bounds.push(...route)
  }
  const activeMarkers = new Set()
  for (const [index, point] of props.points.entries()) {
    const latitude = Number(point?.latitude)
    const longitude = Number(point?.longitude)
    if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) continue
    const key = `${point.kind || 'customer'}:${index}`
    activeMarkers.add(key)
    const [symbol, className] = markerStyles[point.kind] || markerStyles.customer
    const selected = props.editable && (point.kind === 'customer' || props.points.length === 1)
    let marker = markers.get(key)
    if (!marker) {
      marker = L.marker([latitude, longitude], {
        icon: L.divIcon({
          className: `map-marker ${className}${selected ? ' map-marker-selected' : ''}`,
          html: `<span class="map-pin-pulse" aria-hidden="true"></span><span class="map-pin-body" aria-hidden="true">${symbol}</span>`,
          iconSize: [50, 58],
          iconAnchor: [25, 55],
        }),
        keyboard: false,
        zIndexOffset: point.kind === 'rider' ? 1000 : 0,
        title: String(point.label || 'Map location').slice(0, 100),
      }).addTo(layer)
      markers.set(key, marker)
    } else marker.setLatLng([latitude, longitude])
    bounds.push([latitude, longitude])
  }
  for (const [key, marker] of markers) {
    if (!activeMarkers.has(key)) { layer.removeLayer(marker); markers.delete(key) }
  }
  if (bounds.length === 1) map.setView(bounds[0], 15)
  else if (bounds.length > 1) map.fitBounds(bounds, { padding: [38, 38], maxZoom: 16 })
  else map.setView([15.49, 73.83], 11)
}

async function toggleExpanded() {
  expanded.value = !expanded.value
  await nextTick()
  map?.invalidateSize()
  renderPoints()
}

function closeExpanded(event) {
  if (event.key === 'Escape' && expanded.value) toggleExpanded()
}

async function searchPlaces() {
  searchError.value = ''; searchResults.value = []
  if (searchQuery.value.trim().length < 3) { searchError.value = 'Enter at least 3 characters.'; return }
  searching.value = true
  try {
    searchResults.value = await call('locations.search', { query: searchQuery.value.trim() })
    if (!searchResults.value.length) searchError.value = 'No matching places found.'
  } catch (error) { searchError.value = error.message }
  finally { searching.value = false }
}

function choosePlace(place) {
  searchQuery.value = place.label
  searchResults.value = []; searchError.value = ''
  map?.setView([place.latitude, place.longitude], 17)
  emit('pick', place)
}

onMounted(async () => {
  await nextTick()
  map = L.map(container.value, { zoomControl: true, attributionControl: false })
  L.tileLayer(props.config?.tile_url || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(map)
  routeLayer = L.layerGroup().addTo(map)
  layer = L.layerGroup().addTo(map)
  if (props.editable) map.on('click', event => emit('pick', { latitude: Number(event.latlng.lat.toFixed(6)), longitude: Number(event.latlng.lng.toFixed(6)) }))
  renderPoints()
  setTimeout(() => map?.invalidateSize(), 0)
  window.addEventListener('keydown', closeExpanded)
})

watch([() => props.points, () => props.route], renderPoints, { deep: true })
onBeforeUnmount(() => { window.removeEventListener('keydown', closeExpanded); map?.remove(); map = null; layer = null; routeLayer = null; markers.clear() })
</script>

<template>
  <div class="lc-map-shell" :class="{ 'lc-map-shell-expanded': expanded }">
    <div ref="container" class="lc-map" :style="{ height }" :aria-label="editable ? 'Choose a location on the map' : 'Delivery map'"></div>
    <div v-if="editable" class="map-place-search" role="search">
      <input v-model="searchQuery" type="search" maxlength="120" autocomplete="off" placeholder="Search area, street or landmark" aria-label="Search for a place" @keydown.enter.prevent="searchPlaces">
      <button type="button" :disabled="searching" aria-label="Search map" @click="searchPlaces">
        <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6" /><path d="m16 16 4 4" /></svg>
      </button>
      <div v-if="searchResults.length || searchError" class="map-search-results">
        <p v-if="searchError" role="status">{{ searchError }}</p>
        <button v-for="place in searchResults" :key="`${place.latitude}:${place.longitude}`" type="button" @click="choosePlace(place)">
          <span aria-hidden="true">⌖</span><strong>{{ place.label }}</strong>
        </button>
      </div>
    </div>
    <button class="map-expand-button" type="button" :aria-label="expanded ? 'Minimize map' : 'Expand map'" :title="expanded ? 'Minimize map' : 'Expand map'" @click="toggleExpanded">
      <svg v-if="expanded" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5" /></svg>
      <svg v-else viewBox="0 0 24 24" aria-hidden="true"><path d="M9 4H4v5M15 4h5v5M9 20H4v-5M15 20h5v-5" /></svg>
    </button>
    <footer><span v-if="editable">Tap the map to move the pin.</span><small><a :href="config?.attribution_url || 'https://www.openstreetmap.org/copyright'" target="_blank" rel="noopener">{{ config?.attribution || '© OpenStreetMap contributors' }}</a></small></footer>
  </div>
</template>
