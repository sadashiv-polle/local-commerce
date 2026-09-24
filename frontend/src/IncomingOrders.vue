<script setup>
import OrderReference from './OrderReference.vue'
import ManualUpiPayment from './ManualUpiPayment.vue'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { call } from './api.js'

const props = defineProps({ shops: { type: Array, default: () => [] } })
const orders = ref([]), busy = ref(false), error = ref(''), now = ref(Date.now())
const rejecting = ref(false), rejectReason = ref('Unable to fulfil this order')
const minimized = ref(false)
const current = computed(() => orders.value[0] || null)
const urgent = computed(() => current.value && remainingSeconds(current.value) <= 120)
let pollTimer, clockTimer, reminderTimer, audioContext

function money(value, currency) {
  return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(value)
}
function remainingSeconds(order) {
  const end = Number(order?.responseDeadlineMs || 0)
  return Number.isFinite(end) ? Math.max(0, Math.ceil((end - now.value) / 1000)) : 0
}
function remaining(order) {
  const seconds = remainingSeconds(order)
  const minutes = Math.floor(seconds / 60)
  return `${minutes}:${String(seconds % 60).padStart(2, '0')}`
}
function unlockAudio() {
  if (!audioContext) audioContext = new (window.AudioContext || window.webkitAudioContext)()
  if (audioContext.state === 'suspended') audioContext.resume()
}
function chime() {
  if (!current.value) return
  if ('vibrate' in navigator) navigator.vibrate([250, 120, 250])
  if (!audioContext || audioContext.state !== 'running') return
  const start = audioContext.currentTime
  for (const [offset, frequency] of [[0, 660], [0.18, 880]]) {
    const oscillator = audioContext.createOscillator()
    const gain = audioContext.createGain()
    oscillator.frequency.value = frequency
    oscillator.type = 'sine'
    gain.gain.setValueAtTime(0.0001, start + offset)
    gain.gain.exponentialRampToValueAtTime(0.22, start + offset + 0.02)
    gain.gain.exponentialRampToValueAtTime(0.0001, start + offset + 0.3)
    oscillator.connect(gain).connect(audioContext.destination)
    oscillator.start(start + offset); oscillator.stop(start + offset + 0.32)
  }
}
async function load(force = false) {
  if (!props.shops.length) { orders.value = []; return }
  if (busy.value && !force) return
  try {
    const feeds = await Promise.all(props.shops.map(shop => call('orders.list_orders', { shop, start: 0, status: 'Requested' })))
    const unique = new Map()
    for (const order of feeds.flat()) if (order.status === 'Requested') unique.set(order.name, { ...order, responseDeadlineMs: Date.now() + Number(order.response_seconds_remaining || 0) * 1000 })
    orders.value = [...unique.values()].sort((a, b) => String(a.created).localeCompare(String(b.created)))
    error.value = ''
  } catch (exception) { error.value = exception.message }
}
async function change(target) {
  if (!current.value || busy.value) return
  busy.value = true; error.value = ''
  try {
    await call('orders.change', {
      order: current.value.name,
      target,
      reason: target === 'Cancelled' ? rejectReason.value.trim() : '',
    }, true)
    rejecting.value = false
    await load(true)
    window.dispatchEvent(new CustomEvent('lc-orders-change'))
  } catch (exception) { error.value = exception.message }
  finally { busy.value = false }
}
const upiVerified = computed(() => !current.value?.upi || ['Paid', 'Reconciled'].includes(current.value.payment_status))
watch(() => props.shops.join(','), load, { immediate: true })
watch(() => current.value?.name, (value, previous) => {
  rejecting.value = false
  if (value && value !== previous) { minimized.value = false; chime() }
})
onMounted(() => {
  window.addEventListener('pointerdown', unlockAudio, { once: true })
  pollTimer = window.setInterval(load, 8000)
  clockTimer = window.setInterval(() => { now.value = Date.now() }, 1000)
  reminderTimer = window.setInterval(chime, 15000)
})
onBeforeUnmount(() => {
  window.removeEventListener('pointerdown', unlockAudio)
  window.clearInterval(pollTimer); window.clearInterval(clockTimer); window.clearInterval(reminderTimer)
  audioContext?.close()
})
</script>

<template>
  <button v-if="current && minimized" type="button" class="incoming-order-minimized" :class="{ urgent }" aria-label="Open waiting order" @click="minimized = false"><span class="incoming-pulse" aria-hidden="true"></span><span><small>NEW ORDER · {{ current.shop_name }}</small><strong>{{ orders.length > 1 ? `${orders.length} orders waiting` : `${current.recipient}'s order` }}</strong></span><time>{{ remaining(current) }} left</time><b>Open ›</b></button>
  <div v-else-if="current" class="incoming-order" role="alertdialog" aria-modal="true" aria-labelledby="incoming-order-title">
    <section class="incoming-order-card">
      <header :class="{ urgent }"><span class="incoming-pulse" aria-hidden="true"></span><div><span class="eyebrow">NEW ORDER</span><strong>{{ orders.length > 1 ? `${orders.length} orders waiting` : 'Needs your response' }}</strong></div><time>{{ remaining(current) }} left</time><button type="button" class="incoming-minimize" aria-label="Minimize order alert" @click="minimized = true"><span aria-hidden="true">—</span><small>Minimize</small></button></header>
      <div class="incoming-order-body"><OrderReference :order-id="current.name" /><span class="eyebrow">{{ current.shop_name }}</span><h1 id="incoming-order-title">New order from {{ current.recipient }}</h1><p>{{ current.items.length }} {{ current.items.length === 1 ? 'item' : 'items' }} · {{ money(current.total, current.currency) }}</p><ul><li v-for="item in current.items" :key="item.item_code"><span>{{ item.quantity }} × {{ item.name }}</span><strong>{{ money(item.amount, current.currency) }}</strong></li></ul><div class="incoming-address"><span aria-hidden="true">⌖</span><div><small>DELIVER TO</small><strong>{{ current.address.line1 }}</strong><span>{{ current.address.city }} · {{ current.address.postal_code }}</span></div></div><ManualUpiPayment v-if="current.upi" :order="current" :editable="true" @updated="load(true)" /><p v-if="current.upi && !upiVerified" class="lc-notice">Verify the UPI payment above before accepting this order.</p><p v-if="error" class="lc-notice" role="alert">{{ error }}</p></div>
      <footer v-if="!upiVerified" class="incoming-payment-waiting"><strong>Payment verification required</strong><span>Review the customer’s UPI proof above. Accept or reject will be available after verification.</span></footer>
      <footer v-else-if="!rejecting"><button type="button" class="incoming-reject" :disabled="busy" @click="rejecting = true">Reject</button><button type="button" class="incoming-accept" :disabled="busy" @click="change('Accepted')">{{ busy ? 'Accepting…' : 'Accept order' }}</button></footer>
      <footer v-else class="incoming-reject-confirm"><label>Reason for rejection<input v-model="rejectReason" minlength="3" maxlength="500" autofocus></label><button type="button" :disabled="busy" @click="rejecting = false">Go back</button><button type="button" class="incoming-reject" :disabled="busy || rejectReason.trim().length < 3" @click="change('Cancelled')">{{ busy ? 'Rejecting…' : 'Confirm reject' }}</button></footer>
    </section>
  </div>
</template>
