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
    if (session.value.user === user) message.value = result.saved ? 'Alert saved. Enable phone notifications to receive push alerts.' : 'Stock alert cancelled.'
  } catch (e) { error.value = e.message }
  finally { busy.value = false }
}
</script>
<template>
  <div class="stock-alert-control" :class="{ subscribed: saved }">
    <button type="button" :disabled="busy" :aria-pressed="saved" :aria-label="saved ? 'Cancel back-in-stock notification' : 'Notify me when this product is back in stock'" @click.stop.prevent="toggle">
      <svg v-if="!saved" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9Z" /><path d="M10 21h4" /></svg>
      <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="m5 12 4 4L19 6" /></svg>
      <span>{{ busy ? 'Saving…' : saved ? 'Alert on' : 'Notify me' }}</span><span v-if="saved && !busy" class="stock-alert-cancel">Cancel</span>
    </button>
    <small v-if="message" role="status">{{ message }}</small><small v-if="error" class="stock-alert-error" role="alert">{{ error }}</small>
  </div>
</template>
<style>
#lc-app .stock-alert-control { display: grid; gap: 6px; margin-top: 10px; min-width: 0; }
#lc-app .stock-alert-control button { display: flex; align-items: center; justify-content: center; gap: 8px; width: 100%; border: 1px solid #c5d9cb; border-radius: 12px; background: #fff; color: #176647; padding: 10px 12px; min-height: 44px; font-size: 13px; font-weight: 700; cursor: pointer; }
#lc-app .stock-alert-control button:hover { background: #f0f6ee; border-color: #176647; }
#lc-app .stock-alert-control button:focus-visible { outline: 3px solid #e6bd45; outline-offset: 3px; }
#lc-app .stock-alert-control button:disabled { opacity: .65; cursor: wait; }
#lc-app .stock-alert-control.subscribed button { background: #eef6ef; }
#lc-app .stock-alert-control svg { flex-shrink: 0; }
#lc-app .stock-alert-cancel { margin-left: auto; font-size: 12px; font-weight: 500; text-decoration: underline; }
#lc-app .stock-alert-control small { font-size: 12px; line-height: 1.5; color: #52695a; overflow-wrap: anywhere; }
#lc-app .stock-alert-control .stock-alert-error { color: #a33526; }
</style>
