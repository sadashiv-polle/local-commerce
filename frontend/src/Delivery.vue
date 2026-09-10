<script setup>
import { computed, inject, onMounted, ref } from 'vue'
import { call } from './api.js'

const session = inject('session')
const profile = ref(null), assignments = ref([]), view = ref('active'), start = ref(0)
const loading = ref(false), error = ref(''), busyOrder = ref('')
const paymentDialog = ref(null), collectingOrder = ref(null)
const collectedAmount = ref(''), collectionNote = ref(''), collectionError = ref('')
const allowed = computed(() => session.value.roles.includes('LC Delivery Person') && session.value.memberships.some(member => member.membership_role === 'Driver'))
const collectionVariance = computed(() => collectingOrder.value ? Number(collectedAmount.value || 0) - Number(collectingOrder.value.total) : 0)
const next = { Ready: 'Picked Up', 'Picked Up': 'Out for Delivery', 'Out for Delivery': 'Delivered' }
const labels = { Ready: 'Confirm pickup', 'Picked Up': 'Start delivery', 'Out for Delivery': 'Confirm delivered' }

function money(value, currency) { return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(value) }
async function load(delta = 0) {
  if (!allowed.value) return
  start.value = Math.max(0, start.value + delta); loading.value = true; error.value = ''
  try { assignments.value = await call('orders.delivery_assignments', { start: start.value, view: view.value }) }
  catch (e) { error.value = e.message }
  finally { loading.value = false }
}
async function loadProfile() {
  if (!allowed.value) return
  try { profile.value = await call('orders.delivery_profile') }
  catch (e) { error.value = e.message }
}
async function refresh() { await Promise.all([load(), loadProfile()]) }
async function switchView(target) { view.value = target; start.value = 0; await load() }
async function advance(order, payment = {}) {
  busyOrder.value = order.name; error.value = ''
  try {
    await call('orders.delivery_change', { order: order.name, target: next[order.status], ...payment }, true)
    await refresh()
  } catch (e) { error.value = e.message }
  finally { busyOrder.value = '' }
}
function requestAdvance(order) {
  if (order.status !== 'Out for Delivery') { advance(order); return }
  collectingOrder.value = order
  collectedAmount.value = String(order.total)
  collectionNote.value = ''
  collectionError.value = ''
  paymentDialog.value.showModal()
}
function cancelCollection() { paymentDialog.value.close(); collectingOrder.value = null; collectionNote.value = ''; collectionError.value = '' }
async function confirmCollection() {
  const order = collectingOrder.value
  const amount = Number(collectedAmount.value)
  if (!Number.isFinite(amount) || amount < 0) { collectionError.value = 'Enter the cash amount you received.'; return }
  if (collectionVariance.value !== 0 && collectionNote.value.trim().length < 3) { collectionError.value = 'Add a short note explaining the cash difference.'; return }
  paymentDialog.value.close()
  collectingOrder.value = null
  await advance(order, { collected_amount: amount, note: collectionNote.value.trim() })
}
onMounted(refresh)
</script>

