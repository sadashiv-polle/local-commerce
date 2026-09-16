<script setup>
import { inject } from 'vue'
const session = inject('session')
</script>
<template>
  <nav v-if="session.platform_admin" class="admin-workspace-tabs" aria-label="Admin workspace"><RouterLink to="/admin">Master dashboard</RouterLink><RouterLink to="/shop" :aria-current="$route.path === '/shop' ? 'page' : undefined">My shops</RouterLink><RouterLink to="/store-settings" :aria-current="$route.path === '/store-settings' ? 'page' : undefined">Storefront settings</RouterLink></nav>
</template>
