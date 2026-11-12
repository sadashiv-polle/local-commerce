<script setup>
import { computed, ref, watch } from 'vue'
import { call } from './api.js'
const props = defineProps({ profiles: { type: Array, required: true } })
const profile = ref(''), vendor = ref(''), busy = ref(false), error = ref(''), result = ref(null), history = ref([])
const startDate = ref(''), endDate = ref('')
const mode = ref('create'), destination = ref('bank'), prepared = ref(null)
const form = ref({ name: '', email: '', phone: '', verify_account: true, dashboard_access: false, schedule_option: '' })
const bank = ref({ account_number: '', account_holder: '', ifsc: '' }), upi = ref({ vpa: '', account_holder: '' })
const kyc = ref({ account_type: '', business_type: '', pan: '', gst: '', cin: '' })
const transfer = ref({ transfer_type: 'ON_DEMAND', transfer_from: 'VENDOR', transfer_amount: '', remark: '' })
const environment = computed(() => props.profiles.find(row => row.name === profile.value)?.environment || '')
watch([profile, vendor], () => { result.value = null; history.value = []; prepared.value = null })
async function run(fn) {
  if (busy.value) return
  busy.value = true; error.value = ''
  try { await fn() } catch (e) { error.value = e.message } finally { busy.value = false }
}
const args = () => ({ profile: profile.value, vendor: vendor.value.trim() })
async function inspect(view) { await run(async () => { result.value = await call('easy_split.inspect', { ...args(), view }, true) }) }
async function save() {
  const values = { ...form.value }
  const clean = obj => Object.fromEntries(Object.entries(obj).filter(([, value]) => value !== ''))
  if (destination.value === 'bank') values.bank = clean(bank.value)
  if (destination.value === 'upi') values.upi = clean(upi.value)
  values.kyc_details = clean(kyc.value)
  if (!window.confirm(`${mode.value === 'create' ? 'Create' : 'Update'} vendor ${vendor.value} in ${environment.value}? Bank/UPI changes affect Cashfree payouts.`)) return
  await run(async () => { result.value = await call('easy_split.save_vendor', { ...args(), values, mode: mode.value }, true) })
}
async function reviewTransfer() {
  await run(async () => { prepared.value = await call('easy_split.prepare_transfer', { ...args(), values: { ...transfer.value } }, true) })
}
async function confirmTransfer() {
  await run(async () => {
    result.value = await call('easy_split.execute_transfer', { name: prepared.value.name }, true)
    prepared.value = null
    history.value = await call('easy_split.activity', args(), true)
  })
}
</script>
<template>
  <section class="admin-card easy-split">
    <h2>Easy Split · vendor management</h2>
    <p>Create and update Cashfree vendors here. Select the same gateway profile used by the shop. Afterwards, enter the vendor ID in the shop payment settings and save it.</p>
    <a href="https://merchant.cashfree.com" target="_blank" rel="noopener">Open Cashfree dashboard ↗</a>
    <p v-if="error" class="lc-notice" role="alert">{{ error }}</p>
    <fieldset :disabled="busy || !!prepared">
      <div class="form-columns">
        <label>Gateway profile<select v-model="profile"><option value="">Choose profile</option><option v-for="row in profiles" :key="row.name" :value="row.name">{{ row.name }} · {{ row.environment }}</option></select></label>
        <label>Vendor ID<input v-model="vendor" maxlength="100" pattern="[A-Za-z0-9_]+" placeholder="OMIKART"></label>
      </div>
    </fieldset>
    <p v-if="environment"><strong>{{ environment === 'production' ? 'Production — real funds' : 'Sandbox — test environment' }}</strong></p>
    <template v-if="profile && vendor.trim()">
      <fieldset :disabled="busy || !!prepared">
        <div class="button-row"><button type="button" @click="inspect('details')">Vendor details</button><button type="button" @click="inspect('documents')">KYC document status</button><button type="button" @click="inspect('balance')">Check balances</button><button type="button" @click="run(async () => { history = await call('easy_split.activity', args(), true) })">Transfer history</button></div>
      </fieldset>
      <details>
        <summary>Vendor reconciliation</summary>
        <form @submit.prevent="run(async () => { result = await call('easy_split.reconciliation', { ...args(), start_date: startDate, end_date: endDate }, true) })"><fieldset :disabled="busy"><div class="form-columns"><label>From (UTC)<input v-model="startDate" type="date" required></label><label>To (UTC)<input v-model="endDate" type="date" required></label></div><button>Fetch reconciliation</button><p>Up to 25 records per request. Use Cashfree for full report exports.</p></fieldset></form>
      </details>
      <details>
        <summary>Add or edit vendor</summary>
        <form @submit.prevent="save">
          <fieldset :disabled="busy || !!prepared">
            <label>Action<select v-model="mode"><option value="create">Create new vendor</option><option value="update">Update existing vendor</option></select></label>
            <p v-if="mode === 'update'">Enter only the contact, bank or KYC fields you want to change. Blank text fields are left unchanged. Verification and dashboard access use the checkboxes below.</p>
            <div class="form-columns">
              <label>Vendor name<input v-model="form.name" :required="mode === 'create'" maxlength="140"></label>
              <label>Email<input v-model="form.email" type="email" :required="mode === 'create'"></label>
              <label>Phone<input v-model="form.phone" type="tel" :required="mode === 'create'"></label>
              <label>Settlement schedule ID<input v-model="form.schedule_option" type="number" min="1" step="1"><small>Leave blank to keep the existing/default cycle. Use the schedule ID agreed with Cashfree.</small></label>
            </div>
            <label class="check-label"><input v-model="form.verify_account" type="checkbox">Verify payout account</label>
            <label class="check-label"><input v-model="form.dashboard_access" type="checkbox">Give vendor dashboard access</label>
            <label>Payout destination<select v-model="destination"><option value="bank">Bank account</option><option value="upi">UPI</option><option v-if="mode === 'update'" value="unchanged">Keep existing destination</option></select></label>
            <div v-if="destination === 'bank'" class="form-columns"><label>Account holder<input v-model="bank.account_holder"></label><label>Account number<input v-model="bank.account_number" inputmode="numeric" autocomplete="off"></label><label>IFSC<input v-model="bank.ifsc" maxlength="11"></label></div>
            <div v-if="destination === 'upi'" class="form-columns"><label>Account holder<input v-model="upi.account_holder"></label><label>UPI ID<input v-model="upi.vpa"></label></div>
            <h3>KYC details</h3>
            <div class="form-columns"><label v-for="field in [['account_type','Account type'],['business_type','Business type'],['pan','PAN'],['gst','GSTIN'],['cin','CIN']]" :key="field[0]">{{ field[1] }}<input v-model="kyc[field[0]]" maxlength="140"></label></div>
            <p>Use the account and business types accepted by Cashfree. Upload supporting KYC documents in the Cashfree dashboard; check their status here. Updating a vendor does not change your shop’s ERP bank ledger.</p>
            <button class="lc-primary">{{ mode === 'create' ? 'Create vendor' : 'Save vendor changes' }}</button>
          </fieldset>
        </form>
      </details>
      <details>
        <summary>On-demand settlement &amp; balance adjustment</summary>
        <p>These actions change Cashfree balances. They do not create ERP accounting entries. Reconcile them separately. Cashfree fees and account eligibility apply.</p>
        <form @submit.prevent="reviewTransfer">
          <fieldset :disabled="busy || !!prepared">
            <label>Action<select v-model="transfer.transfer_type"><option value="ON_DEMAND">On-demand settlement</option><option value="ADJUSTMENT">Balance adjustment</option></select></label>
            <label>Cashfree transfer_from<select v-model="transfer.transfer_from"><option value="VENDOR">VENDOR</option><option value="MERCHANT">MERCHANT</option></select><small>Confirm the transfer direction with your Cashfree configuration before submitting.</small></label>
            <label>Amount (INR)<input v-model="transfer.transfer_amount" type="number" min="0.01" step="0.01" required></label>
            <label>Reason / reference<input v-model="transfer.remark" maxlength="140" required></label>
            <button type="submit">Review transfer</button>
          </fieldset>
        </form>
        <section v-if="prepared" class="lc-notice" role="region" aria-label="Review transfer">
          <h3>Confirm {{ prepared.environment }} transfer</h3>
          <p>Vendor: {{ vendor }} · Profile: {{ profile }}</p>
          <pre>{{ prepared.payload }}</pre>
          <p>Reference: {{ prepared.name }}. An accepted request is not proof of bank settlement.</p>
          <button type="button" :disabled="busy" @click="confirmTransfer">Confirm and submit to Cashfree</button>
          <button type="button" :disabled="busy" @click="prepared = null">Cancel</button>
        </section>
      </details>
      <section v-if="result"><h3>Cashfree response</h3><pre>{{ result }}</pre></section>
      <section v-if="history.length"><h3>Recent app transfer requests</h3><article v-for="row in history" :key="row.name"><strong>{{ row.status }} · {{ row.creation }}</strong><p>{{ row.name }} · {{ row.owner }}</p><pre>{{ row.payload }}</pre><details v-if="row.response"><summary>Provider response</summary><pre>{{ row.response }}</pre></details><p v-if="row.status === 'Unconfirmed'">Check this request in Cashfree before making another transfer.</p></article></section>
    </template>
  </section>
</template>
<style scoped>
fieldset { border: 0; padding: 0; min-width: 0; }
details { margin-top: 18px; }
summary { cursor: pointer; font-weight: 700; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; }
article { border-top: 1px solid #dce6dc; padding: 12px 0; }
</style>
