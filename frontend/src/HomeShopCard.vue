<script setup>
import { ref } from 'vue'
const props = defineProps({ shop: { type: Object, required: true }, hasAddress: Boolean })
const imageFailed = ref(false)
function money(value) { return new Intl.NumberFormat(undefined, { style: 'currency', currency: props.shop.currency || 'INR', maximumFractionDigits: 0 }).format(value) }
function dateTime(value) {
  // Slot values are shop-local wall times, not browser-local timestamps.
  const date = new Date(String(value).replace(' ', 'T') + 'Z')
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat(undefined, { timeZone: 'UTC', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }).format(date)
}
function time(value) { return String(value).slice(11, 16) }
</script>
<template>
  <RouterLink class="home-shop-card" :to="{ name: 'customer-shop', params: { shop: shop.name } }">
    <div class="home-shop-cover">
      <img v-if="shop.shop_image && !imageFailed" :src="shop.shop_image" :alt="shop.shop_name" loading="lazy" @error="imageFailed = true">
      <div v-else class="home-shop-placeholder" aria-hidden="true"><svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 28v27h40V28M8 28l6-17h36l6 17M8 28h48M24 55V36h16v19M24 11l-3 17m19-17 3 17" /></svg><span>{{ shop.shop_type || 'Your neighbourhood shop' }}</span></div>
      <span class="home-shop-state" :class="{ closed: !shop.availability?.open }">{{ shop.availability?.label || 'View availability' }}</span>
      <span v-if="shop.distance_km != null" class="home-shop-distance">{{ Number(shop.distance_km).toFixed(1) }} km</span>
    </div>
    <div class="home-shop-body">
      <small>{{ shop.city || 'Local to you' }}</small><h3>{{ shop.shop_name }}</h3>
      <p v-if="shop.description" class="home-shop-description">{{ shop.description }}</p>
      <div class="home-shop-delivery"><span v-if="shop.normal_delivery">Normal delivery</span><span v-if="shop.scheduled_enabled">Scheduled · free delivery</span><span v-if="!shop.normal_delivery && !shop.scheduled_enabled">Delivery unavailable</span></div>
      <p class="home-shop-minimum">{{ Number(shop.minimum_order_amount) > 0 ? `Minimum order ${money(shop.minimum_order_amount)}` : 'No minimum order' }}<span v-if="shop.normal_delivery && Number(shop.free_delivery_above) > 0"> · Free normal delivery above {{ money(shop.free_delivery_above) }}</span></p>
      <div v-if="shop.next_slot" class="home-shop-schedule"><strong>Next delivery: {{ dateTime(shop.next_slot.delivery_start) }} – {{ time(shop.next_slot.delivery_end) }}</strong><small>Order by {{ dateTime(shop.next_slot.ordering_end) }} · Check slot availability in shop</small></div>
      <small v-if="hasAddress" class="serviceability-line" :class="{ available: shop.serviceable }">{{ shop.serviceability_message }}</small>
      <span class="home-shop-browse">Browse shop <span aria-hidden="true">→</span></span>
    </div>
  </RouterLink>
</template>
