<script setup>
import { onMounted, ref } from 'vue'
import { call, upload } from './api.js'
const config = ref(null), busy = ref(false), error = ref(''), message = ref(''), newGroup = ref('')
onMounted(async () => { try { config.value = await call('storefront.category_settings') } catch (e) { error.value = e.message } })
function add() {
  if (!newGroup.value || config.value.categories.some(row => row.item_group === newGroup.value)) return
  config.value.categories.push({ item_group: newGroup.value, label: newGroup.value, section: 'Everyday essentials', image: '', enabled: true })
  newGroup.value = ''
}
function move(index, direction) {
  const target = index + direction
  if (target < 0 || target >= config.value.categories.length) return
  const [row] = config.value.categories.splice(index, 1)
  config.value.categories.splice(target, 0, row)
}
async function image(row, event) {
  const file = event.target.files?.[0]
  if (!file) return
  busy.value = true; error.value = ''; message.value = ''
  try { row.image = (await upload('storefront.upload_category_image', {}, file)).image }
  catch (e) { error.value = e.message } finally { busy.value = false; event.target.value = '' }
}
async function save() {
  busy.value = true; error.value = ''; message.value = ''
  try { config.value = await call('storefront.save_categories', { enabled: config.value.enabled ? 1 : 0, categories: config.value.categories }, true); message.value = 'Category menu saved.' }
  catch (e) { error.value = e.message } finally { busy.value = false }
}
</script>
<template>
  <section class="category-menu-settings">
    <header><span class="eyebrow">CUSTOMER STOREFRONT</span><h2>Category menu</h2><p class="muted">Choose what customers see. Upload category artwork, arrange tiles, and turn categories on or off.</p></header>
    <p v-if="error" role="alert" class="lc-notice">{{ error }}</p><p v-if="message" role="status" class="success-note">{{ message }}</p>
    <form v-if="config" @submit.prevent="save">
      <fieldset :disabled="busy">
        <label class="category-menu-switch"><input v-model="config.enabled" type="checkbox">Show category menu on the store</label>
        <div class="category-add-row"><label>Add category<select v-model="newGroup"><option value="">Choose an Item Group</option><option v-for="group in config.groups.filter(name => !config.categories.some(row => row.item_group === name))" :key="group">{{ group }}</option></select></label><button type="button" :disabled="!newGroup || config.categories.length >= 40" @click="add">+ Add category</button></div>
        <div class="category-admin-list">
          <article v-for="(row, index) in config.categories" :key="row.item_group" class="category-admin-card">
            <div class="category-admin-art"><img v-if="row.image" :src="row.image" alt=""><span v-else aria-hidden="true">🛍️</span><label>Change image<input type="file" accept="image/jpeg,image/png,image/webp" @change="image(row, $event)"></label></div>
            <div class="category-admin-fields"><strong>{{ row.item_group }}</strong><label>Display name<input v-model="row.label" maxlength="60" required></label><label>Section heading<input v-model="row.section" maxlength="60" required placeholder="Everyday essentials"></label><label class="category-menu-switch"><input v-model="row.enabled" type="checkbox">{{ row.enabled ? 'Shown to customers' : 'Hidden from menu' }}</label></div>
            <div class="category-admin-actions"><button type="button" :disabled="!index" aria-label="Move category up" @click="move(index, -1)">↑</button><button type="button" :disabled="index === config.categories.length - 1" aria-label="Move category down" @click="move(index, 1)">↓</button><button type="button" @click="config.categories.splice(index, 1)">Remove</button></div>
          </article>
        </div><button type="submit" class="lc-primary">{{ busy ? 'Saving…' : 'Save category menu' }}</button>
      </fieldset>
    </form>
  </section>
</template>
