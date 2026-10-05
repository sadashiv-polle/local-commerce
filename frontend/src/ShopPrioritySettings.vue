<script setup>
import { onMounted, ref } from 'vue'
import { call } from './api.js'
const config = ref(null), busy = ref(false), error = ref(''), message = ref('')
onMounted(async () => {
  try { config.value = await call('storefront.shop_priority_settings') }
  catch (e) { error.value = e.message }
})
async function save() {
  busy.value = true; error.value = ''; message.value = ''
  try {
    await call('storefront.save_shop_priority', { pinned_shop: config.value.pinned_shop }, true)
    message.value = 'Shop display order saved.'
  } catch (e) { error.value = e.message } finally { busy.value = false }
}
</script>
<template>
  <section class="category-menu-settings">
    <h2>Show a shop first</h2>
    <p>The selected active shop appears first, even outside the customer’s delivery range. Delivery rules still apply. Searches only show matching shops.</p>
    <p v-if="error" class="lc-notice" role="alert">{{ error }}</p>
    <p v-if="message" role="status">{{ message }}</p>
    <form v-if="config" class="lc-form" @submit.prevent="save">
      <label>Priority shop<select v-model="config.pinned_shop" :disabled="busy"><option value="">None — use normal sorting</option><option v-if="config.pinned_shop && !config.shops.some(shop => shop.name === config.pinned_shop)" :value="config.pinned_shop">{{ config.pinned_shop }} (inactive)</option><option v-for="shop in config.shops" :key="shop.name" :value="shop.name">{{ shop.shop_name }}</option></select></label>
      <button type="submit" class="lc-primary" :disabled="busy">{{ busy ? 'Saving…' : 'Save shop priority' }}</button>
    </form>
  </section>
</template>
