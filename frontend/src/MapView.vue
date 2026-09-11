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
  shop: ['<svg viewBox="0 0 24 24"><path d="M4 10v9h16v-9M3 10l2-5h14l2 5M8 19v-5h4v5M3 10c0 1.4 1.1 2.5 2.5 2.5S8 11.4 8 10c0 1.4 1.1 2.5 2.5 2.5S13 11.4 13 10c0 1.4 1.1 2.5 2.5 2.5S18 11.4 18 10c0 1.4 1.1 2.5 2.5 2.5"/></svg>', 'map-marker-shop'],
  customer: ['<svg viewBox="0 0 24 24"><path d="m4 11 8-7 8 7v9h-6v-6h-4v6H4z"/></svg>', 'map-marker-customer'],
  rider: ['<svg viewBox="0 0 24 24"><path d="m5 18 3.5-12L19 3l-3 10.5-4.5-2.5z"/></svg>', 'map-marker-rider'],
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
    const selected = props.editable && (point.kind === 'customer' || props.points.length === 1)
    L.marker([latitude, longitude], {
      icon: L.divIcon({
        className: `map-marker ${className}${selected ? ' map-marker-selected' : ''}`,
        html: `<span class="map-pin-pulse" aria-hidden="true"></span><span class="map-pin-body" aria-hidden="true">${symbol}</span>`,
        iconSize: [50, 58],
        iconAnchor: [25, 55],
      }),
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
