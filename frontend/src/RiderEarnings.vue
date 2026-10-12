<script setup>
import { onMounted, ref } from 'vue'
import { call } from './api.js'
const data = ref(null), busy = ref(false), error = ref('')
const money = (amount, currency) => new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(amount || 0)
async function load() {
  busy.value = true; error.value = ''
  try { data.value = await call('orders.rider_earnings') }
  catch (e) { error.value = e.message }
  finally { busy.value = false }
}
onMounted(load)
</script>
<template>
  <section class="earnings-panel">
    <header><h2>Delivery earnings & cash</h2><button :disabled="busy" @click="load">Refresh</button></header>
    <p>Shop owners pay you directly. The app does not make payouts. These all-time earnings use rates set by the administrator; a zero total does not confirm whether the shop has paid you.</p>
    <p v-if="error" role="alert">{{ error }}</p><p v-if="busy" role="status">Loading totals…</p>
    <template v-if="data">
      <p v-if="!data.delivered.length">No completed deliveries yet.</p>
      <article v-for="row in data.delivered" :key="`${row.shop}-${row.currency}`"><strong>{{ row.shop_name }}</strong><dl><div><dt>Completed deliveries</dt><dd>{{ row.deliveries }}</dd></div><div><dt>Recorded earnings</dt><dd>{{ money(row.earned, row.currency) }}</dd></div></dl><p v-if="Number(row.unrecorded)">{{ row.unrecorded }} older deliveries have no recorded rider rate and are excluded from earnings.</p></article>
      <article v-for="row in data.cash" :key="`cash-${row.shop}-${row.currency}`"><strong>{{ row.shop_name }} · Cash handovers</strong><dl><div><dt>Cash collected</dt><dd>{{ money(row.collected, row.currency) }}</dd></div><div><dt>Cash due to shop</dt><dd>{{ money(row.due, row.currency) }}</dd></div></dl><p v-if="Number(row.differences)">{{ row.differences }} handovers need an accounting review. Cash already handed over is not counted again.</p></article>
    </template>
  </section>
</template>
<style scoped>
.earnings-panel { margin: 16px 0; padding: 20px; border: 1px solid #dce6dc; border-radius: 18px; background: white; }
header, dl { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 16px; } article { border-top: 1px solid #dce6dc; padding: 16px 0; } p, dt { color: #63756a; } dd { margin: 6px 0 0; font-size: 22px; font-weight: 700; }
</style>
