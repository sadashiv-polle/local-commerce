<script setup>
import { inject, onMounted, ref } from 'vue'
import { call } from './api.js'
import AuthChoices from './AuthChoices.vue'
const session = inject('session'), data = ref(null), error = ref(''), loading = ref(false), start = ref(0)
async function load(delta = 0) {
  start.value = Math.max(0, start.value + delta)
  loading.value = true; error.value = ''
  try { data.value = await call('customers.account', { start: start.value }, true) } catch(e) { error.value = e.message } finally { loading.value = false }
}
onMounted(() => { if (session.value.user !== 'Guest') load() })
</script>
<template>
  <div class="store-page">
    <AuthChoices v-if="session.user === 'Guest'" /><template v-else>
      <h1>Your account</h1><p>{{ session.full_name }} · {{ session.user }}</p><p v-if="loading" role="status">Loading account…</p>
      <p v-if="error" class="lc-notice" role="alert">{{ error }} <button @click="load()">Retry</button></p>
      <template v-if="data">
        <p>Customer: <strong>{{ data.customer.customer_name }}</strong></p><RouterLink class="primary" to="/orders">My delivery requests →</RouterLink>
        <h2>Recent order history</h2><p v-if="!data.orders.length" class="lc-empty">No previous sales orders.</p>
        <article v-for="order in data.orders" :key="order.name" class="order-card"><strong>{{ order.name }}</strong><p>{{ order.transaction_date }} · {{ order.status }}</p><span>{{ order.currency }} {{ order.grand_total }}</span></article>
        <div class="lc-pagination"><button :disabled="loading || !start" @click="load(-20)">Previous</button><span>Page {{ start / 20 + 1 }}</span><button :disabled="loading || data.orders.length < 20" @click="load(20)">Next</button></div>
      </template><p><a href="/me">Manage login and profile ↗</a></p>
    </template>
  </div>
</template>
