<script setup>
import { onMounted, ref } from 'vue'
import { call } from './api.js'
import { clearDeliverySelection } from './address-selection.js'
const props = defineProps({ next: { type: String, default: '/store' } })
const available = ref(false), busy = ref(false), error = ref('')
onMounted(async () => {
  try { available.value = !!(await call('social_login.options')).google }
  catch { /* Email login remains available when provider discovery fails. */ }
})
async function signIn() {
  if (busy.value) return
  busy.value = true; error.value = ''
  try {
    const result = await call('social_login.google', { next_page: props.next }, true)
    clearDeliverySelection(window.sessionStorage)
    window.location.assign(result.url)
  } catch (e) { error.value = e.message; busy.value = false }
}
</script>
<template>
  <div v-if="available" class="google-sign-in">
    <button type="button" :disabled="busy" @click="signIn"><img :src="'/assets/frappe/icons/social/google.svg'" alt="" width="20" height="20">{{ busy ? 'Opening Google…' : 'Continue with Google' }}</button>
    <p v-if="error" class="lc-notice" role="alert">{{ error }}</p>
    <span class="google-divider">or use your email</span>
  </div>
</template>
<style scoped>
.google-sign-in { margin: 1rem 0; }
.google-sign-in button { display: flex; align-items: center; justify-content: center; gap: .75rem; width: 100%; min-height: 48px; padding: .75rem 1rem; border: 1px solid #747775; border-radius: .75rem; background: #fff; color: #1f1f1f; font: inherit; font-weight: 600; cursor: pointer; }
.google-sign-in button:disabled { opacity: .65; cursor: wait; }
.google-sign-in button:focus-visible { outline: 3px solid #19634b; outline-offset: 3px; }
.google-divider { display: block; margin-top: 1rem; text-align: center; color: #52645b; font-size: .875rem; }
</style>
