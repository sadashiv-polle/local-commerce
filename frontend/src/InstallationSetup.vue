<script setup>
import { onMounted, ref } from 'vue'
import { call } from './api.js'
const data = ref(null), busy = ref(false), error = ref(''), confirmed = ref(false), shop = ref('')
async function load() {
  busy.value = true; error.value = ''
  try { data.value = await call('installation_setup.status') }
  catch (e) { error.value = e.message }
  finally { busy.value = false }
}
async function initialize() {
  busy.value = true; error.value = ''
  try {
    data.value = await call('installation_setup.initialize', {
      confirm_company: confirmed.value ? data.value.company_confirmation : '', confirm_shop: shop.value,
    }, true)
  } catch (e) { error.value = e.message }
  finally { busy.value = false }
}
onMounted(load)
</script>
<template>
  <section class="setup-panel" :aria-busy="busy">
    <header><div><h2>Local dot Setup</h2><p>Your legal business, marketplace and own shop, in one place.</p></div><button :disabled="busy" @click="load">Refresh checklist</button></header>
    <p v-if="error" class="lc-notice" role="alert">{{ error }}</p>
    <p v-if="busy" role="status">Checking your setup…</p>
    <template v-if="data">
      <p>Shiv Tech Works operates Local dot. Daily Basket is your own shop. Third-party shops keep their separate Companies. Basic setup leaves your shop in Draft with ordering and payments off.</p>
      <p v-if="data.message" class="lc-notice">{{ data.message }}</p>
      <div v-if="!data.initialized" class="setup-start lc-form">
        <p>Create the missing basic structure. Existing linked settings are preserved. No GSTIN, bank details or payment credentials are generated.</p>
        <label v-if="data.company_confirmation"><input v-model="confirmed" type="checkbox"> I have checked that the existing {{ data.company_confirmation }} Company is the intended legal business.</label>
        <label v-if="data.shop_choices.length">Confirm the existing Daily Basket shop<select v-model="shop"><option value="">Select the intended owned shop</option><option v-for="row in data.shop_choices" :key="row.name" :value="row.name">{{ row.shop_name }} · {{ row.company }} · {{ row.business_model }} · {{ row.name }}</option></select></label>
        <button :disabled="busy || (!!data.company_confirmation && !confirmed) || (!!data.shop_choices.length && !shop)" @click="initialize">Create or complete basic setup</button>
      </div>
      <ol class="setup-checks">
        <li v-for="(item, index) in data.checks" :key="item.label">
          <span class="setup-number">{{ index + 1 }}</span><div><h3>{{ item.label }}</h3><p>{{ item.detail }}</p><a v-if="item.link.startsWith('/app/')" :href="item.link">Open settings →</a><RouterLink v-else :to="item.link">Open settings →</RouterLink></div>
          <span class="setup-status" :class="{ complete: item.complete }">{{ item.complete ? 'Configured' : 'Pending configuration' }}</span>
        </li>
      </ol>
      <p>“Configured” reports saved setup, not verification by your bank, Cashfree or tax adviser. Complete the remaining settings before accepting live orders. Easy Split and commission apply to third-party shops; they are not required for your own shop.</p>
    </template>
  </section>
</template>
<style scoped>
.setup-panel { background: white; border: 1px solid #dce6dc; border-radius: 20px; padding: clamp(16px, 3vw, 32px); }
.setup-panel header { display: flex; justify-content: space-between; align-items: start; gap: 16px; flex-wrap: wrap; }
.setup-panel h2, .setup-panel h3 { margin: 0 0 8px; }
.setup-panel p { line-height: 1.6; color: #52675c; }
.setup-start { padding: 16px; background: #f2f7ef; border-radius: 12px; }
.setup-checks { list-style: none; padding: 0; }
.setup-checks li { display: grid; grid-template-columns: 32px 1fr auto; gap: 16px; padding: 22px 0; border-bottom: 1px solid #e4ebe4; }
.setup-number { color: #176449; font-weight: 700; }
.setup-status { align-self: start; background: #fff3dc; color: #755019; padding: 6px 10px; border-radius: 8px; font-size: .8rem; }
.setup-status.complete { background: #e7f4e9; color: #176449; }
@media (max-width: 600px) { .setup-checks li { grid-template-columns: 24px 1fr; gap: 8px; } .setup-status { grid-column: 2; justify-self: start; } }
</style>
