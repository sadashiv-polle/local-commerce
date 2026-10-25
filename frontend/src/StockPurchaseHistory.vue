<script setup>
import { onMounted, ref } from 'vue'
import { call } from './api.js'
import { displayTime } from './display-time.js'
const props = defineProps({ shop: { type: String, required: true } })
const rows = ref([]), start = ref(0), purchases = ref(true), busy = ref(false), error = ref('')
let sequence = 0
function money(value, currency) { return new Intl.NumberFormat('en-IN', { style: 'currency', currency: currency || 'INR' }).format(value) }
async function load(delta = 0, reset = false) {
  const request = ++sequence
  start.value = reset ? 0 : Math.max(0, start.value + delta)
  busy.value = true; error.value = ''; rows.value = []
  try {
    const result = await call('owner.history', { shop: props.shop, start: start.value, purchases_only: purchases.value ? 1 : 0 })
    if (request === sequence) rows.value = result
  } catch (e) { if (request === sequence) error.value = e.message }
  finally { if (request === sequence) busy.value = false }
}
onMounted(() => load())
</script>
<template>
  <section class="purchase-register">
    <h3>Purchases & stock history</h3>
    <p>Track stock received through this app. Personally funded purchases have a stock receipt and a funding journal; they are not supplier Purchase Invoices. ERPNext Purchasing transactions are tracked separately.</p>
    <label>Show <select v-model="purchases" :disabled="busy" @change="load(0, true)"><option :value="true">Purchases paid personally</option><option :value="false">All app stock movements</option></select></label>
    <button :disabled="busy" @click="load()">Refresh</button>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-else-if="busy" role="status">Loading stock records…</p>
    <p v-else-if="!rows.length">No records on this page. To record a purchase, open a product → Stock, choose Add and “Purchase paid personally by shop owner”, then enter quantity and purchase cost.</p>
    <article v-for="row in rows" :key="row.name">
      <strong>{{ row.item }}</strong>
      <span>{{ row.action === 'Add' && row.stock_source === 'Personal funds' ? 'Personally funded purchase' : row.action === 'Add' ? 'Stock receipt / adjustment' : 'Stock removal' }}</span>
      <p>Quantity: {{ row.quantity }} <template v-if="row.action === 'Add'">· Purchase / receipt cost per unit: {{ money(row.unit_cost, row.currency) }} · Total: <strong>{{ money(Number(row.quantity) * Number(row.unit_cost), row.currency) }}</strong></template></p>
      <p>{{ row.reason }}</p>
      <small>{{ displayTime(row.creation) }} · Recorded by {{ row.owner }}</small>
      <small>Stock voucher: {{ row.stock_entry }} · Warehouse: {{ row.warehouse }}</small>
      <small v-if="row.funding_journal">Funding journal: {{ row.funding_journal }} · Paid personally; recorded as money owed to the shop owner</small>
      <small v-else>{{ row.stock_source || 'Legacy record — funding not recorded' }}</small>
    </article>
    <div class="lc-pagination"><button :disabled="busy || !start" @click="load(-20)">Previous</button><span>Page {{ Math.floor(start / 20) + 1 }}</span><button :disabled="busy || rows.length < 20" @click="load(20)">Next</button></div>
  </section>
</template>
<style scoped>
.purchase-register { padding: 1rem; margin: 1rem 0; border: 1px solid #d7e4dc; border-radius: 16px; background: #f7faf7; }
h3 { margin-top: 0; }
article { padding: 1rem 0; border-bottom: 1px solid #d7e4dc; overflow-wrap: anywhere; }
article > strong, article > span, small { display: block; margin-bottom: .4rem; }
p { line-height: 1.6; }
label { display: inline-flex; flex-wrap: wrap; align-items: center; gap: .5rem; margin-right: .5rem; }
select { max-width: 100%; }
</style>
