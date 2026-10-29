<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import MapView from './MapView.vue'
import { call } from './api.js'
import { metres, segmentDistance, createRerouteGuard, travelHeading } from './journey-navigation.js'
const props = defineProps({ order: { type: Object, required: true } })
const emit = defineEmits(['close'])
const location = ref(null), route = ref(null), message = ref('Finding your precise location…'), step = ref(0), distance = ref(0)
const now = ref(Date.now()), lastRoute = ref(0), pending = ref(false), routeError = ref(''), trail = ref([])
const heading = ref(null)
let headingFix
let watchId, timer, latest, wake, closed = false, lastTrailTimestamp = null
let shouldReroute = createRerouteGuard()
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
  if (pending.value || !location.value || closed || !latest || Date.now() - latest.timestamp > 15000 || latest.coords.accuracy > 100) return
  pending.value = true; lastRoute.value = Date.now(); routeError.value = ''
  try {
    const result = await call('orders.journey_route', { order: props.order.name, ...location.value })
    if (!closed) { route.value = result; step.value = 0; shouldReroute = createRerouteGuard(); message.value = '' }
  } catch (error) { if (!closed) routeError.value = error.message }
  finally { pending.value = false }
}
function tick() {
  now.value = Date.now()
  if (!latest || closed) return
  if (Date.now() - latest.timestamp > 15000) { message.value = 'GPS signal lost. Waiting for a fresh location…'; return }
  if (latest.coords.accuracy > 100) { message.value = 'Waiting for precise GPS. Move outdoors if possible.'; return }
  heading.value = travelHeading(headingFix, latest, heading.value)
  if (!headingFix || metres(headingFix.coords, latest.coords) >= Math.max(8, latest.coords.accuracy, headingFix.coords.accuracy)) headingFix = latest
  location.value = { latitude: latest.coords.latitude, longitude: latest.coords.longitude }
  if (latest.timestamp !== lastTrailTimestamp) {
    lastTrailTimestamp = latest.timestamp
    const previous = trail.value.at(-1)
    if (!previous || metres(previous, location.value) >= 5) trail.value = [...trail.value.slice(-1999), location.value]
  }
  if (!route.value) { if (now.value - lastRoute.value >= 5000) getRoute(); return }
  message.value = pending.value ? 'Updating route…' : ''
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
  if (shouldReroute(latest, nearest, lastRoute.value, now.value)) getRoute()
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
    <p v-if="routeError" role="alert">{{ routeError }} Retrying automatically when needed.</p>
    <MapView navigation :heading="heading" :trail="trail" :config="order.map" :points="points" :route="route?.points || []" :follow="location" preserve-view hide-expand height="calc(100dvh - 240px)" />
    <footer><span>Green line: your travelled path. Blue line: directions. GPS view refreshes every second. Keep this screen open; follow road signs.</span><small v-if="route">{{ route.attribution }}</small><button type="button" :disabled="pending || !location || now - lastRoute < 5000" @click="getRoute">Refresh route</button></footer>
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
