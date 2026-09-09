<script setup>
import { computed, inject, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { call } from './api.js'
import Products from './Products.vue'
const session = inject('session'), route = useRoute()
const shop = ref(null), loading = ref(false), error = ref(''), saved = ref(''), saving = ref(false)
const tab = ref('inventory')
const canEdit = computed(() => shop.value && (session.value.platform_admin || session.value.memberships.some(m => m.shop === shop.value.name && m.membership_role === 'Owner')))
let request = 0
async function load() {
  const current = ++request
  shop.value = null; loading.value = true; error.value = ''; saved.value = ''; tab.value = 'inventory'
  try {
    const result = await call('shops.get_shop', { shop: route.params.shop })
    if (current === request) shop.value = result
  } catch (e) { if (current === request) error.value = e.message }
  finally { if (current === request) loading.value = false }
}
async function save() {
  saving.value = true; error.value = ''; saved.value = ''
  const current = request
  try {
    const s = shop.value
    const result = await call('shops.update_shop', { shop: s.name, shop_name: s.shop_name, status: s.status, description: s.description || '' }, true)
    if (current === request) { shop.value = result; saved.value = 'Shop settings saved.' }
  } catch (e) { if (current === request) error.value = e.message }
  finally { saving.value = false }
}
watch(() => route.params.shop, load, { immediate: true })
</script>

<template>
  <section class="owner-page">
    <aside class="owner-sidebar">
      <RouterLink class="workspace-back" to="/shop">← All shops</RouterLink>
      <span class="eyebrow">SHOP WORKSPACE</span>
      <strong>{{ shop?.shop_name || 'Your shop' }}</strong>
      <p>Everything you need to manage this shop, in one place.</p>
      <nav v-if="shop" class="workspace-nav" aria-label="Shop sections">
        <button :class="{ 'sidebar-active': tab === 'inventory' }" :aria-current="tab === 'inventory' ? 'page' : undefined" @click="tab = 'inventory'">Products &amp; stock</button>
        <button :class="{ 'sidebar-active': tab === 'settings' }" :aria-current="tab === 'settings' ? 'page' : undefined" @click="tab = 'settings'">Shop settings</button>
      </nav>
      <div class="sidebar-bottom"><span class="status-pill">{{ canEdit ? 'Owner access' : 'Read-only access' }}</span><small>{{ session.user }}</small></div>
    </aside>
    <div class="owner-content">
      <p v-if="loading" role="status">Opening your shop…</p>
      <div v-if="error" class="lc-notice" role="alert">{{ error }} <button v-if="!shop" @click="load">Retry</button></div>
      <template v-if="shop">
        <header class="workspace-heading"><div><span class="eyebrow">YOUR SHOP</span><h1>{{ shop.shop_name }}</h1><p class="muted">{{ shop.company }}</p></div><span class="status-pill">{{ shop.status }}</span></header>
        <Products v-show="tab === 'inventory'" :key="shop.name" :shop="shop.name" :editable="canEdit" />
        <form v-show="tab === 'settings'" class="lc-form" @submit.prevent="save">
          <h2>Shop settings</h2><p class="muted">Keep your shop details and availability up to date.</p>
          <fieldset :disabled="!canEdit || saving" class="workspace-fields">
            <label>Name<input v-model="shop.shop_name" required></label>
            <label>Company<input :value="shop.company" disabled></label>
            <label>Status<select v-model="shop.status"><option>Draft</option><option>Active</option><option>Temporarily Closed</option><option>Disabled</option></select></label>
            <label>Description<textarea v-model="shop.description"></textarea></label>
            <button v-if="canEdit" class="lc-primary">{{ saving ? 'Saving…' : 'Save settings' }}</button>
          </fieldset>
          <p v-if="saved" role="status">{{ saved }}</p>
        </form>
      </template>
    </div>
  </section>
</template>
