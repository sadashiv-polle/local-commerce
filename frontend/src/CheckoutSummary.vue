<script setup>
import { computed } from 'vue'
const props = defineProps({
  address: { type: Object, default: () => ({}) }, items: { type: Array, default: () => [] },
  sellingLines: { type: Array, default: () => [] },
  currency: { type: String, default: 'INR' }, subtotal: { type: Number, default: 0 },
  delivery: { type: Number, default: 0 }, discount: { type: Number, default: 0 },
  taxes: { type: Number, default: null }, total: { type: Number, default: 0 },
  estimated: Boolean, updating: Boolean, needsLocation: Boolean,
  payment: { type: String, default: '' },
})
const destination = computed(() => [props.address.line1, props.address.city, props.address.postal_code].filter(Boolean).join(', '))
function money(value) { return new Intl.NumberFormat(undefined, { style: 'currency', currency: props.currency }).format(value) }
</script>
<template>
  <section class="checkout-summary" aria-label="Order summary" :aria-busy="updating">
    <header><span class="eyebrow">CHECK YOUR ORDER</span><h3>Order summary</h3></header>
    <div class="checkout-summary-address"><strong>Delivering to {{ address.recipient || 'your address' }}</strong><p>{{ destination || 'Enter your delivery address above.' }}</p><small v-if="address.phone">{{ address.phone }}</small><p v-if="address.delivery_instructions">{{ address.delivery_instructions }}</p></div>
    <ul class="checkout-summary-items"><li v-for="(item, index) in items" :key="index"><div><strong>{{ item.item_name || item.name }}</strong><small>{{ item.quantity }} {{ item.uom }}</small><small v-if="item.option_label">{{ item.option_label }}</small><small v-if="sellingLines[index]?.option_id">{{ sellingLines[index].label }} × {{ sellingLines[index].packs }} · {{ sellingLines[index].actual_weight == null ? 'Estimated weight' : 'Packed weight' }} {{ sellingLines[index].actual_weight ?? sellingLines[index].estimated_weight }} kg</small></div><span>{{ money(item.amount ?? item.rate * item.quantity) }}</span></li></ul>
    <dl><div><dt>Items subtotal</dt><dd>{{ money(subtotal) }}</dd></div><div><dt>Delivery fee</dt><dd>{{ needsLocation ? 'Choose location' : delivery === 0 ? 'Free' : money(delivery) }}</dd></div><div><dt>Order discount</dt><dd>{{ discount > 0 ? '−' + money(discount) : 'None applied' }}</dd></div><div><dt>Additional taxes & adjustments</dt><dd>{{ taxes == null ? 'Confirmed after order request' : money(taxes) }}</dd></div><div class="checkout-summary-total"><dt>{{ estimated ? 'Estimated total' : 'Order total' }}</dt><dd>{{ updating ? 'Updating…' : needsLocation ? 'Choose location' : money(total) }}</dd></div></dl>
    <p v-if="estimated" class="checkout-summary-note">Taxes and any final weight adjustments are confirmed on your order before payment.</p>
    <p v-if="payment" class="checkout-summary-note">Payment: <strong>{{ payment }}</strong></p>
  </section>
</template>
<style scoped>
.checkout-summary { margin: 20px 0; padding: 20px; border: 1px solid #ccdfd2; border-radius: 20px; background: #f8fbf6; color: #1b3c2c; }
.checkout-summary h3 { margin: 5px 0 16px; font-size: 22px; }
.checkout-summary-address { padding: 14px; background: white; border-radius: 12px; overflow-wrap: anywhere; }
.checkout-summary-address p { margin: 5px 0; }
.checkout-summary-items { margin: 14px 0; padding: 0; list-style: none; }
.checkout-summary-items li, dl > div { display: flex; justify-content: space-between; align-items: start; gap: 16px; padding: 10px 0; }
.checkout-summary-items li { border-bottom: 1px solid #dce6dc; }
.checkout-summary-items li > div { min-width: 0; overflow-wrap: anywhere; }
.checkout-summary-items small { display: block; margin-top: 4px; color: #627568; }
.checkout-summary-items span { white-space: nowrap; }
dl { margin: 0; } dd { margin: 0; text-align: right; font-weight: 650; }
.checkout-summary-total { border-top: 1px solid #ccdfd2; margin-top: 8px; font-size: 21px; font-weight: 750; }
.checkout-summary-note { margin: 10px 0 0; font-size: 13px; line-height: 1.5; color: #627568; }
@media(max-width:480px) { .checkout-summary { padding: 14px; border-radius: 16px; } dl > div { gap: 10px; } }
</style>
