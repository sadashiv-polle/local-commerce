<script setup>
import { computed, inject, onMounted, ref } from 'vue'
import { call } from './api.js'

const session = inject('session')
const assignments = ref([]), start = ref(0), loading = ref(false), error = ref(''), busyOrder = ref('')
const allowed = computed(() => session.value.roles.includes('LC Delivery Person') && session.value.memberships.some(member => member.membership_role === 'Driver'))
const next = { Ready: 'Picked Up', 'Picked Up': 'Out for Delivery', 'Out for Delivery': 'Delivered' }
const labels = { Ready: 'Confirm pickup', 'Picked Up': 'Start delivery', 'Out for Delivery': 'Confirm delivered' }

function money(value, currency) { return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(value) }
async function load(delta = 0) {
  if (!allowed.value) return
  start.value = Math.max(0, start.value + delta); loading.value = true; error.value = ''
  try { assignments.value = await call('orders.delivery_assignments', { start: start.value }) }
  catch (e) { error.value = e.message }
  finally { loading.value = false }
}
async function advance(order) {
  busyOrder.value = order.name; error.value = ''
  try { await call('orders.delivery_change', { order: order.name, target: next[order.status] }, true); await load() }
  catch (e) { error.value = e.message }
  finally { busyOrder.value = '' }
}
onMounted(load)
</script>

<template>
  <section v-if="!allowed" class="lc-empty delivery-empty"><h2>Delivery access is not configured</h2><p>Your account needs the LC Delivery Person role and an enabled Driver membership for a shop.</p></section>
  <section v-else class="delivery-page">
    <header class="delivery-hero"><div><span class="eyebrow">RIDER WORKSPACE</span><h1>Your deliveries</h1><p>Pickup, deliver, and keep every customer informed.</p></div><div class="rider-avatar" aria-hidden="true">{{ session.full_name.slice(0, 1).toUpperCase() }}</div></header>
    <div class="delivery-toolbar"><div><strong>{{ assignments.filter(order => !['Delivered', 'Cancelled'].includes(order.status)).length }}</strong><span>active deliveries</span></div><button :disabled="loading || busyOrder" @click="load()">Refresh</button></div>
    <p v-if="error" class="lc-notice" role="alert">{{ error }}</p>
    <p v-if="loading" role="status">Loading your deliveries…</p>
    <p v-else-if="!assignments.length" class="lc-empty">No orders are assigned to you yet.</p>
    <div v-else class="delivery-list">
      <article v-for="order in assignments" :key="order.name" class="delivery-card" :class="{ finished: ['Delivered', 'Cancelled'].includes(order.status) }">
        <header><div><span class="eyebrow">{{ order.shop_name }} · {{ order.name }}</span><h2>{{ order.recipient }}</h2></div><span class="status-pill">{{ order.status }}</span></header>
        <div class="delivery-address"><span aria-hidden="true">⌖</span><div><strong>{{ order.address.line1 }}</strong><p>{{ order.address.city }} · {{ order.address.postal_code }}</p><a :href="`tel:${order.phone}`">Call {{ order.phone }}</a></div></div>
        <details><summary>{{ order.items.length }} product{{ order.items.length === 1 ? '' : 's' }} · {{ money(order.total, order.currency) }}</summary><ul><li v-for="(item, index) in order.items" :key="index">{{ item.quantity }} {{ item.uom }} · {{ item.name }}</li></ul></details>
        <button v-if="next[order.status]" class="delivery-action" :disabled="!!busyOrder" @click="advance(order)">{{ busyOrder === order.name ? 'Updating…' : labels[order.status] }} <span>›</span></button>
        <p v-else-if="order.status === 'Delivered'" class="delivery-complete">✓ Delivered{{ order.delivered_at ? ` · ${order.delivered_at}` : '' }}</p>
        <p v-else-if="order.status === 'Cancelled'" class="muted">This order was cancelled.</p>
      </article>
    </div>
    <div class="lc-pagination"><button :disabled="!start || loading || busyOrder" @click="load(-20)">Previous</button><span>Page {{ start / 20 + 1 }}</span><button :disabled="assignments.length < 20 || loading || busyOrder" @click="load(20)">Next</button></div>
  </section>
</template>
