<script setup>
import { displayTime } from './display-time.js'
defineProps({ rows: { type: Array, default: () => [] }, refunded: { type: Number, default: 0 }, paymentStatus: { type: String, default: '' } })
function when(value) { return value ? displayTime(String(value).replace('T', ' ').replace(/([+-]\d\d:\d\d|Z)$/, '')) : 'Date not supplied' }
</script>
<template>
  <section v-if="rows.length || refunded > 0 || paymentStatus === 'Refunded'" class="refund-timeline" aria-label="Refund tracking">
    <h3>Refund tracking</h3>
    <p v-if="!rows.length">Refund recorded. Detailed dates are not yet available; refresh payment status to check.</p>
    <article v-for="row in rows" :key="row.id"><strong>{{ row.label }} · {{ row.currency }} {{ Number(row.amount).toFixed(2) }}</strong><ol><li>Refund requested · {{ when(row.requested_at) }}</li><li v-for="(event, index) in row.events || []" :key="index">{{ event.label }} · Update recorded {{ when(event.at) }}</li></ol><p v-if="['FAILED', 'CANCELLED'].includes(row.status)">Contact the shop to review this refund.</p><p v-else-if="row.status === 'SUCCESS'">The payment provider has confirmed this refund. Contact the shop if the credit is not visible in your bank account.</p></article>
  </section>
</template>
<style scoped>
.refund-timeline { padding: 18px; margin: 16px 0; background: #f4f8f1; border: 1px solid #dce6dc; border-radius: 16px; } li { margin: 8px 0; } ol { padding-left: 20px; }
</style>
