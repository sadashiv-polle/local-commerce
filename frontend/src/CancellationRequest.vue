<script setup>
import { computed, ref } from 'vue'
import { call } from './api.js'
const props = defineProps({ order: { type: Object, required: true } })
const emit = defineEmits(['updated'])
const reason = ref(''), busy = ref(false), error = ref(''), activity = ref(null)
const info = computed(() => props.order.cancellation || {})
const early = computed(() => ['Requested', 'Accepted'].includes(props.order.status))
const canRequest = computed(() => ['Admin', 'Shop', 'Customer'].includes(info.value.role) && (!info.value.status || (['Shop','Admin'].includes(info.value.role) && ['Awaiting approvals','Rejected'].includes(info.value.status))) && props.order.status !== 'Cancelled' &&
  (['Admin', 'Shop'].includes(info.value.role) || props.order.status !== 'Delivered'))
const money = value => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(value / 100)
async function run(method, extra = {}) {
  if (busy.value) return
  busy.value = true; error.value = ''
  try { await call(`cancellations.${method}`, { order: props.order.name, ...extra }, true); emit('updated') }
  catch (e) { error.value = e.message }
  finally { busy.value = false }
}
async function history() {
  try { activity.value = await call('cancellations.activity', { order: props.order.name }) }
  catch (e) { error.value = e.message }
}
</script>
<template>
  <section class="cancellation-card">
    <h3>Cancellation &amp; settlement</h3>
    <p>{{ info.settlement }}</p>
    <p v-if="error" role="alert" class="lc-notice">{{ error }}</p>
    <template v-if="info.status">
      <strong>{{ info.status }}</strong><p>{{ info.reason }}</p>
      <p v-if="info.status === 'Awaiting approvals'">Fulfilment is paused until the shop owner and a separate administrator decide.</p>
      <p v-if="info.refund_status" role="status">{{ info.refund_status }}</p>
      <p v-if="info.error">{{ info.error }}</p>
      <p v-if="info.shop_approval">Shop: {{ info.shop_approval.decision }}</p>
      <p v-if="info.admin_approval">Admin: {{ info.admin_approval.decision }}</p>
      <dl v-if="info.amounts">
        <dt>Customer refund</dt><dd>{{ money(info.amounts.refund_paise) }}</dd>
        <dt>Actual gateway charges, including tax</dt><dd>{{ money(info.amounts.gateway_fee_paise) }}</dd>
        <dt>Preparation compensation before gateway charges</dt><dd>{{ money(info.amounts.compensation_paise) }}</dd>
        <dt>Commission on compensation</dt><dd>{{ money(info.amounts.commission_paise) }}</dd>
        <template v-if="info.role !== 'Customer'"><dt>Vendor compensation after fees</dt><dd>{{ money(info.amounts.vendor_paise) }}</dd><dt>Cancellation cost owed by shop</dt><dd>{{ money(info.amounts.shop_debt_paise) }}</dd></template>
      </dl>
      <p v-if="info.status !== 'Completed — no payment'">A requested refund is not a confirmed bank credit. See the financial activity for confirmation.</p>
      <form v-if="info.status === 'Awaiting approvals' && ['Admin','Shop'].includes(info.role)" @submit.prevent="run('decide', { decision: 'Approve', note: reason, role: info.role })">
        <label>Decision reason<textarea v-model="reason" required minlength="3" maxlength="1000" /></label>
        <button :disabled="busy">Approve cancellation</button>
        <button type="button" :disabled="busy || reason.trim().length < 3" @click="run('decide', { decision: 'Reject', note: reason, role: info.role })">Reject cancellation</button>
      </form>
    </template>
    <details v-if="canRequest">
      <summary>{{ info.role === 'Customer' && !early ? 'Request cancellation' : 'Cancel order' }}</summary>
      <p v-if="info.role !== 'Customer'">The customer receives a full refund of the paid amount. The shop bears actual gateway costs.</p>
      <p v-else-if="early">Cancel before preparation: refund of the amount paid minus actual Cashfree gateway charges, including tax.</p>
      <p v-else>Both the shop owner and administrator must approve. Your refund will be 85% of the paid amount; 15% covers preparation. No marketplace commission is taken from that compensation.</p>
      <form @submit.prevent="run('request', { reason })"><label>Reason<textarea v-model="reason" required minlength="3" maxlength="500" /></label><button :disabled="busy">{{ early || info.role !== 'Customer' ? 'Confirm cancellation' : 'Submit request' }}</button></form>
    </details>
    <button v-if="info.role === 'Admin'" :disabled="busy" @click="run('settlement_check')">Check vendor bank settlement</button>
    <button v-if="info.role === 'Admin'" :disabled="busy" @click="run('retry')">Check / retry existing financial instructions</button>
    <button v-if="['Admin','Shop'].includes(info.role)" @click="history">View financial activity</button>
    <div v-if="activity"><ol><li v-for="(entry, index) in activity.events" :key="index">{{ entry.creation }} · {{ entry.event_type }}<pre>{{ JSON.parse(entry.data_json) }}</pre></li></ol><section v-for="op in activity.operations" :key="op.name"><strong>{{ op.kind }} · {{ op.status }}</strong><pre>{{ JSON.parse(op.payload_json) }}</pre><pre v-if="op.response_json">{{ JSON.parse(op.response_json) }}</pre><details v-if="op.status === 'Unconfirmed' && info.role === 'Admin'"><summary>Retry this same instruction</summary><p>This resends the saved amount with the same Cashfree idempotency key. It does not create a new refund or transfer.</p><button :disabled="busy" @click="run('retry_operation', { operation_name: op.name })">Confirm same-instruction retry</button></details></section></div>
  </section>
</template>
<style scoped>
.cancellation-card { padding: 18px; margin: 16px 0; border: 1px solid #dce5dc; border-radius: 14px; background: #fafcf8; }
h3 { margin-top: 0; } p { line-height: 1.6; } label { display: grid; gap: 8px; margin: 12px 0; }
textarea { width: 100%; min-height: 72px; } button { margin: 8px 8px 0 0; }
dl { display: grid; grid-template-columns: 1fr auto; gap: 10px; } dd { margin: 0; font-weight: 600; }
pre { overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; }
</style>
