<script setup>
import { computed, onMounted, provide, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { call, setCsrfToken } from './api.js'
const session = ref(null), error = ref('')
const route = useRoute(), router = useRouter()
const ownerView = computed(() => route.path === '/shop')
const canManage = computed(() => session.value && (session.value.platform_admin || session.value.memberships.some(m => ['Owner', 'Staff'].includes(m.membership_role))))
provide('session', session)
async function load() {
  error.value = ''
  try {
    session.value = await call('session.context'); setCsrfToken(session.value.csrf_token)
    if (route.path === '/') await router.replace(canManage.value ? '/shop' : '/store')
  } catch (e) { error.value = e.message }
}
onMounted(load)
</script>

<template>
  <div class="commerce-app" :class="{ 'owner-view': ownerView }">
    <header class="topbar">
      <RouterLink class="brand" to="/store">local<span>●</span><small>{{ ownerView ? 'BUSINESS' : 'YOUR NEIGHBOURHOOD, TOGETHER' }}</small></RouterLink>
      <div class="header-note"><span class="pin" aria-hidden="true">⌖</span><div><strong>{{ ownerView ? 'Your business workspace' : 'Good things start nearby' }}</strong><small>{{ ownerView ? 'A little more connected.' : 'Customer shopping opens soon' }}</small></div></div>
      <nav aria-label="Main navigation"><RouterLink v-if="canManage" :to="ownerView ? '/store' : '/shop'">{{ ownerView ? 'View storefront ↗' : 'Shop workspace ↗' }}</RouterLink><a class="account" href="/me"><span aria-hidden="true">{{ session?.user?.slice(0, 1).toUpperCase() || '○' }}</span><span>Account</span></a></nav>
    </header>
    <main>
      <div v-if="error" class="page-state" role="alert"><h1>Let's try that again.</h1><p>{{ error }}</p><button @click="load">Retry</button></div>
      <div v-else-if="!session" class="page-state" role="status"><span class="brand">local<span>●</span></span><p>Opening your neighbourhood…</p></div>
      <RouterView v-else />
    </main>
    <footer class="app-footer"><span class="brand">local<span>●</span></span><span>A little closer to your neighbourhood.</span><small>Local Commerce</small></footer>
  </div>
</template>
