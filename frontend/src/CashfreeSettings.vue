<script setup>
import { onMounted, ref } from 'vue'
import { call } from './api.js'
const data = ref(null), busy = ref(false), error = ref(''), message = ref(''), details = ref({})
const profile = ref({ name: '', environment: 'sandbox', enabled: false, client_id: '', client_secret: '' })
async function load() { data.value = await call('cashfree.settings') }
onMounted(async () => { try { await load() } catch (e) { error.value = e.message } })
async function run(action) {
  busy.value = true; error.value = ''; message.value = ''
  try { await action(); await load(); message.value = 'Saved successfully.' }
  catch (e) { error.value = e.message }
  finally { busy.value = false }
}
function edit(row) { profile.value = { ...row, enabled: !!row.enabled, client_id: '', client_secret: '' } }
async function saveProfile() {
  await run(() => call('cashfree.save_profile', { ...profile.value, enabled: Number(profile.value.enabled) }, true))
  profile.value.client_secret = ''; profile.value.client_id = ''
}
function saveShop(shop) {
  const values = Object.fromEntries(Object.entries(shop).filter(([key]) => key.startsWith('cashfree_')))
  values.cashfree_enabled = Number(!!values.cashfree_enabled)
  return run(() => call('cashfree.save_shop', { shop: shop.name, values }, true))
}
function accounts(shop, type) { return data.value.accounts.filter(a => a.company === shop.company && a.root_type === type && (type !== 'Asset' || a.account_type === 'Bank')) }
</script>
<template>
  <div class="cashfree-settings">
    <p v-if="error" class="lc-notice" role="alert">{{ error }}</p>
    <p v-if="message" role="status">{{ message }}</p>
    <template v-if="data">
      <section class="admin-card">
        <h2>Cashfree gateway</h2>
        <p>Use a separate profile for Sandbox and Production. Keep old profiles for payment history. Disabling a profile stops new checkout sessions; existing payments can still be verified.</p>
        <p><strong>Webhook URL</strong><br><code class="gateway-url">{{ data.webhook_url }}</code></p>
        <div class="button-row"><button v-for="row in data.profiles" :key="row.name" @click="edit(row)">{{ row.name }} · {{ row.environment }} · {{ row.enabled ? 'Enabled' : 'Disabled' }}</button></div>
        <form @submit.prevent="saveProfile">
          <fieldset :disabled="busy">
            <div class="form-columns">
              <label>Profile name<input v-model="profile.name" required maxlength="80" placeholder="Cashfree Sandbox"></label>
              <label>Environment<select v-model="profile.environment"><option value="sandbox">Sandbox — test payments</option><option value="production">Production — real payments</option></select></label>
              <label>Client ID<input v-model="profile.client_id" autocomplete="off" placeholder="Leave blank to retain existing ID"></label>
              <label>Client secret<input v-model="profile.client_secret" type="password" autocomplete="new-password" placeholder="Leave blank to retain existing secret"></label>
            </div>
            <label class="check-label"><input v-model="profile.enabled" type="checkbox">Enable profile</label>
            <button class="lc-primary">Save gateway</button>
          </fieldset>
        </form>
      </section>
      <section v-for="shop in data.shops" :key="shop.name" class="admin-card">
        <h3>{{ shop.shop_name }}</h3><p>{{ shop.company }}</p>
        <form @submit.prevent="saveShop(shop)">
          <fieldset :disabled="busy">
            <label class="check-label"><input v-model="shop.cashfree_enabled" type="checkbox">Offer Cashfree at checkout</label>
            <div class="form-columns">
              <label>Gateway profile<select v-model="shop.cashfree_gateway"><option value="">Select profile</option><option v-for="row in data.profiles" :key="row.name">{{ row.name }}</option></select></label>
              <label>Easy Split vendor ID<input v-model="shop.cashfree_vendor_id" placeholder="Approved vendor ID from Cashfree"></label>
              <label>Commission type<select v-model="shop.cashfree_commission_type"><option>Percentage</option><option>Fixed</option></select></label>
              <label>Commission<input v-model.number="shop.cashfree_commission" type="number" min="0" step="0.01"></label>
              <label>Cashfree clearing account<select v-model="shop.cashfree_clearing_account"><option value="">Select asset account</option><option v-for="account in accounts(shop, 'Asset')" :key="account.name">{{ account.name }}</option></select></label>
              <label>Commission expense account<select v-model="shop.cashfree_commission_account"><option value="">Select expense account</option><option v-for="account in accounts(shop, 'Expense')" :key="account.name">{{ account.name }}</option></select></label>
              <label>Mode of Payment<select v-model="shop.cashfree_mode_of_payment"><option value="">Select bank payment mode</option><option v-for="mode in data.modes" :key="mode">{{ mode }}</option></select></label>
            </div>
            <p>Commission applies to the full order total, including delivery and taxes. The remainder goes to this vendor. Changes apply to new orders only. Complete vendor onboarding and KYC in Cashfree before enabling.</p>
            <button class="lc-primary">Save shop payment settings</button>
            <button type="button" @click="run(async () => { details[shop.name] = await call('cashfree.vendor_status', { shop: shop.name }, true) })">Check vendor status</button><pre v-if="details[shop.name]">{{ details[shop.name] }}</pre>
          </fieldset>
        </form>
      </section>
      <section class="admin-card">
        <h2>Recent Cashfree payments</h2>
        <p>Cashfree settlement does not mean a bank deposit has been reconciled. Match deposits and gateway fees against the clearing account in ERPNext.</p>
        <article v-for="order in data.orders" :key="order.name" class="order-rating">
          <RouterLink :to="{ path: '/admin/orders', query: { shop: order.shop } }">{{ order.gateway_order_id }}</RouterLink>
          <p>{{ order.payment_status }} · {{ order.status }}</p><p v-if="order.gateway_accounting_error">{{ order.gateway_accounting_error }}</p>
          <button :disabled="busy" @click="run(() => call('cashfree.verify', { order: order.name }, true))">Retry verification</button>
          <button :disabled="busy" @click="run(async () => { details[order.name] = await call('cashfree.settlements', { order: order.name }, true) })">View split and settlement</button><pre v-if="details[order.name]">{{ details[order.name] }}</pre>
        </article>
      </section>
    </template>
  </div>
</template>
<style scoped>
.cashfree-settings { display: grid; gap: 20px; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; }
.gateway-url { overflow-wrap: anywhere; }
fieldset { border: 0; padding: 0; min-width: 0; }
label { display: block; }
</style>
