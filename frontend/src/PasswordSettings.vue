<script setup>
import { inject, ref } from 'vue'
import { call, setCsrfToken } from './api.js'
const session = inject('session')
const visible = ref({ current: false, password: false, confirmation: false })
const current = ref(''), password = ref(''), confirmation = ref(''), busy = ref(false), error = ref(''), message = ref('')
async function save() {
  error.value = ''; message.value = ''
  if (password.value !== confirmation.value) { error.value = 'New passwords do not match.'; return }
  busy.value = true
  try {
    await call('session.change_password', { current_password: current.value, new_password: password.value }, true)
    current.value = ''; password.value = ''; confirmation.value = ''
    visible.value = { current: false, password: false, confirmation: false }
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
      <form @submit.prevent="save">
        <fieldset :disabled="busy">
          <div><label for="security-current">Current password</label><div class="password-input"><input id="security-current" v-model="current" :type="visible.current ? 'text' : 'password'" autocomplete="current-password" required maxlength="1000"><button type="button" class="password-eye" :aria-label="(visible.current ? 'Hide' : 'Show') + ' current password'" :aria-pressed="visible.current" @click="visible.current = !visible.current"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" /><circle cx="12" cy="12" r="3" /><path v-if="visible.current" d="m3 3 18 18" /></svg></button></div></div>
          <div><label for="security-password">New password</label><div class="password-input"><input id="security-password" v-model="password" :type="visible.password ? 'text' : 'password'" autocomplete="new-password" required minlength="8" maxlength="1000"><button type="button" class="password-eye" :aria-label="(visible.password ? 'Hide' : 'Show') + ' new password'" :aria-pressed="visible.password" @click="visible.password = !visible.password"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" /><circle cx="12" cy="12" r="3" /><path v-if="visible.password" d="m3 3 18 18" /></svg></button></div></div>
          <div><label for="security-confirmation">Confirm new password</label><div class="password-input"><input id="security-confirmation" v-model="confirmation" :type="visible.confirmation ? 'text' : 'password'" autocomplete="new-password" required minlength="8" maxlength="1000"><button type="button" class="password-eye" :aria-label="(visible.confirmation ? 'Hide' : 'Show') + ' confirm new password'" :aria-pressed="visible.confirmation" @click="visible.confirmation = !visible.confirmation"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" /><circle cx="12" cy="12" r="3" /><path v-if="visible.confirmation" d="m3 3 18 18" /></svg></button></div></div>
          <button class="lc-primary">{{ busy ? 'Please wait…' : 'Save new password' }}</button>
        </fieldset>
      </form>
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
.password-input { position: relative; margin-top: 8px; }
.password-input input { width: 100%; padding-right: 52px; box-sizing: border-box; }
.password-input .password-eye { position: absolute; right: 4px; top: 50%; transform: translateY(-50%); display: grid; place-items: center; width: 44px; height: 44px; min-height: 44px; padding: 10px; background: transparent; border: 0; color: #17654d; }
.password-eye svg { width: 22px; height: 22px; }
.password-eye:focus-visible { outline: 2px solid #17654d; outline-offset: -2px; border-radius: 8px; }
</style>
