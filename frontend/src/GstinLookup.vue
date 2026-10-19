<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { call } from './api.js'
const props = defineProps({ number: { type: String, default: '' } })
const emit = defineEmits(['apply'])
const result = ref(null), error = ref(''), busy = ref(false)
const number = computed(() => props.number.trim().toUpperCase())
let timer, generation = 0
async function fetchDetails() {
  const current = ++generation, requested = number.value
  result.value = null; error.value = ''; busy.value = true
  try {
    const value = await call('gst.lookup_gstin', { number: requested }, true)
    if (current === generation && requested === number.value) result.value = value
  } catch (e) { if (current === generation) error.value = e.message }
  finally { if (current === generation) busy.value = false }
}
watch(number, value => {
  clearTimeout(timer); generation++; result.value = null; error.value = ''; busy.value = false
  if (/^[0-9]{2}[A-Z0-9]{13}$/.test(value)) timer = setTimeout(fetchDetails, 700)
})
onBeforeUnmount(() => { clearTimeout(timer); generation++ })
function apply() {
  if (result.value?.gstin === number.value) emit('apply', result.value)
}
</script>
<template>
  <div class="gst-lookup">
    <p v-if="busy" role="status">Fetching GST registration details…</p>
    <p v-if="error" role="status">{{ error }}</p>
    <template v-if="result">
      <strong>{{ result.legal_name || 'Legal name unavailable' }}</strong>
      <p v-if="result.trade_name">Trade name: {{ result.trade_name }}</p>
      <p>Registration status: {{ result.status || 'Unknown' }} · {{ result.category }}</p>
      <p>{{ result.address || 'Address unavailable' }}</p>
      <p>Review before applying. This updates the form only; tax treatment, accounts and existing Company records stay unchanged.</p>
      <button type="button" :disabled="!result.legal_name || result.status.toLowerCase() !== 'active'" @click="apply">Use these details</button>
      <p v-if="result.status.toLowerCase() !== 'active'">This registration is not reported as active. Review its status before using it.</p>
    </template>
    <button v-if="error && number.length === 15" type="button" :disabled="busy" @click="fetchDetails">Retry GST lookup</button>
  </div>
</template>
<style scoped>
.gst-lookup:not(:empty) { padding: 12px; background: #f1f6ef; border-radius: 12px; margin: 8px 0; }
.gst-lookup p { line-height: 1.5; overflow-wrap: anywhere; }
</style>