<template>
  <section v-if="!allowed" class="lc-empty delivery-empty"><h2>Delivery access is not configured</h2><p>Your account needs the LC Delivery Person role and an enabled Driver membership for a shop.</p></section>
  <section v-else class="delivery-page">
    <header class="delivery-hero"><div><span class="eyebrow">RIDER WORKSPACE</span><h1>Hello, {{ session.full_name.split(' ')[0] }}.</h1><p>Your profile, assigned shops, and every delivery in one place.</p></div><div class="rider-avatar" aria-hidden="true">{{ session.full_name.slice(0, 1).toUpperCase() }}</div></header>

    <div class="rider-dashboard-grid">
      <aside class="rider-profile-card">
        <div class="profile-avatar"><img v-if="profile?.profile.user_image" :src="profile.profile.user_image" :alt="`${profile.profile.full_name} profile`"><span v-else aria-hidden="true">{{ session.full_name.slice(0, 1).toUpperCase() }}</span></div>
        <span class="online-badge">● Ready for delivery</span>
        <h2>{{ profile?.profile.full_name || session.full_name }}</h2>
        <p class="profile-role">Delivery partner</p>
        <dl class="profile-details">
          <div><dt>Email</dt><dd>{{ profile?.profile.email || session.user }}</dd></div>
          <div><dt>Mobile</dt><dd>{{ profile?.profile.mobile_no || 'Not added' }}</dd></div>
        </dl>
        <div class="assigned-shops"><span class="eyebrow">ASSIGNED SHOPS</span><p v-if="!profile?.shops.length">No enabled shops</p><span v-for="shop in profile?.shops || []" :key="shop.name" class="shop-chip">{{ shop.shop_name }} <small>{{ shop.status }}</small></span></div>
        <small class="profile-note">Your contact details come from your login account.</small>
      </aside>

      <div class="rider-workspace">
        <div class="rider-metrics">
          <div><span>ACTIVE</span><strong>{{ profile?.metrics.active ?? '—' }}</strong><small>to complete</small></div>
          <div><span>DELIVERED</span><strong>{{ profile?.metrics.delivered ?? '—' }}</strong><small>successful</small></div>
          <div><span>CASH HANDOVER</span><strong>{{ profile?.metrics.awaiting_handover ?? '—' }}</strong><small>waiting for shop</small></div>
          <div><span>SHOPS</span><strong>{{ profile?.metrics.shops ?? '—' }}</strong><small>connected</small></div>
        </div>
        <div v-if="profile?.cash_pending.length" class="rider-cash-summary"><div><span aria-hidden="true">₹</span><div><strong>Cash to hand over</strong><small>Give each amount to its shop owner.</small></div></div><div class="rider-cash-lines"><p v-for="cash in profile.cash_pending" :key="`${cash.shop}:${cash.currency}`"><small>{{ cash.shop_name }}</small>{{ money(cash.amount, cash.currency) }}</p></div></div>

        <div class="delivery-section-heading"><div><span class="eyebrow">YOUR ROUTE</span><h2>{{ view === 'active' ? 'Active deliveries' : 'Delivery history' }}</h2></div><button :disabled="loading || busyOrder" @click="refresh">Refresh</button></div>
        <div class="delivery-tabs" role="tablist" aria-label="Delivery lists"><button role="tab" :aria-selected="view === 'active'" @click="switchView('active')">Active <span>{{ profile?.metrics.active || 0 }}</span></button><button role="tab" :aria-selected="view === 'history'" @click="switchView('history')">History <span>{{ profile?.metrics.delivered || 0 }}</span></button></div>
        <p v-if="error" class="lc-notice" role="alert">{{ error }}</p>
        <p v-if="loading" role="status">Loading your deliveries…</p>
        <p v-else-if="!assignments.length" class="lc-empty">{{ view === 'active' ? 'No active deliveries right now.' : 'No completed deliveries yet.' }}</p>
        <div v-else class="delivery-list">
          <article v-for="order in assignments" :key="order.name" class="delivery-card" :class="{ finished: ['Delivered', 'Cancelled'].includes(order.status) }">
            <header><div><span class="eyebrow">{{ order.shop_name }} · {{ order.name }}</span><h2>{{ order.recipient }}</h2></div><span class="status-pill">{{ order.status }}</span></header>
            <div class="delivery-address"><span aria-hidden="true">⌖</span><div><strong>{{ order.address.line1 }}</strong><p>{{ order.address.city }} · {{ order.address.postal_code }}</p><a :href="`tel:${order.phone}`">Call {{ order.phone }}</a></div></div>
            <details><summary>{{ order.items.length }} product{{ order.items.length === 1 ? '' : 's' }} · {{ money(order.total, order.currency) }}</summary><ul><li v-for="(item, index) in order.items" :key="index">{{ item.quantity }} {{ item.uom }} · {{ item.name }}</li></ul></details>
            <button v-if="next[order.status]" class="delivery-action" :disabled="!!busyOrder" @click="requestAdvance(order)">{{ busyOrder === order.name ? 'Updating…' : order.status === 'Out for Delivery' ? 'Collect cash & confirm delivered' : labels[order.status] }} <span>›</span></button>
            <p v-else-if="order.status === 'Delivered'" class="delivery-complete">✓ Delivered · Cash {{ order.payment_status === 'Reconciled' ? 'handed over' : 'awaiting handover' }}{{ order.delivered_at ? ` · ${order.delivered_at}` : '' }}</p>
            <p v-else-if="order.status === 'Cancelled'" class="muted">This order was cancelled.</p>
          </article>
        </div>
        <div class="lc-pagination"><button :disabled="!start || loading || busyOrder" @click="load(-20)">Previous</button><span>Page {{ start / 20 + 1 }}</span><button :disabled="assignments.length < 20 || loading || busyOrder" @click="load(20)">Next</button></div>
      </div>
    </div>
    <dialog ref="paymentDialog" class="payment-dialog" aria-labelledby="payment-title">
      <div class="cash-symbol" aria-hidden="true">₹</div><span class="eyebrow">CASH ON DELIVERY</span><h2 id="payment-title">Confirm cash collection</h2>
      <p v-if="collectingOrder">Collect <strong>{{ money(collectingOrder.total, collectingOrder.currency) }}</strong> from {{ collectingOrder.recipient }} before completing this delivery.</p>
      <label class="cash-field">Cash received<input v-model="collectedAmount" type="number" min="0" step="0.01" inputmode="decimal" required></label>
      <p v-if="collectingOrder && collectionVariance" class="variance-note" :class="{ shortage: collectionVariance < 0 }">{{ collectionVariance < 0 ? 'Short' : 'Extra' }} by {{ money(Math.abs(collectionVariance), collectingOrder.currency) }}</p>
      <label v-if="collectionVariance" class="cash-field">Reason for difference<textarea v-model="collectionNote" maxlength="500" placeholder="Explain why the amount is different" required></textarea></label>
      <p v-if="collectionError" class="lc-notice" role="alert">{{ collectionError }}</p>
      <p class="muted">The shop owner will confirm your cash handover later. This step records the amount you received and submits the Sales Invoice.</p>
      <div class="logout-actions"><button @click="cancelCollection">Go back</button><button class="logout-confirm" @click="confirmCollection">Cash received</button></div>
    </dialog>
  </section>
</template>
