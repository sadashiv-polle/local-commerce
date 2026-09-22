<script setup>
import { onMounted, ref } from 'vue'
import { call, upload } from './api.js'
const props = defineProps({ shop: { type: String, required: true } })
const settings = ref(null), busy = ref(false), error = ref(''), message = ref('')
onMounted(async () => { try { settings.value = await call('manual_upi.settings', { shop: props.shop }) } catch (e) { error.value = e.message } })
async function save() {
  busy.value = true; error.value = ''; message.value = ''
  try { settings.value = await call('manual_upi.configure', { shop: props.shop, enabled: settings.value.enabled, upi_id: settings.value.upi_id, bank_account: settings.value.bank_account, mode_of_payment: settings.value.mode_of_payment }, true); message.value = 'UPI settings saved.' } catch (e) { error.value = e.message } finally { busy.value = false }
}
async function photo(event) {
  const file = event.target.files?.[0]; if (!file) return
  busy.value = true; error.value = ''
  try { const result = await upload('manual_upi.upload_qr', { shop: props.shop }, file); settings.value.qr = result.qr; message.value = 'QR image uploaded. Check that it matches your UPI ID.' } catch (e) { error.value = e.message } finally { busy.value = false; event.target.value = '' }
}
</script>
<template>
  <form class="lc-form payment-settings" @submit.prevent="save">
    <span class="eyebrow">PAYMENT</span><h2>UPI · scan & pay</h2>
    <p>Customers upload a screenshot after you accept their order. Verify the money in your bank account before approving payment.</p>
    <fieldset v-if="settings" :disabled="busy" class="workspace-fields">
      <label class="check-label"><input v-model="settings.enabled" type="checkbox">Enable manual UPI</label>
      <label>UPI ID<input v-model="settings.upi_id" placeholder="yourshop@bank" :required="settings.enabled" autocomplete="off"></label>
      <label>Receiving bank account<select v-model="settings.bank_account" :required="settings.enabled"><option value="">Select bank account</option><option v-for="account in settings.accounts" :key="account">{{ account }}</option></select><small>Create a Bank account for this Company in ERPNext if none is listed.</small></label>
      <label>Mode of payment<select v-model="settings.mode_of_payment" :required="settings.enabled"><option value="">Select bank payment mode</option><option v-for="mode in settings.modes" :key="mode">{{ mode }}</option></select></label>
      <img v-if="settings.qr" :src="settings.qr" class="upi-qr" alt="Shop payment QR">
      <label>Upload QR image (optional)<input type="file" accept="image/jpeg,image/png,image/webp" @change="photo"><small>JPG, PNG or WebP · up to 5 MB. UPI ID works without a QR image.</small></label>
      <button class="lc-primary">{{ busy ? 'Saving…' : 'Save UPI settings' }}</button>
    </fieldset>
    <p v-if="error" class="lc-notice" role="alert">{{ error }}</p><p v-if="message" class="success-note" role="status">{{ message }}</p>
  </form>
</template>
