<script setup>
import { inject, ref } from 'vue'
import { call, setCsrfToken } from './api.js'
const session = inject('session')
const current = ref(''), password = ref(''), confirmation = ref(''), busy = ref(false), error = ref(''), message = ref('')
async function save() {
  error.value = ''; message.value = ''
  if (password.value !== confirmation.value) { error.value = 'New passwords do not match.'; return }
  busy.value = true
  try {
    await call('session.change_password', { current_password: current.value, new_password: password.value }, true)
    current.value = ''; password.value = ''; confirmation.value = ''
    message.value = 'Password changed. Other sessions have been signed out.'
    const context = await call('session.context'); setCsrfToken(context.csrf_token)
  } catch (e) { error.value = e.message }
  finally { busy.value = false }
}
async function resetEmail() {
  busy.value = true; error.value = ''; message.value = ''
  try { message.value = (await call('session.password_reset_email', {}, true)).message }
  catch (e) { error.value = e.message }
  finally { busy.value = false }
}
</script>
<template>
  <section class="password-settings inventory-form">
    <span class="eyebrow">ACCOUNT SECURITY</span><h1>Change password</h1>
    <template v-if="session.user !== 'Guest'">
      <p>Update the password for your account. Other sessions will be signed out.</p>
      <p v-if="error" class="lc-notice" role="alert">{{ error }}</p><p v-if="message" class="success-note" role="status">{{ message }}</p>
      <form @submit.prevent="save"><fieldset :disabled="busy">
        <label>Current password<input v-model="current" type="password" autocomplete="current-password" required maxlength="1000"></label>
        <label>New password<input v-model="password" type="password" autocomplete="new-password" required minlength="8" maxlength="1000"></label>
        <label>Confirm new password<input v-model="confirmation" type="password" autocomplete="new-password" required minlength="8" maxlength="1000"></label>
        <button class="lc-primary">{{ busy ? 'Please wait…' : 'Save new password' }}</button>
      </fieldset></form>
      <section v-if="session.user !== 'Administrator'"><h2>Forgot your current password?</h2><p>Send a reset link to the email registered on your account.</p><button :disabled="busy" @click="resetEmail">Email me a reset link</button></section>
    </template>
    <RouterLink v-else to="/login">Log in to manage your password</RouterLink>
  </section>
</template>
<style scoped>
.password-settings { max-width: 520px; margin: 24px auto; padding: 24px; }
fieldset { display: grid; gap: 18px; border: 0; padding: 0; }
label { display: grid; gap: 8px; }
h1 { font-size: 26px; letter-spacing: normal; }
h2 { font-size: 18px; margin-top: 28px; }
@media (max-width: 600px) { .password-settings { margin: 12px; padding: 18px; } }
</style>
