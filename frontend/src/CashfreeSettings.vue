<script setup>
import { onMounted, ref } from 'vue'
import { call } from './api.js'
const data = ref(null), busy = ref(false), error = ref(''), message = ref(''), details = ref({}), credits = ref({})
const profile = ref({ name: '', environment: 'sandbox', enabled: false, client_id: '', client_secret: '' })
async function load() {
  data.value = await call('cashfree.settings')
  for (const shop of data.value.shops) shop.cashfree_settlement_mode ||= 'Easy Split'
}
onMounted(async () => { try { await load() } catch (e) { error.value = e.message } })
async function run(action) {
  busy.value = true; error.value = ''; message.value = ''
  try { await action(); await load(); message.value = 'Updated successfully.' }
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
  values.cashfree_auto_reconcile = Number(!!values.cashfree_auto_reconcile)
  return run(() => call('cashfree.save_shop', { shop: shop.name, values }, true))
}
async function prepareCredit(order) {
  await run(async () => {
    const result = await call('cashfree.prepare_credit', { order: order.name }, true)
    details.value[order.name] = { credit_note: result.credit_note }
  })
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
              <label>Receive payments into<select v-model="shop.cashfree_settlement_mode"><option value="Direct merchant">Main merchant account — my own shop</option><option value="Easy Split">Vendor account — Easy Split</option></select></label>
              <label v-if="shop.cashfree_settlement_mode === 'Easy Split'">Easy Split vendor ID<input v-model="shop.cashfree_vendor_id" placeholder="Approved vendor ID from Cashfree"></label>
              <label v-if="shop.cashfree_settlement_mode === 'Easy Split'">Commission type<select v-model="shop.cashfree_commission_type"><option>Percentage</option><option>Fixed</option></select></label>
              <label v-if="shop.cashfree_settlement_mode === 'Easy Split'">Commission<input v-model.number="shop.cashfree_commission" type="number" min="0" step="0.01"></label>
              <label>Cashfree clearing account<select v-model="shop.cashfree_clearing_account"><option value="">Select asset account</option><option v-for="account in accounts(shop, 'Asset')" :key="account.name">{{ account.name }}</option></select></label>
              <label v-if="shop.cashfree_settlement_mode === 'Easy Split'">Commission expense account<select v-model="shop.cashfree_commission_account"><option value="">Select expense account</option><option v-for="account in accounts(shop, 'Expense')" :key="account.name">{{ account.name }}</option></select></label>
              <label>Settlement receiving bank<select v-model="shop.cashfree_bank_account"><option value="">Select actual bank account</option><option v-for="account in accounts(shop, 'Asset').filter(a => a.name !== shop.cashfree_clearing_account)" :key="account.name">{{ account.name }}</option></select></label>
              <label>Gateway fee expense<select v-model="shop.cashfree_fee_account"><option value="">Select expense account</option><option v-for="account in accounts(shop, 'Expense')" :key="account.name">{{ account.name }}</option></select></label>
              <label>Gateway fee tax expense<select v-model="shop.cashfree_fee_tax_account"><option value="">Select expense account</option><option v-for="account in accounts(shop, 'Expense')" :key="account.name">{{ account.name }}</option></select></label>
              <label>Mode of Payment<select v-model="shop.cashfree_mode_of_payment"><option value="">Select bank payment mode</option><option v-for="mode in data.modes" :key="mode">{{ mode }}</option></select></label>
            </div>
            <p v-if="shop.cashfree_settlement_mode === 'Easy Split'">Commission applies to the full order total, including delivery and taxes. The remainder goes to this vendor. Changes apply to new orders only. Complete vendor onboarding and KYC in Cashfree before enabling.</p>
            <p v-else>Payments use the merchant account linked to the selected gateway profile. No vendor ID or marketplace commission is needed. Cashfree fees still apply in production. Changes apply to new orders only.</p>
            <label class="check-label"><input v-model="shop.cashfree_auto_reconcile" type="checkbox">Automatically reconcile paid orders and bank settlements every hour</label><button class="lc-primary">Save shop payment settings</button>
            <button v-if="shop.cashfree_settlement_mode === 'Easy Split'" type="button" @click="run(async () => { details[shop.name] = await call('cashfree.vendor_status', { shop: shop.name }, true) })">Check vendor status</button><pre v-if="details[shop.name] && shop.cashfree_settlement_mode === 'Easy Split'">{{ details[shop.name] }}</pre>
          </fieldset>
        </form>
      </section>
      <section class="admin-card">
        <h2>Recent Cashfree payments</h2>
        <p>Verified settlements create a bank journal for the order amount and provider charges. Fee tax is expensed; no input tax credit is claimed automatically. Match the journal against your bank statement in ERPNext. Existing manual postings must be reviewed before enabling automatic reconciliation.</p>
        <article v-for="order in data.orders" :key="order.name" class="order-rating">
          <RouterLink :to="{ path: '/admin/orders', query: { shop: order.shop } }">{{ order.gateway_order_id }}</RouterLink>
          <p>{{ order.payment_status }} · {{ order.status }}</p><p v-if="order.gateway_accounting_error">{{ order.gateway_accounting_error }}</p><p v-if="order.gateway_settlement_error">{{ order.gateway_settlement_error }}</p>
          <button :disabled="busy" @click="run(() => call('cashfree.verify', { order: order.name }, true))">Retry verification</button>
          <button :disabled="busy" @click="run(async () => { details[order.name] = await call('cashfree.settlements', { order: order.name }, true) })">Refunds & accounting entries</button>
          <button :disabled="busy" @click="run(async () => { details[order.name] = await call('cashfree.reconcile_settlement', { order: order.name }, true) })">Reconcile bank settlement</button>
          <button v-if="order.sales_invoice" :disabled="busy" @click="prepareCredit(order)">Prepare partial refund credit note</button><p v-if="details[order.name]?.credit_note"><a :href="'/app/sales-invoice/' + encodeURIComponent(details[order.name].credit_note)" target="_blank" rel="noopener">Edit credit note in ERPNext ↗</a> — choose the returned items and charges, then submit. This does not put goods back in stock.</p>
          <div v-for="refund in details[order.name]?.refunds || []" :key="refund.cf_refund_id">
            <template v-if="refund.refund_status === 'SUCCESS'">
              <p>Refund {{ refund.cf_refund_id }} · ₹{{ refund.refund_amount }}</p>
              <label>Submitted credit note<input v-model="credits[refund.cf_refund_id]" placeholder="ACC-SINV-…"></label>
              <button :disabled="busy || !credits[refund.cf_refund_id]" @click="run(() => call('cashfree.link_refund_credit', { order: order.name, refund_id: refund.cf_refund_id, credit_note: credits[refund.cf_refund_id] }, true))">Link credit note</button>
              <small>After linking, select Retry verification to post the refund payment.</small>
            </template>
          </div><pre v-if="details[order.name]">{{ details[order.name] }}</pre>
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
