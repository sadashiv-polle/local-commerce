<script setup>
import { ref } from 'vue'
import { call } from './api.js'
const props = defineProps({ order: { type: Object, required: true }, customer: Boolean })
const emit = defineEmits(['updated'])
const busy = ref(false), error = ref('')
async function refresh() {
  busy.value = true; error.value = ''
  try { await call('cashfree.verify', { order: props.order.name }, true); emit('updated') }
  catch (e) { error.value = e.message }
  finally { busy.value = false }
}
async function pay() {
  busy.value = true; error.value = ''
  try {
    const session = await call('cashfree.checkout', { order: props.order.name }, true)
    if (!window.Cashfree) await new Promise((resolve, reject) => {
      const script = document.createElement('script')
      script.src = 'https://sdk.cashfree.com/js/v3/cashfree.js'
      script.onload = resolve
      script.onerror = () => { script.remove(); reject(new Error('Payment checkout could not load. Please retry.')) }
      document.head.appendChild(script)
    })
    await window.Cashfree({ mode: session.environment }).checkout({
      paymentSessionId: session.payment_session_id, redirectTarget: '_modal',
    })
    await refresh()
  } catch (e) { error.value = e.message }
  finally { busy.value = false }
}
</script>
<template>
  <section class="order-rating">
    <strong>Cashfree payment · {{ order.payment_status }}</strong>
    <p v-if="order.payment_status === 'Paid'">Payment received. No cash is due at delivery.</p>
    <p v-else-if="order.payment_status === 'Refunded'">Your payment has been refunded.</p>
    <p v-else>Complete your secure online payment before the shop prepares your order.</p>
    <p v-if="order.accounting_pending">Payment received; the shop is resolving an order processing issue.</p>
    <div class="button-row">
      <button v-if="customer && !['Paid', 'Refunded'].includes(order.payment_status) && order.status !== 'Cancelled'" :disabled="busy" class="lc-primary" @click="pay">Pay securely</button>
      <button :disabled="busy" @click="refresh">{{ busy ? 'Checking…' : 'Refresh payment status' }}</button>
    </div>
    <p v-if="error" role="alert" class="lc-notice">{{ error }}</p>
  </section>
</template>
