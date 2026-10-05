<script setup>
import { onMounted, ref } from 'vue'
import { call } from './api.js'
import { checkoutTarget } from './checkout-target.js'
import { useRoute } from 'vue-router'
const route = useRoute()
const props = defineProps({ order: { type: Object, required: true }, customer: Boolean, autoStart: Boolean })
const emit = defineEmits(['updated', 'checkout-started'])
const busy = ref(false), error = ref(''), phase = ref(''), verified = ref('')
async function verifyPayment() {
  phase.value = 'checking'
  const result = await call('cashfree.verify', { order: props.order.name }, true)
  verified.value = result.payment_status
  phase.value = result.payment_status === 'Paid' ? 'success' : 'pending'
  emit('updated')
  return result
}
async function refresh() {
  if (busy.value) return
  busy.value = true; error.value = ''
  try { await verifyPayment() }
  catch (e) { phase.value = ''; error.value = e.message }
  finally { busy.value = false }
}
async function pay() {
  if (busy.value) return
  busy.value = true; error.value = ''; phase.value = 'opening'
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
    phase.value = 'checkout'
    const result = await window.Cashfree({ mode: session.environment }).checkout({
      paymentSessionId: session.payment_session_id, redirectTarget: target,
    })
    await verifyPayment()
    if (result?.error && verified.value !== 'Paid') error.value = 'Checkout closed or could not finish. If money was deducted, refresh payment status before paying again.'
  } catch (e) { phase.value = ''; error.value = e.message }
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
    <div v-if="phase" class="checkout-feedback" :class="{ success: phase === 'success' && order.payment_status !== 'Refunded' }" role="status" aria-live="polite">
      <span v-if="['opening', 'checking'].includes(phase)" class="checkout-spinner" aria-hidden="true"></span>
      <span v-else-if="phase === 'success'" class="checkout-check" aria-hidden="true">✓</span>
      <strong>{{ phase === 'opening' ? 'Opening secure payment…' : phase === 'checkout' ? 'Complete payment in the popup' : phase === 'checking' ? 'Checking your payment…' : phase === 'success' ? 'Payment received' : 'Payment status: ' + verified }}</strong>
      <small v-if="phase === 'success'">Payment confirmed by the server. Your order details will update below.</small>
      <small v-if="phase === 'pending'">If you paid, refresh the status before trying again.</small>
    </div>
    <strong>Cashfree payment · {{ order.payment_status }}</strong>
    <p v-if="order.refunded_amount > 0">Refund recorded: {{ new Intl.NumberFormat(undefined, { style: 'currency', currency: order.currency || 'INR' }).format(order.refunded_amount) }}. Check your bank for the credit. Contact the shop about any remaining items before delivery.</p>
    <p v-else-if="order.payment_status === 'Paid'">Payment received. No cash is due at delivery.</p>
    <p v-else-if="order.payment_status === 'Reconciled'">A payment receipt is recorded. Refresh payment status to verify it before delivery. Do not pay again.</p>
    <p v-else-if="order.payment_status === 'Refunded'">Your payment has been refunded.</p>
    <p v-else>Complete payment to confirm your order. The shop accepts it automatically after payment is verified.</p>
    <p v-if="order.accounting_pending">Payment received; the shop is resolving an order processing issue.</p>
    <div class="button-row">
      <button v-if="customer && verified !== 'Paid' && ['Pending', 'Failed'].includes(order.payment_status) && order.status !== 'Cancelled'" :disabled="busy" class="lc-primary" @click="pay">Pay securely</button>
      <button :disabled="busy" @click="refresh">{{ busy ? 'Checking…' : 'Refresh payment status' }}</button>
    </div>
    <p v-if="error" role="alert" class="lc-notice">{{ error }}</p>
  </section>
</template>

<style scoped>
.checkout-feedback { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; padding: 16px; margin-bottom: 16px; border-radius: 14px; background: #f0f5f1; }
.checkout-feedback small { flex-basis: 100%; line-height: 1.5; }
.checkout-feedback.success { color: #17654d; background: #e7f5eb; }
.checkout-check { display: grid; place-items: center; width: 36px; height: 36px; background: #17654d; color: white; border-radius: 50%; animation: payment-pop .3s ease-out; }
.checkout-spinner { width: 22px; height: 22px; border: 3px solid #cbded1; border-top-color: #17654d; border-radius: 50%; animation: payment-spin .8s linear infinite; }
@keyframes payment-spin { to { transform: rotate(360deg); } }
@keyframes payment-pop { from { transform: scale(.7); opacity: 0; } to { transform: scale(1); opacity: 1; } }
@media (prefers-reduced-motion: reduce) { .checkout-check, .checkout-spinner { animation: none; } }
</style>
