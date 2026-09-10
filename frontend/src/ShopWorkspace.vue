<script setup>
import { computed, inject, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { call } from './api.js'
import Products from './Products.vue'
import Orders from './Orders.vue'
import CashReconciliation from './CashReconciliation.vue'
const session = inject('session'), route = useRoute()
const shop = ref(null), loading = ref(false), error = ref(''), saved = ref(''), saving = ref(false)
const payment = ref(null), paymentSaved = ref(''), paymentSaving = ref(false)
const tab = ref('inventory')
const canEdit = computed(() => shop.value && (session.value.platform_admin || session.value.memberships.some(m => m.shop === shop.value.name && m.membership_role === 'Owner')))
let request = 0
async function load() {
  const current = ++request
  shop.value = null; payment.value = null; loading.value = true; error.value = ''; saved.value = ''; tab.value = 'inventory'
  try {
    const result = await call('shops.get_shop', { shop: route.params.shop })
    if (current === request) {
      shop.value = result
      if (session.value.platform_admin || session.value.memberships.some(m => m.shop === result.name && m.membership_role === 'Owner')) payment.value = await call('orders.payment_options', { shop: result.name })
    }
  } catch (e) { if (current === request) error.value = e.message }
  finally { if (current === request) loading.value = false }
}
async function savePayment() {
  paymentSaving.value = true; error.value = ''; paymentSaved.value = ''
  try {
    payment.value = await call('orders.configure_cod', { shop: shop.value.name, enabled: payment.value.enabled, cash_account: payment.value.cash_account || '', mode_of_payment: payment.value.mode_of_payment || '' }, true)
    paymentSaved.value = 'Cash on Delivery settings saved.'
  } catch (e) { error.value = e.message }
  finally { paymentSaving.value = false }
}
async function save() {
  saving.value = true; error.value = ''; saved.value = ''
  const current = request
  try {
    const s = shop.value
    const result = await call('shops.update_shop', { shop: s.name, shop_name: s.shop_name, status: s.status, description: s.description || '' }, true)
    if (current === request) { shop.value = result; saved.value = 'Shop settings saved.' }
  } catch (e) { if (current === request) error.value = e.message }
  finally { saving.value = false }
}
watch(() => route.params.shop, load, { immediate: true })
</script>

<template>
  <section class="owner-page">
    <aside class="owner-sidebar">
      <RouterLink class="workspace-back" to="/shop">← All shops</RouterLink>
      <span class="eyebrow">SHOP WORKSPACE</span>
      <strong>{{ shop?.shop_name || 'Your shop' }}</strong>
      <p>Everything you need to manage this shop, in one place.</p>
      <nav v-if="shop" class="workspace-nav" aria-label="Shop sections">
        <button :class="{ 'sidebar-active': tab === 'orders' }" :aria-current="tab === 'orders' ? 'page' : undefined" @click="tab = 'orders'">Orders</button>
        <button :class="{ 'sidebar-active': tab === 'cash' }" :aria-current="tab === 'cash' ? 'page' : undefined" @click="tab = 'cash'">Cash handover</button>
        <button :class="{ 'sidebar-active': tab === 'inventory' }" :aria-current="tab === 'inventory' ? 'page' : undefined" @click="tab = 'inventory'">Products &amp; stock</button>
        <button :class="{ 'sidebar-active': tab === 'settings' }" :aria-current="tab === 'settings' ? 'page' : undefined" @click="tab = 'settings'">Shop settings</button>
      </nav>
      <div class="sidebar-bottom"><span class="status-pill">{{ canEdit ? 'Owner access' : 'Read-only access' }}</span><small>{{ session.user }}</small></div>
    </aside>
    <div class="owner-content">
      <p v-if="loading" role="status">Opening your shop…</p>
      <div v-if="error" class="lc-notice" role="alert">{{ error }} <button v-if="!shop" @click="load">Retry</button></div>
      <template v-if="shop">
        <header class="workspace-heading"><div><span class="eyebrow">YOUR SHOP</span><h1>{{ shop.shop_name }}</h1><p class="muted">{{ shop.company }}</p></div><span class="status-pill">{{ shop.status }}</span></header>
        <Orders v-if="tab === 'orders'" :shop="shop.name" :editable="canEdit" />
        <CashReconciliation v-if="tab === 'cash'" :shop="shop.name" :editable="canEdit" />
        <Products v-show="tab === 'inventory'" :key="shop.name" :shop="shop.name" :editable="canEdit" />
        <form v-show="tab === 'settings'" class="lc-form" @submit.prevent="save">
          <h2>Shop settings</h2><p class="muted">Keep your shop details and availability up to date.</p>
          <fieldset :disabled="!canEdit || saving" class="workspace-fields">
            <label>Name<input v-model="shop.shop_name" required></label>
            <label>Company<input :value="shop.company" disabled></label>
            <label>Status<select v-model="shop.status"><option>Draft</option><option>Active</option><option>Temporarily Closed</option><option>Disabled</option></select></label>
            <label>Description<textarea v-model="shop.description"></textarea></label>
            <button v-if="canEdit" class="lc-primary">{{ saving ? 'Saving…' : 'Save settings' }}</button>
          </fieldset>
          <p v-if="saved" role="status">{{ saved }}</p>
        </form>
        <form v-if="tab === 'settings' && canEdit && payment" class="lc-form payment-settings" @submit.prevent="savePayment">
          <span class="eyebrow">PAYMENT</span><h2>Cash on Delivery</h2><p class="muted">The rider records the amount at delivery. The Payment Entry is created after the shop confirms the cash handover.</p>
          <fieldset :disabled="paymentSaving" class="workspace-fields">
            <label class="check-label"><input v-model="payment.enabled" type="checkbox"><span>Enable Cash on Delivery<small>Customers can place an order and pay the rider at delivery.</small></span></label>
            <label>Cash collection account<select v-model="payment.cash_account" :required="payment.enabled"><option value="">Select cash account</option><option v-for="account in payment.cash_accounts" :key="account" :value="account">{{ account }}</option></select></label>
            <label>Mode of payment<select v-model="payment.mode_of_payment" :required="payment.enabled"><option value="">Select mode</option><option v-for="mode in payment.modes" :key="mode" :value="mode">{{ mode }}</option></select></label>
            <button class="lc-primary">{{ paymentSaving ? 'Saving…' : 'Save payment settings' }}</button>
          </fieldset>
          <p v-if="paymentSaved" class="success-note" role="status">{{ paymentSaved }}</p>
        </form>
      </template>
    </div>
  </section>
</template>
