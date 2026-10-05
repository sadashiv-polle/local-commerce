<script setup>
import { onMounted, ref } from 'vue'
import { call } from './api.js'
import { checkoutTarget } from './checkout-target.js'
import { useRoute } from 'vue-router'
const route = useRoute()
const props = defineProps({ order: { type: Object, required: true }, customer: Boolean, autoStart: Boolean })
const emit = defineEmits(['updated', 'checkout-started'])
const busy = ref(false), error = ref('')
async function refresh() {
  busy.value = true; error.value = ''
  try { await call('cashfree.verify', { order: props.order.name }, true); emit('updated') }
  catch (e) { error.value = e.message }
  finally { busy.value = false }
}
async function pay() {
  if (busy.value) return
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
    const target = checkoutTarget()
    const result = await window.Cashfree({ mode: session.environment }).checkout({
      paymentSessionId: session.payment_session_id, redirectTarget: target,
    })
    if (target === '_modal' || result?.error) await refresh()
    if (result?.error) error.value ||= 'Checkout was closed or could not finish. Payment status was checked; retry only if payment is still pending.'
  } catch (e) { error.value = e.message }
  finally { busy.value = false }
}
onMounted(() => {
  if (props.customer && route.path === '/orders' && route.query.order === props.order.name && !props.autoStart) { refresh(); return }
  if (!props.autoStart || !props.customer) return
  emit('checkout-started')
  if (props.order.status === 'Requested' && ['Pending', 'Failed'].includes(props.order.payment_status)) pay()
})
</script>
<template>
  <section class="order-rating">
    <strong>Cashfree payment · {{ order.payment_status }}</strong>
    <p v-if="order.refunded_amount > 0">Refund recorded: {{ new Intl.NumberFormat(undefined, { style: 'currency', currency: order.currency || 'INR' }).format(order.refunded_amount) }}. Check your bank for the credit. Contact the shop about any remaining items before delivery.</p>
    <p v-else-if="order.payment_status === 'Paid'">Payment received. No cash is due at delivery.</p>
    <p v-else-if="order.payment_status === 'Reconciled'">A payment receipt is recorded. Refresh payment status to verify it before delivery. Do not pay again.</p>
    <p v-else-if="order.payment_status === 'Refunded'">Your payment has been refunded.</p>
    <p v-else>Complete payment to confirm your order. The shop accepts it automatically after payment is verified.</p>
    <p v-if="order.accounting_pending">Payment received; the shop is resolving an order processing issue.</p>
    <div class="button-row">
      <button v-if="customer && ['Pending', 'Failed'].includes(order.payment_status) && order.status !== 'Cancelled'" :disabled="busy" class="lc-primary" @click="pay">Pay securely</button>
      <button :disabled="busy" @click="refresh">{{ busy ? 'Checking…' : 'Refresh payment status' }}</button>
    </div>
    <p v-if="error" role="alert" class="lc-notice">{{ error }}</p>
  </section>
</template>
