<script setup>
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { call } from './api.js'
import { loginUrl } from './cart.js'
const route = useRoute(), email = ref(''), fullName = ref(''), error = ref(''), message = ref(''), busy = ref(false)
const password = ref(''), confirmation = ref(''), code = ref(''), challenge = ref('')
const next = typeof route.query.next === 'string' && route.query.next.startsWith('/') && !route.query.next.startsWith('//') ? route.query.next : '/account'
async function signup() {
  busy.value = true; error.value = ''
  try {
    if (password.value !== confirmation.value) throw new Error('Passwords do not match.')
    if (!challenge.value) {
      const result = await call('customers.signup', { email: email.value, full_name: fullName.value, redirect_to: '/local-commerce#' + next }, true)
      challenge.value = result.challenge_id; message.value = result.message
    } else {
      await call('customers.complete_signup', { challenge_id: challenge.value, code: code.value, password: password.value }, true)
      password.value = ''; confirmation.value = ''
      window.location.assign('/local-commerce#' + next); window.location.reload()
    }
  }
  catch (e) { error.value = e.message }
  finally { busy.value = false }
}
</script>
<template>
  <div class="store-page auth-page">
    <RouterLink to="/store">← Continue shopping</RouterLink>
    <form class="inventory-form" @submit.prevent="signup">
      <h1>Create your account</h1><p>Verify your email and choose a password. We’ll connect your customer record automatically and keep your cart saved.</p>
      <p v-if="error" class="lc-notice" role="alert">{{ error }}</p><p v-if="message" class="success-note" role="status">{{ message }}</p>
      <fieldset :disabled="busy"><label>Full name<input v-model="fullName" :readonly="!!challenge" required maxlength="140" autocomplete="name"></label><label>Email<input v-model="email" :readonly="!!challenge" type="email" required maxlength="140" autocomplete="email"></label><label>Password<input v-model="password" type="password" required minlength="8" maxlength="1000" autocomplete="new-password"></label><label>Confirm password<input v-model="confirmation" type="password" required minlength="8" maxlength="1000" autocomplete="new-password"></label><label v-if="challenge">Email verification code<input v-model="code" required inputmode="numeric" autocomplete="one-time-code" pattern="[0-9]{6}" maxlength="6"></label><button class="lc-primary">{{ busy ? 'Please wait…' : challenge ? 'Verify & create account' : 'Send verification code' }}</button><button v-if="challenge" type="button" @click="challenge = ''; message = ''; code = ''">Use another email / Request new code</button></fieldset>
      <p>Already have an account? <a :href="loginUrl(next)">Login</a></p>
    </form>
  </div>
</template>
