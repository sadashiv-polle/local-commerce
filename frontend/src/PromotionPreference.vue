<script setup>
import { onMounted, ref } from 'vue'
import { call } from './api.js'
const enabled = ref(false), busy = ref(true), error = ref('')
onMounted(async () => {
  try { enabled.value = (await call('campaigns.preference')).enabled }
  catch (e) { error.value = e.message }
  finally { busy.value = false }
})
async function update(event) {
  const checked = event.target.checked
  busy.value = true; error.value = ''
  try { enabled.value = (await call('campaigns.set_preference', { enabled: checked ? 1 : 0 }, true)).enabled }
  catch (e) { event.target.checked = enabled.value; error.value = e.message }
  finally { busy.value = false }
}
</script>
<template>
  <section class="lc-panel">
    <h2>Product updates & offers</h2>
    <label><input type="checkbox" :checked="enabled" :disabled="busy" @change="update"> Send me promotional notifications</label>
    <p>Enabling app notifications includes shop and product updates, once a day while a shop is open. Turn this off any time. Your order and delivery alerts stay on.</p>
    <p>To receive these on your phone, also enable the app’s phone notifications.</p>
    <p v-if="error" role="alert">{{ error }}</p>
  </section>
</template>
