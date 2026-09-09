<script setup>
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { call } from './api.js'
import { loginUrl } from './cart.js'
const route = useRoute(), email = ref(''), fullName = ref(''), error = ref(''), message = ref(''), busy = ref(false)
const next = typeof route.query.next === 'string' && route.query.next.startsWith('/') && !route.query.next.startsWith('//') ? route.query.next : '/account'
async function signup() {
  busy.value = true; error.value = ''
  try { const result = await call('customers.signup', { email: email.value, full_name: fullName.value, redirect_to: '/local-commerce#' + next }, true); message.value = result.message }
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
      <fieldset v-if="!message" :disabled="busy"><label>Full name<input v-model="fullName" required maxlength="140" autocomplete="name"></label><label>Email<input v-model="email" type="email" required maxlength="140" autocomplete="email"></label><button class="lc-primary">{{ busy ? 'Sending…' : 'Create account' }}</button></fieldset>
      <p>Already have an account? <a :href="loginUrl(next)">Login</a></p>
    </form>
  </div>
</template>
