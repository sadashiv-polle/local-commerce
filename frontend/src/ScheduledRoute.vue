<script setup>
import { computed, ref, watch } from 'vue'
import { call } from './api.js'
import BatchActions from './BatchActions.vue'
import MapView from './MapView.vue'
const props = defineProps({ slotName: { type: String, required: true }, manageable: Boolean, riderLocation: { type: Object, default: null } })
const emit = defineEmits(['open-order', 'changed', 'resume-tracking'])
const data = ref(null), error = ref(''), busy = ref(false)
const points = computed(() => data.value ? [{ ...data.value.origin, kind: 'shop', label: 'Pickup' }, ...data.value.stops.map((s, i) => ({ ...s.destination_location, kind: 'customer', label: `${i + 1}. ${s.recipient}` })), ...(props.riderLocation ? [{ ...props.riderLocation, kind: 'rider', label: 'Your current location' }] : [])] : [])
async function load() { busy.value = true; error.value = ''; data.value = null; try { data.value = await call('scheduled.route', { slot: props.slotName }) } catch(e) { error.value = e.message } finally { busy.value = false } }
function navigation(stop) { return `https://www.google.com/maps/dir/?api=1&destination=${stop.destination_location.latitude},${stop.destination_location.longitude}&travelmode=driving` }
watch(() => props.slotName, load, { immediate: true })
</script>
<template>
  <section class="scheduled-panel"><div class="workspace-heading"><h3>Scheduled delivery route</h3><button type="button" :disabled="busy" @click="load">{{ busy ? 'Loading…' : 'Refresh route' }}</button></div><BatchActions v-if="manageable" :slot-name="slotName" @changed="load(); emit('changed', $event)" /><button v-if="manageable" type="button" @click="emit('resume-tracking', slotName)">Show my location / resume batch tracking</button><p v-if="error" role="alert">{{ error }}</p><template v-if="data"><h4>{{ data.title }}</h4><p>{{ data.delivery_start }} – {{ data.delivery_end }}</p><p>Recommended order by road travel time. You can deliver any stop first. Use each order’s delivery controls below to confirm pickup, delivery and payment.</p><MapView v-if="data.stops.length" :points="points" :route="data.points" :config="data.map" height="320px" /><p v-if="data.attribution">{{ data.distance_km }} km · about {{ data.duration_minutes }} minutes driving · {{ data.attribution }}</p><p v-if="!data.stops.length">All stops are complete.</p><article v-for="(stop, i) in data.stops" :key="stop.name" class="scheduled-slot"><strong>{{ i + 1 }}. {{ stop.recipient }}</strong><p>{{ stop.address.line1 }} · {{ stop.address.city }} · {{ stop.status }}</p><p>Order #{{ stop.name.slice(0, 8) }}</p><a :href="navigation(stop)" target="_blank" rel="noopener">Navigate to this stop ↗</a><button v-if="manageable" type="button" @click="emit('open-order', stop.name)">Open delivery controls</button></article></template></section>
</template>
