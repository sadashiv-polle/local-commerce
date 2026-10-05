<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
const props = defineProps({ location: { type: Object, required: true } })
const received = ref(Date.now()), now = ref(Date.now())
watch(() => props.location, () => { received.value = Date.now(); now.value = Date.now() })
const timer = window.setInterval(() => { now.value = Date.now() }, 10000)
onBeforeUnmount(() => window.clearInterval(timer))
const age = computed(() => Number.isFinite(Number(props.location.age_seconds)) ? Math.max(0, Number(props.location.age_seconds) + (now.value - received.value) / 1000) : null)
const label = computed(() => age.value == null ? 'Location update time unavailable' : age.value < 15 ? 'Location last updated just now' : age.value < 60 ? `Location last updated ${Math.floor(age.value)} seconds ago` : `Location last updated ${Math.floor(age.value / 60)} minutes ago`)
</script>
<template><p class="location-freshness" :class="{ stale: age == null || age >= 120 }">{{ label }}<span v-if="age == null || age >= 120"> · Updates delayed. The rider may have lost signal or paused location sharing.</span></p></template>
<style>
#lc-app .location-freshness { padding: 10px 12px; background: #edf6ef; border-radius: 10px; color: #176547; font-size: 13px; }
#lc-app .location-freshness.stale { background: #fff4df; color: #835a19; }
</style>
