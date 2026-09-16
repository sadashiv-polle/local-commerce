<script setup>
import { inject, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { call } from './api.js'
const session = inject('session'), settings = ref(null), search = ref(''), results = ref([]), busy = ref(false), error = ref(''), message = ref('')
const searchInput = ref(null), pickerLoading = ref(false), pickerError = ref(''), start = ref(0), hasMore = ref(false)
let timer, generation = 0
async function load() { try { settings.value = await call('storefront.settings') } catch (e) { error.value = e.message } }
async function find(delta = 0) {
  const current = ++generation
  start.value = Math.max(0, start.value + delta); pickerLoading.value = true; pickerError.value = ''
  try {
    const result = await call('storefront.product_options', { search: search.value, start: start.value })
    if (current === generation) { results.value = result.items; hasMore.value = result.has_more }
  } catch (e) { if (current === generation) pickerError.value = e.message }
  finally { if (current === generation) pickerLoading.value = false }
}
function scheduleSearch() {
  window.clearTimeout(timer); generation++; start.value = 0; pickerLoading.value = true
  timer = window.setTimeout(() => find(), 250)
}
async function select(item) {
  if (settings.value.products.length >= 24 || settings.value.products.some(row => row.item === item.item)) return
  settings.value.products.push({ item: item.item, item_name: item.item_name })
  if (search.value) search.value = ''
  else { start.value = 0; find() }
  await nextTick(); searchInput.value?.focus()
}
async function save() { busy.value = true; error.value = ''; message.value = ''; try { settings.value = await call('storefront.configure', { mode: settings.value.mode, title: settings.value.title, random_count: settings.value.random_count, products: settings.value.products.map(item => item.item) }, true); message.value = 'Public store updated.' } catch (e) { error.value = e.message } finally { busy.value = false } }
watch(search, scheduleSearch)
watch(() => settings.value?.mode, mode => {
  window.clearTimeout(timer); generation++
  if (mode === 'Selected') { start.value = 0; find() }
})
onMounted(() => { if (session.value.platform_admin) load() })
onBeforeUnmount(() => { window.clearTimeout(timer); generation++ })
</script>
<template>
  <section class="store-page storefront-settings">
    <RouterLink to="/store">← Public store</RouterLink><h1>Storefront products</h1><p class="muted">Choose the products customers see above the shop directory.</p>
    <p v-if="!session.platform_admin" class="lc-notice">Platform administrator access is required.</p><p v-if="error" role="alert" class="lc-notice">{{ error }}</p><p v-if="message" role="status" class="success-note">{{ message }}</p>
    <form v-if="settings" class="lc-form" @submit.prevent="save">
      <fieldset :disabled="busy">
        <label>Display mode<select v-model="settings.mode"><option>Disabled</option><option>Selected</option><option>Random</option></select></label>
        <label>Section title<input v-model="settings.title" maxlength="80" required></label>
        <label v-if="settings.mode === 'Random'">Number of random products<input v-model.number="settings.random_count" type="number" min="1" max="24" required><small>A new selection is shown when the store is opened or refreshed.</small></label>
        <template v-if="settings.mode === 'Selected'">
          <div class="featured-product-picker">
            <label>Find products<input ref="searchInput" v-model="search" type="search" maxlength="140" placeholder="Search an item or shop name…" autocomplete="off" @keydown.enter.prevent><small>Click an item to select it. The search clears so you can pick the next one.</small></label>
            <p v-if="pickerLoading" role="status">Loading items…</p><p v-if="pickerError" role="alert">{{ pickerError }} <button type="button" @click="find()">Retry</button></p>
            <div class="featured-picker-options" aria-label="Available products" :aria-busy="pickerLoading">
              <button v-for="item in results" :key="item.item" type="button" :disabled="pickerLoading || settings.products.length >= 24 || settings.products.some(row => row.item === item.item)" @click="select(item)"><img v-if="item.image" :src="item.image" :alt="item.item_name" loading="lazy"><span v-else class="picker-item-letter" aria-hidden="true">{{ item.item_name.slice(0, 1) }}</span><span><strong>{{ item.item_name }}</strong><small>{{ item.shop_name }}</small></span><b>{{ settings.products.some(row => row.item === item.item) ? '✓ Selected' : '+' }}</b></button>
            </div>
            <p v-if="!pickerLoading && !pickerError && !results.length" class="muted">No matching items. Try another name.</p>
            <div class="lc-pagination"><button type="button" :disabled="pickerLoading || !start" @click="find(-20)">Previous</button><button type="button" :disabled="pickerLoading || !hasMore" @click="find(20)">Next</button></div>
          </div>
          <h3>Selected products · {{ settings.products.length }}/24</h3><p class="muted">Products appear in the order you select them.</p>
          <div class="featured-selection"><article v-for="item in settings.products" :key="item.item"><strong>{{ item.item_name }}</strong><button type="button" @click="settings.products = settings.products.filter(row => row.item !== item.item)">Remove</button></article></div>
        </template>
        <button type="submit" class="lc-primary">{{ busy ? 'Saving…' : 'Save public store' }}</button>
      </fieldset>
    </form>
  </section>
</template>
