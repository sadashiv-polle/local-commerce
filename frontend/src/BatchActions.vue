<script setup>
import { ref, watch } from 'vue'
import { call } from './api.js'
const props = defineProps({ slotName: { type: String, required: true } })
const emit = defineEmits(['changed'])
const state = ref(null), error = ref(''), busy = ref(false), confirmation = ref(null), message = ref('')
const labels = { Preparing: 'Start preparing batch', Ready: 'Mark batch ready', 'Picked Up': 'Confirm batch pickup', 'Out for Delivery': 'Start batch delivery' }
async function load() { error.value = ''; try { state.value = await call('scheduled.batch_actions', { slot: props.slotName }) } catch(e) { error.value = e.message } }
async function confirm() {
  busy.value = true; error.value = ''; message.value = ''
  try { const result = await call('scheduled.advance_batch', { slot: props.slotName, target: confirmation.value.target }, true); confirmation.value = null; message.value = `${result.changed} orders updated to ${result.target}.`; await load(); emit('changed') } catch(e) { error.value = e.message } finally { busy.value = false }
}
watch(() => props.slotName, () => { state.value = null; confirmation.value = null; load() }, { immediate: true })
</script>
<template>
  <section class="scheduled-slot" aria-label="Batch progress">
    <div class="workspace-heading"><h4>Batch progress</h4><button type="button" :disabled="busy" @click="load">Refresh status</button></div>
    <p v-if="error" role="alert">{{ error }}</p><p v-if="message" role="status">{{ message }}</p>
    <template v-if="state"><p><span v-for="(count, status) in state.counts" :key="status" class="status-pill">{{ status }}: {{ count }} </span></p><p>Accept requests separately. Advance the batch together; each customer’s delivery still needs their OTP and cash confirmation.</p><p v-if="!state.actions.length">No batch action available. Check pending requests, order preparation and delivery assignment.</p><div v-if="!confirmation" class="button-row"><button v-for="action in state.actions" :key="action.target" type="button" class="lc-primary" :disabled="busy" @click="confirmation = action">{{ labels[action.target] }} · {{ action.count }} orders</button></div><div v-else role="group" aria-label="Confirm batch update"><h4>{{ labels[confirmation.target] }}?</h4><p>Apply this step to all {{ confirmation.count }} eligible orders. If any order fails validation, none of these updates will be saved.</p><div class="button-row"><button type="button" :disabled="busy" @click="confirmation = null">Go back</button><button type="button" class="lc-primary" :disabled="busy" @click="confirm">{{ busy ? 'Updating batch…' : 'Confirm for batch' }}</button></div></div></template>
  </section>
</template>
