<script setup>
import { computed } from 'vue'
import { cartKey } from './cart.js'
const props = defineProps({ product: { type: Object, required: true }, cart: { type: Object, required: true }, disabled: Boolean })
const emit = defineEmits(['change'])
const choices = computed(() => (props.product.selling_options || []).map(option => ({
  ...props.product, option_id: option.id, option_label: option.label,
  stock_per_pack: Number(option.estimated_weight), stock_available: Number(props.product.available),
  rate: option.billing === 'Pieces' ? Number(option.piece_price) * Number(option.quantity) : props.product.rate == null ? null : Number(props.product.rate) * Number(option.estimated_weight),
  base_rate: props.product.rate, uom: option.label,
  available: Math.floor(Number(props.product.available) / Number(option.estimated_weight)),
  option_kind: option.kind, option_quantity: Number(option.quantity), estimated: option.billing !== 'Pieces' && !(props.product.preweighed_weights && option.kind === 'Weight'), billing: option.billing,
})))
function money(value) { return value == null ? 'Price coming soon' : new Intl.NumberFormat(undefined, { style: 'currency', currency: props.product.currency }).format(value) }
</script>
<template>
  <section class="selling-option-picker" aria-label="Choose count or weight">
    <h3>Choose your option</h3><p class="muted"><template v-if="choices.some(choice => choice.estimated)">Weight-priced options use actual packed weight at {{ money(product.rate) }} / kg. </template><template v-if="product.preweighed_weights && choices.some(choice => choice.option_kind === 'Weight')">Weight packs use the listed weight at {{ money(product.rate) }} / kg. No extra weighing step.</template><template v-if="choices.some(choice => choice.billing === 'Pieces')">Piece prices stay fixed after packing.</template></p>
    <article v-for="choice in choices" :key="choice.option_id" class="selling-option-choice" :class="{ selected: cart[cartKey(choice)] }">
      <div><strong>{{ choice.option_label }}</strong><small>{{ choice.option_kind === 'Count' ? `${choice.option_quantity} pieces` : `${choice.option_quantity} kg` }}</small><b>{{ choice.estimated ? '≈ ' : '' }}{{ money(choice.rate) }}</b></div>
      <div v-if="cart[cartKey(choice)]" class="quantity-stepper"><button type="button" :disabled="disabled" :aria-label="`Remove one ${choice.option_label}`" @click="emit('change', choice, -1)">−</button><strong>{{ cart[cartKey(choice)].quantity }}</strong><button type="button" :disabled="disabled || cart[cartKey(choice)].quantity >= choice.available" :aria-label="`Add one ${choice.option_label}`" @click="emit('change', choice, 1)">+</button></div>
      <button v-else type="button" class="add-item-button" :disabled="disabled || choice.available < 1 || choice.rate == null" @click="emit('change', choice, 1)">{{ choice.available > 0 ? 'ADD' : 'Sold out' }}</button>
    </article>
  </section>
</template>
