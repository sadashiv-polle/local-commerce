<script setup>
import { onMounted, ref } from 'vue'
import { call } from './api.js'
const categories = { returns: 'Return requests', unpaid: 'Unpaid / payment review', refunds: 'Refund issues', unassigned: 'Unassigned deliveries', expired: 'Expired reservations', accounting: 'Accounting issues' }
const hints = { returns: 'Review returned items and approve or reject the refund. Only administrators can send Cashfree refunds.', unpaid: 'Check payment evidence before processing. COD awaiting delivery is excluded.', refunds: 'Review failed refunds or cancelled paid orders. Use Cashfree to check refund status.', unassigned: 'Assign a rider to these ready orders.', expired: 'Open the order to review stock and repack with fresh stock.', accounting: 'Review Cashfree accounting or cash handover differences.' }
const data = ref(null), category = ref('unpaid'), start = ref(0), busy = ref(false), error = ref('')
async function load(key = category.value, offset = 0) {
  if (busy.value) return
  category.value = key; start.value = offset; busy.value = true; error.value = ''
  try { data.value = await call('admin.attention', { category: key, start: offset }) }
  catch (e) { error.value = e.message; data.value = null }
  finally { busy.value = false }
}
onMounted(() => load())
</script>
<template>
  <section class="attention-panel">
    <header><h2>Needs attention</h2><button :disabled="busy" @click="load(category, start)">Refresh</button></header>
    <div class="attention-tabs"><button v-for="(label, key) in categories" :key="key" :disabled="busy" :aria-pressed="category === key" @click="load(key)">{{ label }} <strong>{{ data?.counts[key] ?? '—' }}</strong></button></div>
    <p>{{ hints[category] }}</p>
    <p v-if="error" role="alert">{{ error }}</p><p v-if="busy" role="status">Loading…</p>
    <template v-else-if="data">
      <p v-if="!data.items.length">Nothing needs attention in this category.</p>
      <article v-for="row in data.items" :key="row.name" class="attention-row"><div><strong>{{ row.shop_name }} · #{{ row.name.slice(0, 8).toUpperCase() }}</strong><p>{{ row.status }} · {{ row.payment_status }}</p></div><RouterLink :to="{ path: '/admin/orders', query: { shop: row.shop, order: row.name } }">Open order →</RouterLink><RouterLink v-if="category === 'accounting' || category === 'refunds'" :to="row.payment_method === 'Cashfree' ? '/admin/cashfree' : { path: '/admin/payments', query: { shop: row.shop } }">Review payment →</RouterLink></article>
      <nav aria-label="Attention pages"><button :disabled="start === 0" @click="load(category, start - 20)">Previous</button><button :disabled="!data.has_more" @click="load(category, start + 20)">Next</button></nav>
    </template>
  </section>
</template>
<style scoped>
.attention-panel { padding: 20px; background: white; border: 1px solid #dce6dc; border-radius: 18px; }
header, .attention-row, nav { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.attention-tabs { display: flex; flex-wrap: wrap; gap: 8px; }
.attention-tabs button { padding: 12px; border-radius: 12px; }
button[aria-pressed=true] { background: #176547; color: white; }
.attention-row { padding: 16px 0; border-bottom: 1px solid #dce6dc; }
p { color: #63756a; } nav { margin-top: 16px; }
</style>
