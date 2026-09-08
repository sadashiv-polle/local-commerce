<script setup>
import { computed, inject, onMounted, ref } from 'vue'
import { call } from './api.js'
import Products from './Products.vue'
const session = inject('session'), shops = ref([]), error = ref(''), loading = ref(false)
const start = ref(0), selected = ref(null), saving = ref(false), saved = ref('')
const canList = computed(() => session.value.platform_admin || session.value.memberships.some(m => ['Owner', 'Staff'].includes(m.membership_role)))
const canEdit = computed(() => selected.value && (session.value.platform_admin || session.value.memberships.some(m => m.shop === selected.value.name && m.membership_role === 'Owner')))
async function load(delta = 0) {
  loading.value = true; error.value = ''; start.value = Math.max(0, start.value + delta)
  try { shops.value = await call('shops.list_shops', { start: start.value, page_length: 20 }) }
  catch (e) { error.value = e.message }
  finally { loading.value = false }
}
async function open(shop) {
  error.value = ''; saved.value = ''
  try { selected.value = await call('shops.get_shop', { shop }) }
  catch (e) { error.value = e.message }
}
async function save() {
  saving.value = true; error.value = ''; saved.value = ''
  try {
    const s = selected.value
    selected.value = await call('shops.update_shop', { shop: s.name, shop_name: s.shop_name, status: s.status, description: s.description || '' }, true)
    saved.value = 'Shop settings saved.'; await load()
  } catch (e) { error.value = e.message }
  finally { saving.value = false }
}
onMounted(() => { if (canList.value) load() })
</script>

<template>
  <section v-if="canList" class="owner-page">
    <aside class="owner-sidebar"><span class="eyebrow">WORKSPACE</span><strong class="sidebar-active">⌂ &nbsp; My shops</strong><p>Manage your shops and keep your neighbourhood up to date.</p><div class="sidebar-bottom"><span class="status-pill">Connected</span><small>{{ session.user }}</small></div></aside>
    <div class="owner-content">
      <span class="eyebrow">A GOOD DAY TO GROW LOCAL</span><h1>Your business, at a glance.</h1><p class="muted">Your shops. Your people. Your neighbourhood.</p>
      <div class="lc-section-heading"><h2>Shop directory</h2><a v-if="session.platform_admin" href="/app/lc-shop">Manage in Desk ↗</a></div>
      <p v-if="error" role="alert" class="lc-notice">{{ error }}</p>
      <p v-if="loading" role="status">Loading shops…</p>
      <template v-else>
        <p v-if="!shops.length" class="lc-empty">No shops are available. A platform administrator can create a shop and assign membership in Desk.</p>
        <div class="lc-grid">
          <button v-for="shop in shops" :key="shop.name" class="lc-card" @click="open(shop.name)">
            <div class="shop-avatar" aria-hidden="true">{{ shop.shop_name.slice(0, 1).toUpperCase() }}</div><span class="lc-status">{{ shop.status }}</span><h3>{{ shop.shop_name }}</h3><span>{{ shop.company }}</span><span class="lc-card-link">Open shop →</span>
          </button>
        </div>
        <div class="lc-pagination"><button :disabled="!start" @click="load(-20)">Previous</button><span>Page {{ start / 20 + 1 }}</span><button :disabled="shops.length < 20" @click="load(20)">Next</button><button @click="load()">Refresh</button></div>
      </template>
      <Products v-if="selected" :key="selected.name" :shop="selected.name" :editable="canEdit" />
      <form v-if="selected" class="lc-form" @submit.prevent="save">
        <h2>Shop settings</h2>
        <label>Name<input v-model="selected.shop_name" required :disabled="!canEdit"></label>
        <label>Company<input :value="selected.company" disabled></label>
        <label>Status<select v-model="selected.status" :disabled="!canEdit"><option>Draft</option><option>Active</option><option>Temporarily Closed</option><option>Disabled</option></select></label>
        <label>Description<textarea v-model="selected.description" :disabled="!canEdit"></textarea></label>
        <button v-if="canEdit" class="lc-primary" :disabled="saving">{{ saving ? 'Saving…' : 'Save settings' }}</button>
        <p v-if="saved" role="status">{{ saved }}</p>
      </form>
    </div>
  </section>
  <section v-else class="lc-empty">
    <h2>Your account is connected</h2>
    <p v-if="session.roles.includes('LC Delivery Person')">Delivery assignments will be available when the delivery phase is installed.</p>
    <p v-else-if="session.roles.includes('LC Customer')">Customer ordering will be available when the ordering phase is installed.</p>
    <p v-else>Your account has no shop workspace. Contact your platform administrator for access.</p>
  </section>
</template>
