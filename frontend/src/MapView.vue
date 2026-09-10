<script setup>
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  config: { type: Object, default: () => ({}) },
  points: { type: Array, default: () => [] },
  editable: Boolean,
  height: { type: String, default: '260px' },
})
const emit = defineEmits(['pick'])
const container = ref(null)
let map
let layer

const markerStyles = {
  shop: ['S', 'map-marker-shop'],
  customer: ['●', 'map-marker-customer'],
  rider: ['↟', 'map-marker-rider'],
}

function renderPoints() {
  if (!map || !layer) return
  layer.clearLayers()
  const bounds = []
  for (const point of props.points) {
    const latitude = Number(point?.latitude)
    const longitude = Number(point?.longitude)
    if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) continue
    const [symbol, className] = markerStyles[point.kind] || markerStyles.customer
    L.marker([latitude, longitude], {
      icon: L.divIcon({ className: `map-marker ${className}`, html: `<span aria-hidden="true">${symbol}</span>`, iconSize: [38, 38], iconAnchor: [19, 38] }),
      keyboard: false,
      title: String(point.label || 'Map location').slice(0, 100),
    }).addTo(layer)
    bounds.push([latitude, longitude])
  }
  if (bounds.length === 1) map.setView(bounds[0], 15)
  else if (bounds.length > 1) map.fitBounds(bounds, { padding: [38, 38], maxZoom: 16 })
  else map.setView([15.49, 73.83], 11)
}

onMounted(async () => {
  await nextTick()
  map = L.map(container.value, { zoomControl: true, attributionControl: false })
  L.tileLayer(props.config?.tile_url || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(map)
  layer = L.layerGroup().addTo(map)
  if (props.editable) map.on('click', event => emit('pick', { latitude: Number(event.latlng.lat.toFixed(6)), longitude: Number(event.latlng.lng.toFixed(6)) }))
  renderPoints()
  setTimeout(() => map?.invalidateSize(), 0)
})

watch(() => props.points, renderPoints, { deep: true })
onBeforeUnmount(() => { map?.remove(); map = null; layer = null })
</script>

<template>
  <div class="lc-map-shell">
    <div ref="container" class="lc-map" :style="{ height }" :aria-label="editable ? 'Choose a location on the map' : 'Delivery map'"></div>
    <footer><span v-if="editable">Tap the map to move the pin.</span><small><a :href="config?.attribution_url || 'https://www.openstreetmap.org/copyright'" target="_blank" rel="noopener">{{ config?.attribution || '© OpenStreetMap contributors' }}</a></small></footer>
  </div>
</template>
