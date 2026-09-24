<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { call } from './api.js'
const props = defineProps({ shop: { type: String, required: true } })
const emit = defineEmits(['open'])
const period = ref('today'), data = ref(null), loading = ref(false), error = ref('')
let generation = 0
function money(value, currency) { return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(value) }
async function load() {
  const current = ++generation
  loading.value = true; error.value = ''
  try { const result = await call('owner.dashboard', { shop: props.shop, period: period.value }); if (current === generation) data.value = result }
  catch (e) { if (current === generation) error.value = e.message }
  finally { if (current === generation) loading.value = false }
}
watch(() => [props.shop, period.value], load, { immediate: true })
onMounted(() => window.addEventListener('lc-orders-change', load))
onBeforeUnmount(() => { generation++; window.removeEventListener('lc-orders-change', load) })
</script>
<template>
  <section class="sales-dashboard">
    <header class="dashboard-heading"><div><span class="eyebrow">BUSINESS OVERVIEW</span><h2>Your shop at a glance</h2></div><div class="dashboard-controls"><select v-model="period" aria-label="Sales period"><option value="today">Today</option><option value="week">This week</option><option value="month">This month</option></select><button :disabled="loading" @click="load">Refresh</button></div></header>
    <p v-if="error" class="lc-notice" role="alert">{{ error }}</p><p v-if="loading" role="status">Updating overview…</p>
    <template v-if="data">
      <div class="dashboard-metrics dashboard-order-summary"><article class="dashboard-sales"><small>TODAY'S SALES</small><strong>{{ money(data.sales, data.currency) }}</strong><span>{{ data.delivered_orders }} delivered orders</span></article><article><small>NEW ORDERS</small><strong>{{ data.status_counts.Requested }}</strong><button @click="emit('open', 'orders')">Review orders →</button></article><article><small>PREPARING</small><strong>{{ data.status_counts.Preparing }}</strong><span>Being prepared now</span></article><article><small>READY</small><strong>{{ data.status_counts.Ready }}</strong><span>Waiting for pickup</span></article><article><small>OUT FOR DELIVERY</small><strong>{{ data.status_counts['Out for Delivery'] }}</strong><span>Currently on the way</span></article><article class="dashboard-attention"><small>STUCK ORDERS</small><strong>{{ data.stuck_orders }}</strong><span>Waiting beyond the response time</span></article></div><p class="dashboard-explanation">Order counts show the current position across all dates. Stuck orders have not changed within the shop’s configured response window.</p>
      <div class="dashboard-panels"><section class="dashboard-panel"><header><h3>Stock needing attention</h3><button @click="emit('open', 'inventory')">Manage stock →</button></header><p v-if="!data.inventory_configured" class="lc-notice">Set up a warehouse to see stock alerts.</p><div class="dashboard-stock-counts"><span><strong>{{ data.low_stock_count }}</strong> low stock</span><span><strong>{{ data.sold_out_count }}</strong> sold out</span></div><ul><li v-for="item in data.low_stock" :key="item.name"><strong>{{ item.item_name }}</strong><span>{{ item.available }} {{ item.uom }} left</span></li><li v-for="item in data.sold_out" :key="item.name"><strong>{{ item.item_name }}</strong><span>Sold out / paused</span></li></ul><p v-if="data.inventory_configured && !data.low_stock_count && !data.sold_out_count" class="muted">No stock alerts right now.</p><small v-if="data.low_stock_count + data.sold_out_count > data.low_stock.length + data.sold_out.length">Open Products &amp; stock to view all items.</small></section><section class="dashboard-panel"><header><h3>Cash awaiting handover</h3></header><div v-for="cash in data.cash_pending" :key="cash.currency" class="dashboard-cash"><strong>{{ money(cash.amount, cash.currency) }}</strong><span>{{ cash.collections }} collections awaiting shop confirmation</span></div><p v-if="!data.cash_pending.length" class="muted">No cash handovers waiting.</p><button class="lc-primary" @click="emit('open', 'cash')">View cash handovers →</button></section></div>
    </template>
  </section>
</template>
