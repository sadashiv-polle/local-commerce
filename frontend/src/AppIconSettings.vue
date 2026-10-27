<script setup>
import { onMounted, ref } from 'vue'
import { call } from './api.js'
const icon = ref('Wordmark'), busy = ref(true), error = ref(''), message = ref('')
const options = [
  { value: 'Original', label: 'Original icon', src: '/assets/local_commerce/icons/icon-192.png?v=20261007-white' },
  { value: 'Wordmark', label: 'Local wordmark', src: '/assets/local_commerce/icons/wordmark-192.png?v=1' },
]
onMounted(async () => {
  try { icon.value = (await call('admin.app_icon')).icon }
  catch (e) { error.value = e.message }
  finally { busy.value = false }
})
async function save() {
  busy.value = true; error.value = ''; message.value = ''
  try {
    icon.value = (await call('admin.save_app_icon', { icon: icon.value }, true)).icon
    message.value = 'App icon saved. Reopen the app before installing it.'
  } catch (e) { error.value = e.message }
  finally { busy.value = false }
}
</script>
<template>
  <section class="admin-card app-icon-settings">
    <h2>Installed app icon</h2>
    <p>Choose the home screen icon for Local on this site.</p>
    <form @submit.prevent="save">
      <fieldset :disabled="busy"><legend>App logo</legend><div class="icon-options"><label v-for="option in options" :key="option.value"><img :src="option.src" alt="" width="80" height="80"><span><input v-model="icon" type="radio" name="app-icon" :value="option.value"> {{ option.label }}</span></label></div></fieldset>
      <p>Already installed? Your device may keep the previous icon. Remove the home screen app and install it again to use the selected logo.</p>
      <p v-if="error" role="alert">{{ error }}</p><p v-if="message" role="status">{{ message }}</p>
      <button :disabled="busy">{{ busy ? 'Please wait…' : 'Save app icon' }}</button>
    </form>
  </section>
</template>
<style scoped>
.app-icon-settings { padding: 20px; margin-top: 20px; } fieldset { border: 1px solid #d9e4d8; border-radius: 12px; } .icon-options { display: flex; flex-wrap: wrap; gap: 24px; padding: 12px; } label { display: grid; justify-items: center; gap: 12px; cursor: pointer; } img { border-radius: 16px; border: 1px solid #d9e4d8; } p { line-height: 1.5; }
</style>
