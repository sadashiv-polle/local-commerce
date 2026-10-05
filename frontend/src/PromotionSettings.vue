<script setup>
import { onMounted, ref } from 'vue'
import { call, upload } from './api.js'
const config = ref(null), busy = ref(false), error = ref(''), message = ref('')
onMounted(async () => { try { config.value = await call('storefront.promotion_settings') } catch (e) { error.value = e.message } })
function add() { config.value.slides.push({ title: '', image: '', link: '', enabled: true }) }
function move(index, direction) {
  const rows = config.value.slides
  const [row] = rows.splice(index, 1); rows.splice(index + direction, 0, row)
}
async function image(row, event) {
  const file = event.target.files?.[0]
  if (!file) return
  busy.value = true; error.value = ''; message.value = ''
  try { row.image = (await upload('storefront.upload_promotion_image', {}, file)).image }
  catch (e) { error.value = e.message } finally { busy.value = false; event.target.value = '' }
}
async function save() {
  busy.value = true; error.value = ''; message.value = ''
  try { config.value = await call('storefront.save_promotions', { config: config.value }, true); message.value = config.value.enabled ? 'Promotional slider saved. Enabled slides will appear on the homepage.' : 'Saved, but hidden. Turn on Show slider on homepage to display it.' }
  catch (e) { error.value = e.message } finally { busy.value = false }
}
</script>
<template>
  <section class="promotion-settings">
    <h2>Homepage promotional slider</h2><p>Upload offer photos, choose their order, and show or hide them anytime. These banners advertise offers; they do not change checkout prices.</p>
    <p v-if="error" class="lc-notice" role="alert">{{ error }}</p><p v-if="message" role="status">{{ message }}</p>
    <form v-if="config" class="lc-form" @submit.prevent="save">
      <fieldset :disabled="busy">
        <label><input v-model="config.enabled" type="checkbox"> Show slider on homepage</label>
        <label><input v-model="config.autoplay" type="checkbox"> Automatically change slides</label>
        <label>Seconds between slides<input v-model.number="config.interval" type="number" min="3" max="30" required></label>
        <p>Use wide images (recommended 1600 × 500). JPG, PNG or WebP, up to 5 MB. Images are shown in full on mobile and laptop.</p>
        <article v-for="(row, index) in config.slides" :key="index" class="promotion-editor">
          <h3>Slide {{ index + 1 }}</h3><img v-if="row.image" :src="row.image" :alt="row.title || 'Slide preview'">
          <label>Photo<input type="file" accept="image/jpeg,image/png,image/webp" @change="image(row, $event)"></label>
          <label>Offer title / image description<input v-model="row.title" maxlength="80" required placeholder="Weekend offers at Fish World"></label>
          <label>App link (optional)<input v-model="row.link" maxlength="300" placeholder="/store/shop-id"><small>Paste the full shop/category page address, or the part after #.</small></label>
          <label><input v-model="row.enabled" type="checkbox"> Show this slide</label>
          <div class="promotion-editor-actions"><button type="button" :disabled="index === 0" @click="move(index, -1)">Move up</button><button type="button" :disabled="index === config.slides.length - 1" @click="move(index, 1)">Move down</button><button type="button" @click="config.slides.splice(index, 1)">Delete slide</button></div>
        </article>
        <button type="button" :disabled="config.slides.length >= 12" @click="add">+ Add slide</button>
        <button type="submit" class="lc-primary">{{ busy ? 'Saving…' : 'Save promotional slider' }}</button>
      </fieldset>
      <p v-if="error" class="lc-notice" role="alert">{{ error }}</p>
      <p v-if="message" role="status">{{ message }}</p>
    </form>
  </section>
</template>
<style>
#lc-app .promotion-settings { border-bottom: 1px solid #dce6dc; padding-bottom: 24px; margin-bottom: 24px; }
#lc-app .promotion-editor { padding: 16px; margin: 16px 0; border: 1px solid #dce6dc; border-radius: 14px; background: #fff; }
#lc-app .promotion-editor > img { display: block; width: 100%; max-height: 180px; object-fit: contain; background: #f1f5ee; border-radius: 10px; }
#lc-app .promotion-editor-actions { display: flex; flex-wrap: wrap; gap: 8px; }
</style>
