<script setup>
import { ref, watch } from 'vue'
import { call } from './api.js'
const props = defineProps({ shop: { type: String, required: true } })
const emit = defineEmits(['changed'])
const data = ref(null), busy = ref(false), error = ref(''), message = ref('')
const blank = () => ({ mode: 'new', bank: '', holder: '', number: '', confirm_number: '', ifsc: '' })
const form = ref(blank()), usage = ref('store')
let generation = 0
async function load() {
  const request = ++generation
  try { const result = await call('admin.shop_banks', { shop: props.shop }); if (request === generation) data.value = result }
  catch (e) { if (request === generation) error.value = e.message }
}
watch(() => props.shop, () => { data.value = null; error.value = ''; message.value = ''; form.value = blank(); load() }, { immediate: true })
async function save(details, target) {
  const shop = props.shop
  busy.value = true; error.value = ''; message.value = ''
  try {
    await call('admin.save_shop_bank', { shop, details, usage: target }, true)
    if (shop !== props.shop) return
    form.value = blank()
    message.value = target === 'store' ? 'Bank account saved. Current payment accounts are unchanged.' : 'Bank selection updated. Previous bank records are preserved.'
    await load(); emit('changed')
  } catch (e) { if (shop === props.shop) error.value = e.message }
  finally { busy.value = false }
}
</script>
<template>
  <section class="bank-settings">
    <h2>Shop bank accounts</h2>
    <p>Add accounts now or later, and choose which account is used for Manual UPI or Cashfree settlement accounting. Only platform admins can make these changes.</p>
    <p v-if="error" class="lc-notice" role="alert">{{ error }}</p>
    <p v-if="message" role="status">{{ message }}</p>
    <template v-if="data">
      <p><strong>Company:</strong> {{ data.company }}</p>
      <p>UPI ledger: {{ data.upi_ledger || 'Not selected' }}<br>Settlement ledger: {{ data.settlement_ledger || 'Not selected' }}</p>
      <p v-if="!data.accounts.length">No Bank Account records yet. Add your first account below.</p>
      <ul class="bank-settings-list">
        <li v-for="bank in data.accounts" :key="bank.name">
          <strong>{{ bank.bank }} · ending {{ bank.last_four }}</strong>
          <small>{{ bank.name }}</small>
          <span v-if="bank.account === data.upi_ledger">Selected for UPI</span>
          <span v-if="bank.account === data.settlement_ledger">Selected for settlement accounting</span>
          <div class="bank-settings-actions">
            <button type="button" :disabled="busy || bank.account === data.upi_ledger" @click="save({ mode: 'existing', existing: bank.name }, 'upi')">Use for UPI</button>
            <button type="button" :disabled="busy || bank.account === data.settlement_ledger" @click="save({ mode: 'existing', existing: bank.name }, 'settlement')">Use for settlement</button>
          </div>
        </li>
      </ul>
      <form @submit.prevent="save(form, usage)">
        <h3>Add another bank account</h3>
        <fieldset :disabled="busy">
          <div class="form-columns">
            <label>Bank name<input v-model="form.bank" list="existing-shop-banks" required maxlength="80"><datalist id="existing-shop-banks"><option v-for="bank in data.banks" :key="bank" :value="bank" /></datalist></label>
            <label>Account holder name<input v-model="form.holder" required maxlength="80" autocomplete="off"></label>
            <label>Account number<input v-model="form.number" required inputmode="numeric" pattern="[0-9]{6,34}" maxlength="34" autocomplete="off"></label>
            <label>Confirm account number<input v-model="form.confirm_number" required inputmode="numeric" pattern="[0-9]{6,34}" maxlength="34" autocomplete="off"></label>
            <label>IFSC<input v-model="form.ifsc" required pattern="[A-Za-z]{4}0[A-Za-z0-9]{6}" maxlength="11" autocapitalize="characters" spellcheck="false"></label>
            <label>Use this account for<select v-model="usage"><option value="store">Save only — choose later</option><option value="upi">Manual UPI</option><option value="settlement">Cashfree settlement accounting</option><option value="both">UPI and settlement accounting</option></select></label>
          </div>
          <button class="lc-primary">{{ busy ? 'Saving…' : 'Save bank account' }}</button>
        </fieldset>
      </form>
      <p>Changing the bank ledger does not change the UPI ID/QR or Cashfree vendor payout destination. Update those separately before receiving payments. Posted accounting entries and Company defaults are not edited. Pending Cashfree settlement reconciliation uses the selected bank ledger.</p>
    </template>
  </section>
</template>
<style scoped>
.bank-settings { border: 1px solid #dce6dc; border-radius: 18px; padding: clamp(16px,3vw,28px); margin-block: 24px; background: white; }
.bank-settings-list { list-style: none; padding: 0; display: grid; gap: 12px; }
.bank-settings-list li { display: grid; gap: 8px; padding: 16px; border: 1px solid #dce6dc; border-radius: 12px; overflow-wrap: anywhere; }
.bank-settings-actions { display: flex; gap: 10px; flex-wrap: wrap; }
fieldset { border: 0; padding: 0; min-width: 0; }
label { display: grid; gap: 6px; }
.bank-settings p { overflow-wrap: anywhere; }
</style>
