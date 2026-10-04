<script setup>
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { call } from './api.js'
const route = useRoute()
const password = ref(''), confirmation = ref(''), busy = ref(false), error = ref(''), done = ref(false), visible = ref(false)
const key = typeof route.query.key === 'string' ? route.query.key : ''
async function submit() {
  error.value = ''
  if (password.value !== confirmation.value) { error.value = 'The passwords do not match.'; return }
  busy.value = true
  try {
    await call('customers.reset_password', { key, new_password: password.value }, true)
    password.value = ''; confirmation.value = ''; done.value = true
    window.history.replaceState(null, '', '/local-commerce#/reset-password')
  } catch (e) { error.value = e.message }
  finally { busy.value = false }
}
</script>
<template>
  <div class="store-page" style="max-width: 600px; margin: 24px auto;">
    <form class="inventory-form login-form" @submit.prevent="submit">
      <span class="eyebrow">YOUR LOCAL ACCOUNT</span><h1>{{ done ? 'Password updated' : 'Choose a new password' }}</h1>
      <template v-if="done"><p>Your password has been changed. Use your new password next time you log in.</p><a class="lc-primary" href="/local-commerce#/store">Continue to Localdot →</a></template>
      <template v-else-if="key">
        <p>Enter a strong password you haven’t used before.</p><p v-if="error" class="lc-notice" role="alert">{{ error }}</p>
        <fieldset :disabled="busy"><label>New password<input v-model="password" :type="visible ? 'text' : 'password'" autocomplete="new-password" minlength="8" maxlength="1000" required></label><label>Confirm new password<input v-model="confirmation" :type="visible ? 'text' : 'password'" autocomplete="new-password" minlength="8" maxlength="1000" required></label><button type="button" :aria-pressed="visible" @click="visible = !visible">{{ visible ? 'Hide passwords' : 'Show passwords' }}</button><button class="lc-primary login-submit">{{ busy ? 'Updating…' : 'Save new password' }}</button></fieldset>
      </template>
      <p v-else role="alert">This reset link is missing its key. Please request a new reset email.</p>
      <RouterLink v-if="!done" to="/login">Back to login / request a new link</RouterLink>
    </form>
  </div>
</template>
