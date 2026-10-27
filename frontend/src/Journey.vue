<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import MapView from './MapView.vue'
import { call } from './api.js'
import { metres, segmentDistance } from './journey-navigation.js'
const props = defineProps({ order: { type: Object, required: true } })
const emit = defineEmits(['close'])
const location = ref(null), route = ref(null), message = ref('Finding your precise location…'), step = ref(0), distance = ref(0)
let watchId, timer, latest, wake, pending = false, lastRoute = 0, closed = false
const target = computed(() => props.order.status === 'Ready' ? props.order.shop_location : props.order.destination_location)
const points = computed(() => [...(target.value ? [{ ...target.value, kind: 'customer', label: 'Destination' }] : []), ...(location.value ? [{ ...location.value, kind: 'rider', label: 'You' }] : [])])
const instruction = computed(() => {
  const next = route.value?.steps?.[step.value + 1]
  if (!next) return route.value ? 'Approaching destination' : 'Preparing directions…'
  if (next.type === 'arrive') return 'Arrive at destination'
  const action = next.type.includes('roundabout') || next.type === 'rotary' ? `At the roundabout, ${next.exit ? `take exit ${next.exit}` : 'follow the route'}` : `${next.type === 'turn' ? 'Turn' : next.type === 'fork' ? 'Keep' : 'Continue'} ${next.modifier || 'ahead'}`
  return `${action}${next.name ? ` onto ${next.name}` : ''}`
})
async function getRoute() {
  if (pending || !location.value || closed) return
  pending = true; lastRoute = Date.now()
  try {
    const result = await call('orders.journey_route', { order: props.order.name, ...location.value })
    if (!closed) { route.value = result; step.value = 0; message.value = '' }
  } catch (error) { if (!closed) message.value = error.message }
  finally { pending = false }
}
function tick() {
  if (!latest || closed) return
  if (Date.now() - latest.timestamp > 15000) { message.value = 'GPS signal lost. Waiting for a fresh location…'; return }
  if (latest.coords.accuracy > 100) { message.value = 'Waiting for precise GPS. Move outdoors if possible.'; return }
  location.value = { latitude: latest.coords.latitude, longitude: latest.coords.longitude }
  if (!route.value) { if (Date.now() - lastRoute > 30000) getRoute(); return }
  message.value = pending ? 'Updating route…' : ''
  const steps = route.value.steps || []
  // Search the current and following segment only, avoiding jumps at crossing roads.
  let nearest = Infinity, index = step.value
  for (let i = step.value; i < Math.min(steps.length, step.value + 2); i++) {
    const d = segmentDistance(location.value, steps[i].points)
    if (d < nearest) { nearest = d; index = i }
  }
  step.value = index
  const next = steps[index + 1]?.points?.[0] || target.value
  distance.value = next ? Math.round(metres(location.value, next)) : 0
  if (nearest > 60 && Date.now() - lastRoute > 30000) getRoute()
}
async function keepAwake() {
  if (closed || document.visibilityState !== 'visible' || wake) return
  try { const lock = await navigator.wakeLock?.request('screen'); if (closed) { await lock?.release(); return } wake = lock; lock?.addEventListener('release', () => { wake = null }) } catch { /* Device may decline; navigation still works while visible. */ }
}
function visible() { keepAwake(); tick() }
onMounted(() => {
  keepAwake()
  document.addEventListener('visibilitychange', visible)
  if (!navigator.geolocation || !window.isSecureContext) { message.value = 'Navigation needs HTTPS and location access.'; return }
  watchId = navigator.geolocation.watchPosition(position => { latest = position; tick() }, error => {
    message.value = error.code === 1 ? 'Allow precise location in your browser settings to navigate.' : 'Waiting for GPS signal…'
  }, { enableHighAccuracy: true, maximumAge: 0, timeout: 10000 })
  timer = window.setInterval(tick, 1000)
})
onBeforeUnmount(() => { closed = true; if (watchId != null) navigator.geolocation.clearWatch(watchId); clearInterval(timer); wake?.release(); document.removeEventListener('visibilitychange', visible) })
</script>
<template>
  <section class="journey" role="dialog" aria-modal="true" aria-label="Delivery navigation" @keydown.esc="emit('close')">
    <header><div><small>{{ order.status === 'Ready' ? 'JOURNEY TO SHOP' : 'JOURNEY TO CUSTOMER' }}</small><h2>{{ instruction }}</h2><strong v-if="route">{{ distance >= 1000 ? `${(distance / 1000).toFixed(1)} km` : `${distance} m` }} approximately to next direction</strong></div><button type="button" autofocus @click="emit('close')">End journey</button></header>
    <p v-if="message" role="status">{{ message }}</p>
    <MapView :config="order.map" :points="points" :route="route?.points || []" :follow="location" preserve-view hide-expand height="calc(100dvh - 240px)" />
    <footer><span>GPS view refreshes every second. Keep this screen open; follow road signs.</span><small v-if="route">{{ route.attribution }}</small><button type="button" :disabled="pending || !location || Date.now() - lastRoute < 30000" @click="getRoute">Refresh route</button></footer>
  </section>
</template>
<style scoped>
.journey { position: fixed; inset: 0; z-index: 1300; background: #fffef9; padding: 16px; overflow: auto; }
.journey header { display: flex; justify-content: space-between; gap: 12px; align-items: center; background: #176448; color: white; border-radius: 16px; padding: 18px; }
.journey h2 { color: white; font-size: clamp(20px, 4vw, 28px); margin: 8px 0; }
.journey button { padding: 12px; border-radius: 10px; border: 1px solid #cbd8d0; background: white; color: #174d39; cursor: pointer; }
.journey footer { display: flex; flex-wrap: wrap; gap: 12px; padding: 12px 0; align-items: center; }
.journey footer small { display: block; }
</style>
