<script setup>
import { onMounted, ref } from 'vue'
import { call } from './api.js'
const rows = ref([]), busy = ref(false), error = ref(''), message = ref('')
onMounted(async () => { try { rows.value = await call('admin.rider_rates') } catch (e) { error.value = e.message } })
async function save(row) {
  busy.value = true; error.value = ''; message.value = ''
  try { rows.value = await call('admin.save_rider_rate', { shop: row.name, amount: row.rider_delivery_fee }, true); message.value = 'Rate saved for future delivery completions.' }
  catch (e) { error.value = e.message } finally { busy.value = false }
}
</script>
<template>
  <section class="admin-card rider-rates"><h2>Rider earnings rates</h2><p>Admin only. Leave the rate at 0 until you decide to record rider earnings. Shop owners pay riders directly; the app does not make payouts. Any rate you set applies per completed delivery, including scheduled deliveries, and does not change past earnings or customer delivery charges.</p><p v-if="error" role="alert">{{ error }}</p><p v-if="message" role="status">{{ message }}</p><form v-for="row in rows" :key="row.name" @submit.prevent="save(row)"><label>{{ row.shop_name }} · {{ row.currency }}<input v-model.number="row.rider_delivery_fee" type="number" min="0" max="100000" step="0.01" required :disabled="busy"></label><button :disabled="busy">Save rate</button></form></section>
</template>
<style scoped>
.rider-rates { padding: 20px; margin-top: 20px; } form { display: flex; flex-wrap: wrap; align-items: end; gap: 12px; margin: 16px 0; } label { display: grid; gap: 8px; }
</style>
