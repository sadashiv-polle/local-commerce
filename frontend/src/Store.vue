<script setup>
import { computed, inject, onMounted, ref } from 'vue'
import { call } from './api.js'
const session = inject('session')
const canOrder = computed(() => session.value.platform_admin || session.value.roles.includes('LC Customer'))
const shops = ref([]), error = ref(''), start = ref(0), loading = ref(false)
async function load(delta = 0) {
  start.value = Math.max(0, start.value + delta); loading.value = true; error.value = ''
  try { shops.value = await call('orders.shops', { start: start.value }) } catch(e) { error.value = e.message } finally { loading.value = false }
}
onMounted(() => { if (canOrder.value) load() })
const browse = ref(null)
</script>

<template>
  <div class="store-page">
    <section class="store-hero">
      <div><span class="eyebrow">GOOD THINGS, CLOSE TO HOME</span><h1>Your neighbourhood.<br>Your everyday essentials.</h1><p>Fresh finds and familiar favourites.<br>Discover a better way to shop local.</p><button class="primary" @click="browse?.scrollIntoView()">Explore the neighbourhood <span>↗</span></button></div>
      <div class="hero-art" aria-hidden="true"><span class="art-label">FRESH · LOCAL · EVERYDAY</span><div class="produce">🥬<span>🍊</span>🥖</div><div class="market-bag">local<span>good things inside.</span></div><span class="art-sticker">A little<br>closer.</span></div>
    </section>
    <section ref="browse" class="browse-section">
      <div class="section-title"><h2>Shops accepting delivery requests</h2><RouterLink v-if="canOrder" to="/orders">My orders →</RouterLink></div>
      <p v-if="!canOrder" class="lc-empty">Ask your administrator to enable the LC Customer role to request delivery.</p>
      <template v-else>
        <p v-if="error" role="alert" class="lc-notice">{{ error }}</p><p v-if="loading" role="status">Loading shops…</p>
        <div class="lc-grid"><RouterLink v-for="shop in shops" :key="shop.name" class="lc-card" :to="{ name: 'customer-shop', params: { shop: shop.name } }"><h3>{{ shop.shop_name }}</h3><p>{{ shop.description }}</p><span class="lc-card-link">Browse products →</span></RouterLink></div>
        <p v-if="!loading && !shops.length" class="lc-empty">No shops are accepting delivery requests yet.</p>
        <div class="lc-pagination"><button :disabled="!start || loading" @click="load(-20)">Previous</button><button :disabled="shops.length < 20 || loading" @click="load(20)">Next</button><button :disabled="loading" @click="load()">Refresh</button></div>
      </template>
    </section>
    <div class="values"><div><strong>Local at heart</strong><p>Your neighbourhood businesses, together.</p></div><div><strong>Everyday made easier</strong><p>One place for the things you need.</p></div><div><strong>More choice, closer by</strong><p>From fresh produce to familiar favourites.</p></div></div>
  </div>
</template>
