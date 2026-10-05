<script setup>
import { inject, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { call } from './api.js'
import { loginUrl } from './cart.js'
import OrderReference from './OrderReference.vue'
const session = inject('session'), route = useRoute()
const order = ref(null), error = ref(''), loading = ref(false)
let generation = 0
async function load() {
  const current = ++generation
  order.value = null; error.value = ''
  if (session.value.user === 'Guest') return
  loading.value = true
  try {
    const result = await call('orders.detail', { order: route.params.order })
    if (current === generation) order.value = result
  } catch {
    if (current === generation) error.value = 'This order could not be opened. Sign in with the account used to place it, or contact the shop if it still does not load.'
  } finally { if (current === generation) loading.value = false }
}
function money(value) { return new Intl.NumberFormat('en-IN', { style: 'currency', currency: order.value.currency }).format(value) }
watch(() => route.params.order, load, { immediate: true })
</script>
<template>
  <section class="label-verification inventory-form">
    <span class="eyebrow">PACKAGE DETAILS</span><h1>Check your order</h1>
    <p>Compare these details with the package you received.</p>
    <template v-if="session.user === 'Guest'"><p>Sign in with the account used to place this order to view its details.</p><a class="primary" :href="loginUrl(route.fullPath)">Sign in to view order</a></template>
    <p v-else-if="loading" role="status">Loading order…</p>
    <div v-else-if="error" role="alert"><p class="lc-notice">{{ error }}</p><button @click="load">Try again</button></div>
    <template v-else-if="order">
      <OrderReference :order-id="order.name" />
      <h2>{{ order.shop_name }}</h2><span class="status-pill">{{ order.status }}</span>
      <h3>{{ order.recipient }}</h3><p>{{ [order.address?.line1, order.address?.city, order.address?.postal_code].filter(Boolean).join(', ') }}</p>
      <ul><li v-for="(item, index) in order.items" :key="index"><span>{{ item.quantity }} {{ item.uom }} · {{ item.name }}</span><strong>{{ money(item.amount) }}</strong></li></ul>
      <p><strong>Order total {{ money(order.total) }}</strong></p>
      <p>{{ order.payment_method }} · {{ order.payment_status }}</p>
      <p class="muted">Scanning this label does not mark the order as delivered. Contact the shop if the contents do not match.</p>
      <button @click="load">Refresh details</button>
    </template>
  </section>
</template>
<style scoped>
.label-verification { max-width: 620px; margin: 20px auto; padding: 24px; }
h1 { font-size: 26px; letter-spacing: normal; }
p { overflow-wrap: anywhere; line-height: 1.5; }
ul { padding: 0; list-style: none; }
li { display: flex; justify-content: space-between; gap: 16px; padding: 12px 0; border-bottom: 1px solid #dce6de; }
li strong { white-space: nowrap; }
@media (max-width: 600px) { .label-verification { margin: 12px; padding: 18px; } }
</style>
