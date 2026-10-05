<script setup>
import { ref } from 'vue'
import { call } from './api.js'
const props = defineProps({ shop: { type: String, required: true } })
const result = ref(null), busy = ref(false), error = ref('')
async function runCheck() {
  busy.value = true; error.value = ''
  try { result.value = await call('shops.readiness', { shop: props.shop }) }
  catch (e) { error.value = e.message } finally { busy.value = false }
}
function target(check) {
  return check.target === 'people' ? { path: '/admin/people', query: { shop: props.shop } }
    : { name: 'shop-workspace', params: { shop: props.shop }, query: { tab: check.target } }
}
</script>
<template>
  <section class="shop-readiness">
    <header><div><h2>Shop readiness</h2><p>Check setup before taking orders. This does not replace a test checkout.</p></div><button type="button" :disabled="busy" @click="runCheck">{{ busy ? 'Checking…' : result ? 'Check again' : 'Check setup' }}</button></header>
    <p v-if="error" class="lc-notice" role="alert">{{ error }}</p>
    <template v-if="result"><p role="status"><strong>{{ result.passed }} / {{ result.total }} checks passed</strong></p><ul><li v-for="check in result.checks" :key="check.label"><span :class="{ passed: check.ready }">{{ check.ready ? '✓ Passed' : 'Review' }}</span><div><strong>{{ check.label }}</strong><p>{{ check.detail }}</p></div><RouterLink :to="target(check)">{{ check.ready ? 'View' : 'Fix this' }} →</RouterLink></li></ul></template>
  </section>
</template>
<style>
#lc-app .shop-readiness { margin: 16px 0; padding: 18px; background: #fff; border: 1px solid #dce6dc; border-radius: 16px; }
#lc-app .shop-readiness header, #lc-app .shop-readiness li { display: flex; align-items: center; gap: 14px; justify-content: space-between; }
#lc-app .shop-readiness h2 { margin: 0; font-size: 20px; }
#lc-app .shop-readiness p { margin: 6px 0; color: #63756a; font-size: 13px; }
#lc-app .shop-readiness ul { padding: 0; list-style: none; }
#lc-app .shop-readiness li { padding: 12px 0; border-top: 1px solid #edf1ea; }
#lc-app .shop-readiness li > div { flex: 1; }
#lc-app .shop-readiness li > span { font-size: 12px; color: #975218; }
#lc-app .shop-readiness li > span.passed { color: #176547; }
#lc-app .shop-readiness a { white-space: nowrap; font-weight: 650; }
@media(max-width:600px) { #lc-app .shop-readiness header { flex-wrap: wrap; } #lc-app .shop-readiness li { align-items: flex-start; flex-wrap: wrap; } #lc-app .shop-readiness li > div { flex-basis: 65%; } }
</style>
