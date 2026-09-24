<script setup>
import { computed, inject, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { call } from './api.js'

const session = inject('session')
const customer = computed(() => session.value?.user !== 'Guest' && session.value?.roles?.includes('LC Customer'))
const orders = ref([])
const labels = {
  Requested: 'Waiting for shop confirmation',
  Accepted: 'Your order is confirmed',
  Preparing: 'Your order is being prepared',
  Ready: 'Your order is ready for pickup',
  'Picked Up': 'Your delivery person has picked up your order',
  'Out for Delivery': 'Your order is on the way',
}
let timer, generation = 0, pending = false
async function refresh() {
  if (!customer.value || document.hidden || pending) return
  const current = generation
  pending = true
  try {
    const result = await call('orders.active_orders')
    if (current === generation) orders.value = result
  } catch { /* Browsing stays available if order updates are temporarily unavailable. */ }
  finally { pending = false }
}
watch(() => session.value?.user, () => { generation++; orders.value = []; refresh() })
onMounted(() => {
  refresh()
  timer = window.setInterval(refresh, 15000)
  window.addEventListener('lc-orders-change', refresh)
  document.addEventListener('visibilitychange', refresh)
})
onBeforeUnmount(() => {
  generation++
  window.clearInterval(timer)
  window.removeEventListener('lc-orders-change', refresh)
  document.removeEventListener('visibilitychange', refresh)
})
</script>

<template>
  <section v-if="customer && orders.length" class="home-active-orders" aria-label="Your active orders">
    <RouterLink v-for="order in orders" :key="order.name" class="home-active-order" :to="{ path: '/orders', query: { order: order.name } }">
      <span class="home-active-order-dot" aria-hidden="true"></span>
      <span class="home-active-order-copy"><small>{{ order.shop_name }}<template v-if="order.delivery_mode === 'Scheduled'"> · Scheduled</template></small><strong>{{ labels[order.status] || order.status }}</strong></span>
      <span class="home-active-order-action">Track order <span aria-hidden="true">→</span></span>
    </RouterLink>
  </section>
</template>

<style>
#lc-app .home-active-orders { display: grid; gap: 8px; margin-bottom: 16px; }
#lc-app .home-active-order { display: flex; align-items: center; gap: 12px; padding: 12px 16px; border: 1px solid #cde1d2; border-radius: 14px; background: #f0f7ef; color: #204e38; text-decoration: none; min-height: 44px; }
#lc-app .home-active-order-dot { width: 8px; height: 8px; background: #188552; border-radius: 50%; flex-shrink: 0; }
#lc-app .home-active-order-copy { display: grid; gap: 3px; min-width: 0; }
#lc-app .home-active-order-copy small { font-size: 12px; color: #5b7061; }
#lc-app .home-active-order-copy strong { font-size: 14px; line-height: 1.4; }
#lc-app .home-active-order-action { margin-left: auto; flex-shrink: 0; font-size: 13px; font-weight: 700; }
#lc-app .home-active-order:hover { border-color: #188552; }
#lc-app .home-active-order:focus-visible { outline: 3px solid #d8b43c; outline-offset: 3px; }
@media (max-width: 480px) {
  #lc-app .home-active-order { padding: 10px 12px; gap: 8px; }
  #lc-app .home-active-order-copy strong { font-size: 13px; }
  #lc-app .home-active-order-action { font-size: 12px; }
}
</style>
