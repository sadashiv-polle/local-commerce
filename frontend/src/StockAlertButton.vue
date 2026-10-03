<script setup>
import { computed, inject, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { call } from './api.js'
import { loadStockAlerts, stockAlerts, setStockAlert } from './stock-alerts-state.js'
const props = defineProps({ item: { type: String, required: true }, shop: { type: String, required: true } })
const session = inject('session'), router = useRouter(), busy = ref(false), error = ref(''), message = ref('')
const saved = computed(() => stockAlerts.value.has(props.item))
watch(() => session.value.user, user => { error.value = ''; message.value = ''; loadStockAlerts(user).catch(() => {}) }, { immediate: true })
async function toggle() {
  const user = session.value.user
  if (user === 'Guest') { router.push({ path: '/login', query: { next: `/store/${props.shop}?item=${encodeURIComponent(props.item)}` } }); return }
  busy.value = true; error.value = ''; message.value = ''
  try {
    const result = await call('stock_alerts.toggle', { shop: props.shop, item: props.item, saved: saved.value ? 0 : 1 }, true)
    setStockAlert(user, props.item, result.saved)
    if (session.value.user === user) message.value = result.saved ? 'We’ll notify you once it’s back. Phone alerts need notifications enabled.' : 'Stock alert cancelled.'
  } catch (e) { error.value = e.message }
  finally { busy.value = false }
}
</script>
<template>
  <div class="stock-alert-control">
    <button type="button" :disabled="busy" :aria-pressed="saved" @click.stop.prevent="toggle">{{ busy ? 'Saving…' : saved ? '✓ Notification set · Cancel' : 'Notify me when available' }}</button>
    <small v-if="message" role="status">{{ message }}</small><small v-if="error" role="alert">{{ error }}</small>
  </div>
</template>
<style>
#lc-app .stock-alert-control { display: grid; gap: 6px; margin-top: 10px; }
#lc-app .stock-alert-control button { border: 1px solid #abcbb4; border-radius: 10px; background: #f0f6ee; color: #176647; padding: 10px 12px; min-height: 44px; font-size: 13px; font-weight: 700; }
#lc-app .stock-alert-control small { font-size: 12px; line-height: 1.5; color: #52695a; }
</style>
