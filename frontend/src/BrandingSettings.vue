<script setup>
import { onMounted, ref } from 'vue'
import { call, upload } from './api.js'
const config = ref(null), busy = ref(false), error = ref(''), message = ref('')
onMounted(async () => {
  try { config.value = await call('storefront.branding_settings') }
  catch (e) { error.value = e.message }
})
async function save(event) {
  const file = event?.target?.files?.[0]
  if (event && !file) return
  busy.value = true; error.value = ''; message.value = ''
  try {
    config.value = file ? await upload('storefront.upload_favicon', {}, file) : await call('storefront.reset_favicon', {}, true)
    const icon = document.querySelector('link[rel="icon"]')
    if (icon) icon.href = config.value.favicon
    message.value = 'Favicon saved. Other users will see it when they reload the app.'
  } catch (e) { error.value = e.message }
  finally { busy.value = false; if (event) event.target.value = '' }
}
</script>
<template>
  <section class="branding-settings lc-form">
    <h2>App favicon</h2>
    <p>Change the small logo in the browser tab. This does not change the installed phone app icon.</p>
    <template v-if="config">
      <img :src="config.favicon" alt="Current favicon" width="64" height="64">
      <label>Upload and save favicon<input type="file" accept="image/png,image/jpeg,image/webp,image/x-icon,image/vnd.microsoft.icon,.ico" :disabled="busy" @change="save"></label>
      <small>Square PNG, JPG, WebP or ICO, up to 2 MB. Saved automatically as a browser-ready PNG.</small>
      <button type="button" :disabled="busy" @click="save()">Restore default favicon</button>
    </template>
    <p v-if="busy" role="status">Saving favicon…</p>
    <p v-if="message" role="status">{{ message }}</p>
    <p v-if="error" class="lc-notice" role="alert">{{ error }}</p>
  </section>
</template>
<style scoped>
.branding-settings { padding-bottom: 24px; margin-bottom: 24px; border-bottom: 1px solid #dce6dc; }
.branding-settings img { border-radius: 12px; border: 1px solid #dce6dc; }
</style>
