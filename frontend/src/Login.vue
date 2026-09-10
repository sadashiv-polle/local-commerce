<script setup>
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { authenticate, call } from './api.js'
const route = useRoute()
const username = ref(''), password = ref(''), otp = ref(''), challenge = ref(null)
const busy = ref(false), error = ref(''), message = ref(''), forgot = ref(false), showPassword = ref(false)
const candidate = route.query.next
const next = typeof candidate === 'string' && /^\/(store|shop|orders|account|delivery)(\/|\?|$)/.test(candidate) ? candidate : '/store'
async function submit() {
  busy.value = true; error.value = ''; message.value = ''
  try {
    if (forgot.value) {
      const result = await call('customers.forgot_password', { email: username.value }, true)
      message.value = result.message
      return
    }
    const result = await authenticate(challenge.value ? { otp: otp.value.trim(), tmp_id: challenge.value.tmp_id } : { usr: username.value.trim(), pwd: password.value })
    password.value = ''
    if (result.verification) { challenge.value = result; return }
    // Reload session/CSRF and resolve the Customer before returning to checkout.
    window.location.assign('/local-commerce#' + next)
    window.location.reload()
  } catch (e) { error.value = e.message }
  finally { busy.value = false }
}
function reset() { challenge.value = null; otp.value = ''; password.value = ''; error.value = ''; message.value = ''; forgot.value = !forgot.value }
</script>
<template>
  <div class="store-page login-page">
    <aside class="login-intro"><span class="eyebrow">YOUR NEIGHBOURHOOD, TOGETHER</span><h1>Welcome<br>back to local.</h1><p>Your favourite shops. Your saved cart.<br>Everything right where you left it.</p><RouterLink to="/store">← Keep browsing</RouterLink></aside>
    <form class="inventory-form login-form" @submit.prevent="submit">
      <span class="eyebrow">YOUR ACCOUNT</span><h2>{{ forgot ? 'Reset your password' : challenge ? 'Verify your login' : 'Login' }}</h2>
      <p>{{ forgot ? 'Enter your email to receive reset instructions.' : challenge ? 'Enter the code from your authenticator, email or SMS.' : 'Sign in to continue to your order.' }}</p>
      <p v-if="error" class="lc-notice" role="alert">{{ error }}</p><p v-if="message" class="success-note" role="status">{{ message }}</p>
      <fieldset :disabled="busy">
        <template v-if="!challenge"><label>Email or username<input v-model="username" required autocomplete="username" autocapitalize="none" spellcheck="false" maxlength="140"></label><template v-if="!forgot"><label>Password<input v-model="password" :type="showPassword ? 'text' : 'password'" required autocomplete="current-password" maxlength="1000"></label><button type="button" :aria-pressed="showPassword" @click="showPassword = !showPassword">{{ showPassword ? 'Hide password' : 'Show password' }}</button></template></template>
        <template v-else><p v-if="challenge.verification.method === 'OTP App' && !challenge.verification.setup" class="lc-notice">Authenticator setup is incomplete. Contact your administrator.</p><label>Verification code<input v-model="otp" required autocomplete="one-time-code" inputmode="numeric" maxlength="20"></label></template>
        <button class="lc-primary login-submit">{{ busy ? 'Please wait…' : forgot ? 'Send reset instructions' : challenge ? 'Verify and login' : 'Login' }}</button>
        <button type="button" class="login-text-button" @click="reset">{{ forgot ? 'Back to login' : 'Forgot password?' }}</button>
      </fieldset>
      <p>New customer? <RouterLink :to="{ path: '/signup', query: { next } }">Create an account →</RouterLink></p>
    </form>
  </div>
</template>
