<script setup>
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { call } from './api.js'
import OrderReference from './OrderReference.vue'
const route = useRoute()
const order = ref(null), error = ref(''), loading = ref(false)
let generation = 0
async function load() {
  const current = ++generation
  order.value = null; error.value = ''
  loading.value = true
  try {
    const result = await call('orders.label_details', { order: route.params.order, token: typeof route.query.token === 'string' ? route.query.token : '' }, true)
    if (current === generation) order.value = result
  } catch {
    if (current === generation) error.value = 'This order could not be opened. Scan a newly printed label or ask the shop to check the link.'
  } finally { if (current === generation) loading.value = false }
}
function money(value) { return new Intl.NumberFormat('en-IN', { style: 'currency', currency: order.value.currency }).format(value) }
watch([() => route.params.order, () => route.query.token], load, { immediate: true })
</script>
<template>
  <section class="label-verification inventory-form">
    <span class="eyebrow">PACKAGE DETAILS</span><h1>Check your order</h1>
    <p>Compare these details with the package you received.</p>
    <p v-if="loading" role="status">Loading order…</p>
    <div v-else-if="error" role="alert"><p class="lc-notice">{{ error }}</p><button @click="load">Try again</button></div>
    <template v-else-if="order">
      <OrderReference :order-id="order.name" />
      <h2>{{ order.shop_name }}</h2><span class="status-pill">{{ order.status }}</span>
      <ul><li v-for="(item, index) in order.items" :key="index"><span>{{ item.quantity }} {{ item.uom }} · {{ item.name }}</span><strong>{{ money(item.amount) }}</strong></li></ul>
      <p><strong>Order total {{ money(order.total) }}</strong></p>
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
