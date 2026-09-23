<script setup>
import { computed, ref } from 'vue'
import { call, upload } from './api.js'
const props = defineProps({ order: { type: Object, required: true }, editable: Boolean })
const emit = defineEmits(['updated'])
const busy = ref(false), error = ref(''), reference = ref(''), note = ref(''), confirmed = ref(false)
const amount = computed(() => new Intl.NumberFormat('en-IN', { style: 'currency', currency: props.order.currency }).format(props.order.total))
const link = computed(() => `upi://pay?${new URLSearchParams({ pa: props.order.upi.id, pn: props.order.shop_name, am: Number(props.order.total).toFixed(2), cu: 'INR', tn: `Order ${props.order.name}` })}`)
async function proof(event) {
  const file = event.target.files?.[0]; if (!file) return
  busy.value = true; error.value = ''
  try { await upload('manual_upi.upload_proof', { order: props.order.name }, file); emit('updated') } catch (e) { error.value = e.message } finally { busy.value = false; event.target.value = '' }
}
async function review(approve) {
  if (approve && !confirmed.value) { error.value = 'Confirm that you checked the receipt in your bank account.'; return }
  busy.value = true; error.value = ''
  try { await call('manual_upi.review', { order: props.order.name, approve, reference: reference.value, note: note.value }, true); emit('updated') } catch (e) { error.value = e.message } finally { busy.value = false }
}
</script>
<template>
  <section v-if="order.upi" class="upi-payment">
    <span class="eyebrow">UPI PAYMENT</span><h3>{{ order.payment_status === 'Paid' ? 'Payment verified' : order.payment_status === 'Awaiting Verification' ? 'Payment under review' : 'Scan, pay & upload proof' }}</h3>
    <p v-if="order.payment_status === 'Paid'" class="success-note">{{ amount }} received · No cash due at delivery.</p>
    <p v-else-if="order.payment_status === 'Awaiting Verification'">{{ editable ? 'Check the actual credit in your bank account. A screenshot alone does not confirm payment.' : 'Your screenshot was sent. Please wait for the shop to verify it; do not pay again.' }}</p>
    <p v-else-if="!order.upi.payable">Wait for the shop to accept your order before paying.</p>
    <template v-else-if="!editable">
      <p>Pay <strong>{{ amount }}</strong> to <strong>{{ order.shop_name }}</strong>. Check the payee shown in your UPI app.</p>
      <img v-if="order.upi.qr" :src="order.upi.qr" alt="Scan this QR in your UPI app" class="upi-qr">
      <p class="upi-id">{{ order.upi.id }}</p><a :href="link" class="lc-primary">Open UPI app · {{ amount }}</a>
      <p v-if="order.payment_status === 'Payment Rejected'">Please check the shop's note below before paying again.</p>
      <label class="upi-upload">Already paid? Upload screenshot<input type="file" accept="image/jpeg,image/png,image/webp" :disabled="busy" @change="proof"><small>JPG, PNG or WebP · up to 5 MB</small></label>
    </template>
    <p v-if="order.upi.note" class="lc-notice">{{ order.upi.note }}</p>
    <a v-if="order.upi.proof" :href="order.upi.proof" target="_blank" rel="noopener">View payment screenshot ↗</a>
    <form v-if="editable && order.payment_status === 'Awaiting Verification'" @submit.prevent="review(true)">
      <fieldset :disabled="busy" class="workspace-fields">
        <label>Bank transaction reference<input v-model="reference" maxlength="100" placeholder="UTR / bank reference"></label>
        <label>Review note<textarea v-model="note" maxlength="500" placeholder="Required when rejecting proof"></textarea></label>
        <label class="check-label"><input v-model="confirmed" type="checkbox">I verified receipt of {{ amount }} in the bank account.</label>
        <div class="upi-actions"><button type="button" @click="review(false)">Reject proof</button><button class="lc-primary">Confirm payment received</button></div>
      </fieldset>
    </form>
    <p v-if="error" class="lc-notice" role="alert">{{ error }}</p>
  </section>
</template>
