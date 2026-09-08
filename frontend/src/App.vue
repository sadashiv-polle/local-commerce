<script setup>
import { onMounted, provide, ref } from 'vue'
import { call, setCsrfToken } from './api.js'
const session = ref(null), error = ref('')
provide('session', session)
async function load() {
  error.value = ''
  try { session.value = await call('session.context'); setCsrfToken(session.value.csrf_token) }
  catch (e) { error.value = e.message }
}
onMounted(load)
</script>

<template>
  <div class="lc-shell">
    <header class="lc-header">
      <a class="lc-brand" href="/local-commerce">LC <span>Local Commerce</span></a>
      <a href="/me">My account</a>
    </header>
    <main>
      <p class="lc-eyebrow">YOUR LOCAL BUSINESS NETWORK</p>
      <h1>Workspace</h1>
      <div v-if="error" role="alert" class="lc-notice">{{ error }} <button @click="load">Retry</button></div>
      <p v-else-if="!session" role="status">Loading your workspace…</p>
      <template v-else>
        <p class="lc-muted">Signed in as {{ session.user }}</p>
        <div class="lc-tags"><span v-for="role in session.roles" :key="role">{{ role.replace('LC ', '') }}</span></div>
        <RouterView />
      </template>
    </main>
    <footer>Local Commerce · Foundation release 0.1.0</footer>
  </div>
</template>
