<script setup>
import { useRoute } from 'vue-router'
import { loginUrl } from './cart.js'
const route = useRoute()
</script>
<template>
  <section class="inventory-form">
    <h2>Sign in to place your order</h2><p>Your cart is saved on this device.</p>
    <div class="auth-choices"><div><strong>Already have an account?</strong><a class="primary" :href="loginUrl(route.fullPath)">Login</a></div><div><strong>New customer?</strong><RouterLink class="primary" :to="{ path: '/signup', query: { next: route.fullPath } }">Sign Up / Create Account</RouterLink></div></div>
  </section>
</template>
