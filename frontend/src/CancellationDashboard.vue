<script setup>
import { onMounted, ref } from 'vue'
import { call } from './api.js'
import CancellationRequest from './CancellationRequest.vue'
const orders = ref([]), error = ref(''), start = ref(0)
async function load() {
  try { orders.value = (await call('cancellations.queue', { start: start.value })).map(row => ({ ...row, cancellation: { ...row.cancellation, role: 'Admin', settlement: row.marketplace_settlement_state } })) }
  catch (e) { error.value = e.message }
}
function page(delta) { start.value = Math.max(0, start.value + delta); load() }
onMounted(load)
</script>
<template>
  <section class="admin-card"><h2>Marketplace cancellations &amp; settlement holds</h2><p>Review customer requests, refund progress, preparation compensation and provider instructions.</p><p v-if="error" role="alert">{{ error }}</p><button @click="load">Refresh</button><p v-if="!orders.length">No orders using the new policy on this page.</p><details v-for="order in orders" :key="order.name"><summary>{{ order.name }} · {{ order.shop }} · {{ order.cancellation_state || order.status }}</summary><CancellationRequest :order="order" @updated="load" /></details><button :disabled="!start" @click="page(-30)">Previous</button><button :disabled="orders.length < 30" @click="page(30)">Next</button></section>
</template>
