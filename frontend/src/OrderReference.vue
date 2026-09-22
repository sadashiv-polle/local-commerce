<script setup>
import { ref } from 'vue'
defineProps({ orderId: { type: String, required: true } })
const message = ref('')
async function copy(value) {
  try { await navigator.clipboard.writeText(value); message.value = 'Copied' }
  catch { message.value = 'Press and hold the ID to copy it.' }
}
</script>
<template>
  <div class="order-reference"><div><span>Order ID</span><code>{{ orderId }}</code></div><button type="button" aria-label="Copy order ID" @click="copy(orderId)">Copy</button><small v-if="message" role="status">{{ message }}</small></div>
</template>
