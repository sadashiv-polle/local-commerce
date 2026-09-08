<script setup>
import { onMounted, ref } from 'vue'
import { call } from './api.js'
const props = defineProps({ shop: { type: String, required: true }, editable: Boolean })
const items = ref([]), choices = ref({ groups: [], uoms: [] }), loading = ref(false), saving = ref(false)
const error = ref(''), success = ref(''), start = ref(0)
const form = ref({ item_name: '', item_group: '', stock_uom: '' })
async function load(delta = 0) {
  loading.value = true; error.value = ''; start.value = Math.max(0, start.value + delta)
  try { items.value = await call('products.list_items', { shop: props.shop, start: start.value }) }
  catch (e) { error.value = e.message }
  finally { loading.value = false }
}
async function init() {
  await load()
  if (props.editable) {
    try { choices.value = await call('products.options', { shop: props.shop }) }
    catch (e) { error.value = e.message }
  }
}
async function create() {
  saving.value = true; error.value = ''; success.value = ''
  try {
    const item = await call('products.create_item', { shop: props.shop, ...form.value }, true)
    success.value = `${item.item_name} added to your shop.`; form.value.item_name = ''; start.value = 0
    await load()
  } catch (e) { error.value = e.message }
  finally { saving.value = false }
}
onMounted(init)
</script>

<template>
  <section class="products-panel">
    <div class="lc-section-heading"><div><span class="eyebrow">YOUR SHOP CATALOG</span><h2>Products</h2></div><button :disabled="loading" @click="init">Refresh</button></div>
    <p class="muted">Add your products here. Pricing and stock quantities will be connected in the next step.</p>
    <p v-if="error" class="lc-notice" role="alert">{{ error }}</p>
    <p v-if="success" class="lc-notice" role="status">{{ success }}</p>
    <form v-if="editable" class="lc-form" @submit.prevent="create">
      <h3>Add a product</h3>
      <label>Product name<input v-model="form.item_name" required maxlength="140" placeholder="e.g. Fresh whole wheat bread" :disabled="saving"></label>
      <label>Category<select v-model="form.item_group" required :disabled="saving"><option disabled value="">Select a category</option><option v-for="group in choices.groups" :key="group">{{ group }}</option></select></label>
      <label>Unit of measure<select v-model="form.stock_uom" required :disabled="saving"><option disabled value="">Select a unit</option><option v-for="uom in choices.uoms" :key="uom">{{ uom }}</option></select></label>
      <button class="lc-primary" :disabled="saving || !choices.groups.length || !choices.uoms.length">{{ saving ? 'Adding…' : 'Add product' }}</button>
      <p v-if="!choices.groups.length || !choices.uoms.length" class="muted">Your administrator must configure product categories and enabled units before you can add products.</p>
    </form>
    <p v-if="loading" role="status">Loading products…</p>
    <template v-else>
      <p v-if="!items.length" class="lc-empty">No products on this page yet.</p>
      <div class="lc-grid product-grid"><article v-for="item in items" :key="item.name" class="lc-card"><span class="status-pill">{{ item.disabled ? 'Disabled' : 'Active' }}</span><h3>{{ item.item_name }}</h3><p>{{ item.item_group }} · {{ item.stock_uom }}</p><small class="muted">{{ item.name }}</small></article></div>
      <div class="lc-pagination"><button :disabled="loading || !start" @click="load(-20)">Previous</button><span>Page {{ start / 20 + 1 }}</span><button :disabled="loading || items.length < 20" @click="load(20)">Next</button></div>
    </template>
  </section>
</template>
