<script setup>
import { inject, ref, watch } from 'vue'
import AuthChoices from './AuthChoices.vue'
const session = inject('session')
import { call } from './api.js'
const props = defineProps({ shop: { type: String, default: '' }, editable: Boolean })
const orders = ref([]), start = ref(0), error = ref(''), loading = ref(false), busy = ref(false)
const reasons = ref({})
const next = { Requested: 'Accepted', Accepted: 'Preparing', Preparing: 'Ready' }
let generation = 0
function money(value, currency) { return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(value) }
async function load(delta = 0) {
  if (session.value.user === 'Guest') return
  const current = ++generation
  start.value = Math.max(0, start.value + delta); loading.value = true; error.value = ''
  try {
    const result = await call('orders.list_orders', { ...(props.shop ? { shop: props.shop } : {}), start: start.value })
    if (current === generation) orders.value = result
  } catch (e) { if (current === generation) error.value = e.message }
  finally { if (current === generation) loading.value = false }
}
async function change(order, target) {
  busy.value = true; error.value = ''
  try { await call('orders.change', { order: order.name, target, reason: reasons.value[order.name] || '' }, true); await load() }
  catch (e) { error.value = e.message }
  finally { busy.value = false }
}
watch(() => props.shop, () => { start.value = 0; load() }, { immediate: true })
</script>
<template>
  <AuthChoices v-if="session.user === 'Guest'" />
  <section v-else class="orders-page">
    <div class="inventory-heading"><div><span class="eyebrow">DELIVERY REQUESTS</span><h2>{{ shop ? 'Your orders' : 'My orders' }}</h2><p>Requests need shop confirmation. Payment and driver dispatch are not available here yet.</p></div><button :disabled="loading || busy" @click="load()">Refresh orders</button></div>
    <p v-if="error" class="lc-notice" role="alert">{{ error }}</p>
    <p v-if="loading" role="status">Loading orders…</p>
    <p v-else-if="!orders.length" class="lc-empty">No delivery requests yet.</p>
    <article v-for="order in orders" :key="order.name" class="order-card">
      <div class="workspace-heading"><div><span class="eyebrow">{{ order.shop_name }}</span><h3>{{ order.recipient }}</h3><small>{{ order.created }}</small></div><span class="status-pill">{{ order.status }}</span></div>
      <ul><li v-for="(item, index) in order.items" :key="index">{{ item.quantity }} {{ item.uom }} · {{ item.name }} <strong>{{ money(item.amount, order.currency) }}</strong></li></ul>
      <p><strong>Order total {{ money(order.total, order.currency) }}</strong><br><small>Includes {{ money(order.taxes_and_charges, order.currency) }} in configured taxes and charges. No payment collected.</small></p>
      <details><summary>Delivery details</summary><p>{{ order.address.line1 }}<br>{{ order.address.city }} · {{ order.address.postal_code }}<br>{{ order.phone }}</p></details>
      <p v-if="order.reason">Cancellation: {{ order.reason }}</p>
      <p v-if="order.status === 'Requested'" class="muted">Stock is checked again when the shop accepts. Delivery timing needs confirmation.</p>
      <p v-if="order.status === 'Ready'" class="muted">Ready for dispatch. Driver assignment and delivery confirmation are not enabled yet.</p>
      <div v-if="(shop && editable) || (!shop && order.status === 'Requested')" class="order-actions">
        <button v-if="shop && next[order.status]" class="lc-primary" :disabled="busy" @click="change(order, next[order.status])">{{ { Requested: 'Accept order', Accepted: 'Start preparing', Preparing: 'Mark ready' }[order.status] }}</button>
        <details v-if="order.status !== 'Cancelled'"><summary>Cancel request</summary><label>Reason<input v-model="reasons[order.name]" minlength="3" maxlength="500"></label><button :disabled="busy || (reasons[order.name] || '').trim().length < 3" @click="change(order, 'Cancelled')">Confirm cancellation</button></details>
      </div>
    </article>
    <div class="lc-pagination"><button :disabled="!start || loading || busy" @click="load(-20)">Previous</button><span>Page {{ start / 20 + 1 }}</span><button :disabled="orders.length < 20 || loading || busy" @click="load(20)">Next</button></div>
  </section>
</template>
