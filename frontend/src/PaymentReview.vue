<script setup>
import { ref, watch } from 'vue'
import { call } from './api.js'
import OrderReference from './OrderReference.vue'
import ManualUpiPayment from './ManualUpiPayment.vue'
import GatewayPayment from './GatewayPayment.vue'
const props = defineProps({ shop: { type: String, required: true } })
const category = ref('upi'), start = ref(0), orders = ref([]), more = ref(false), loading = ref(false), error = ref('')
const categories = [ ['upi', 'UPI proofs'], ['cashfree', 'Pending / failed'], ['accounting', 'Accounting issues'], ['refunds', 'Refund history'] ]
let generation = 0
async function load() {
  const current = ++generation
  loading.value = true; error.value = ''
  try {
    const result = await call('payment_review.list_orders', { shop: props.shop, category: category.value, start: start.value })
    if (current === generation) { orders.value = result.orders; more.value = result.has_more }
  } catch (e) { if (current === generation) error.value = e.message }
  finally { if (current === generation) loading.value = false }
}
watch([() => props.shop, category], () => { start.value = 0; orders.value = []; load() }, { immediate: true })
function page(delta) { start.value += delta; orders.value = []; load() }
</script>
<template>
  <section>
    <div class="section-title"><div><h2>Payment review</h2><p>Review payment evidence and recover orders using the existing payment controls.</p></div><button :disabled="loading" @click="load">Refresh</button></div>
    <nav class="panel-tabs" aria-label="Payment review categories"><button v-for="[key, label] in categories" :key="key" :aria-pressed="category === key" @click="category = key">{{ label }}</button></nav>
    <p v-if="category === 'refunds'" class="lc-notice">This is refund history, not a list of unresolved refunds. Initiate refunds in Cashfree. An administrator must reconcile credit notes and refund payments in ERPNext.</p>
    <p v-if="category === 'accounting'" class="lc-notice">A payment may have succeeded while accounting failed. Do not ask the customer to pay again. Correct the accounting setup, then refresh payment status.</p>
    <p v-if="error" role="alert" class="lc-notice">{{ error }}</p><p v-if="loading" role="status">Loading payments…</p>
    <p v-if="!loading && !error && !orders.length" class="lc-empty">No orders in this category.</p>
    <article v-for="order in orders" :key="order.name" class="payment-review-card">
      <OrderReference :order-id="order.name" /><h3>{{ order.customer_name || 'Customer order' }}</h3><p>Order: {{ order.status }} · Payment: {{ order.payment_status }}</p>
      <GatewayPayment v-if="order.payment_method === 'Cashfree'" :order="order" @updated="load" />
      <ManualUpiPayment v-else :order="order" editable @updated="load" />
    </article>
    <div class="lc-pagination"><button :disabled="loading || !start" @click="page(-20)">Previous</button><span>Page {{ start / 20 + 1 }}</span><button :disabled="loading || !more" @click="page(20)">Next</button></div>
  </section>
</template>
<style scoped>
.payment-review-card { border: 1px solid #dce6dc; border-radius: 16px; padding: clamp(12px, 3vw, 24px); margin: 16px 0; min-width: 0; }
.payment-review-card :deep(code) { overflow-wrap: anywhere; }
</style>
