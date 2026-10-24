<script setup>
import { computed, inject, ref } from 'vue'
import { call } from './api.js'
const props = defineProps({ order: { type: Object, required: true }, customer: Boolean, reviewer: Boolean })
const emit = defineEmits(['updated'])
const session = inject('session')
const reason = ref(''), reviewNote = ref(''), decisionNote = ref(''), kind = ref('Full'), amount = ref('')
const creditNote = ref(''), paymentEntry = ref('')
const busy = ref(false), error = ref(''), confirm = ref(false)
const request = computed(() => props.order.return_request || {})
const admin = computed(() => !!session?.value?.platform_admin)
const remaining = computed(() => Math.max(0, Number(props.order.total) - Number(props.order.refunded_amount || 0)))
const displayMoney = value => new Intl.NumberFormat('en-IN', { style: 'currency', currency: props.order.currency || 'INR' }).format(Number(value))
async function run(method, args) {
  busy.value = true; error.value = ''
  try { await call(`returns.${method}`, { order: props.order.name, ...args }, true); confirm.value = false; emit('updated') }
  catch (e) { error.value = e.message }
  finally { busy.value = false }
}
function approve() {
  run('decide', { decision: 'Approve', decision_note: decisionNote.value, kind: kind.value, amount: amount.value || null, credit_note: creditNote.value || null })
}
</script>
<template>
  <section v-if="request.status || (customer && order.status === 'Delivered')" class="return-card">
    <h3>Return &amp; refund</h3>
    <p v-if="error" class="lc-notice" role="alert">{{ error }}</p>
    <template v-if="request.status">
      <strong class="return-status">{{ request.status }}</strong>
      <p>{{ request.reason }}</p>
      <p v-if="request.review_note"><b>Shop review:</b> {{ request.review_note }}</p>
      <p v-if="request.decision_note"><b>Administrator decision:</b> {{ request.decision_note }}</p>
      <p v-if="request.amount">Approved refund: <b>{{ displayMoney(request.amount) }}</b> · {{ request.kind }}</p>
      <p v-if="request.status === 'Needs review'">The refund needs administrator review. This does not confirm that money was returned.</p>
      <ol><li v-for="(event, index) in request.events || []" :key="index">{{ event.status }} · {{ new Date(event.at.replace(' ', 'T')).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short', hour12: true }) }}</li></ol>
      <p v-if="request.status === 'Manual refund recorded'">The administrator recorded a refund against submitted accounting documents. This app did not initiate a bank transfer.</p>
      <p>{{ request.stock_note }}. Contact the shop to arrange any physical return.</p>
      <form v-if="reviewer && request.status === 'Requested'" @submit.prevent="run('review', { review_note: reviewNote })">
        <label>Shop review<textarea v-model="reviewNote" required minlength="3" maxlength="1000" placeholder="Items received, condition, and your recommendation" /></label>
        <button :disabled="busy" type="submit">Send review to administrator</button>
      </form>
      <form v-if="admin && ['Requested', 'Reviewed'].includes(request.status)" @submit.prevent="confirm = true">
        <p v-if="order.payment_method !== 'Cashfree'">{{ order.payment_method }}: arrange the refund and credit note manually. This screen cannot send that payment.</p>
        <template v-if="order.payment_method !== 'Cashfree'">
          <label>Submitted return credit note<input v-model="creditNote" placeholder="ACC-SINV-…"></label>
          <label>Submitted refund Payment Entry<input v-model="paymentEntry" placeholder="ACC-PAY-…"></label>
        </template>
        <label>Decision reason<textarea v-model="decisionNote" required minlength="3" maxlength="1000" /></label>
        <template v-if="order.payment_method === 'Cashfree'">
          <label>Refund type<select v-model="kind" @change="confirm = false"><option>Full</option><option>Partial</option></select></label>
          <p v-if="kind === 'Full'">Refund the remaining paid balance: {{ displayMoney(remaining) }}. Includes paid delivery charges and taxes; prior refunds are deducted.</p>
          <label v-else>Refund amount<input v-model="amount" type="number" min="0.01" :max="remaining" step="0.01" required @input="confirm = false"></label>
          <p v-if="kind === 'Partial' || Number(order.refunded_amount || 0) > 0">Create and submit an item-specific credit note under Admin → Cashfree before approving. GST orders use its items and charges to calculate the vendor refund correctly.</p><label v-if="kind === 'Partial' || Number(order.refunded_amount || 0) > 0">Submitted credit note<input v-model="creditNote" placeholder="Sales Invoice credit note reference"></label>
          <button type="submit" :disabled="busy">Review refund</button>
          <div v-if="confirm" class="return-confirm"><p>Send {{ displayMoney(kind === 'Full' ? remaining : amount) }} to the original Cashfree payment source? This starts a real refund for a production profile.</p><button type="button" :disabled="busy" @click="approve">Approve and send refund</button></div>
        </template>
        <button v-if="order.payment_method !== 'Cashfree'" type="button" :disabled="busy || !creditNote || !paymentEntry || decisionNote.trim().length < 3" @click="run('record_manual', { credit_note: creditNote, payment_entry: paymentEntry, decision_note: decisionNote })">Record completed manual refund</button>
        <button type="button" :disabled="busy || decisionNote.trim().length < 3" @click="run('decide', { decision: 'Reject', decision_note: decisionNote })">Reject return request</button>
      </form>
      <button v-if="admin && ['Needs review', 'Refund processing', 'Refund queued'].includes(request.status)" type="button" :disabled="busy" @click="run('retry', {})">Check / retry same refund</button>
    </template>
    <form v-else @submit.prevent="run('request_return', { reason })">
      <p>Tell the shop which items you want to return and why. Submitting a request does not automatically issue a refund.</p>
      <label>Items and reason<textarea v-model="reason" required minlength="3" maxlength="1000" /></label>
      <button :disabled="busy" type="submit">Request return</button>
    </form>
  </section>
</template>
<style scoped>
.return-card { margin: 16px 0; padding: 20px; border: 1px solid #dce5dc; border-radius: 16px; background: #fafcf8; }
.return-card h3 { margin-top: 0; }
.return-card p, .return-card li { line-height: 1.6; overflow-wrap: anywhere; }
.return-card label { display: grid; gap: 8px; margin: 12px 0; }
.return-card textarea { min-height: 90px; width: 100%; }
.return-card button { margin: 8px 8px 0 0; }
.return-status { color: #176449; }
.return-confirm { background: #fff2d4; border-radius: 10px; padding: 12px; margin-top: 12px; }
</style>
