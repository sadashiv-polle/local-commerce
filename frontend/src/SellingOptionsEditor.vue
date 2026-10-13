<script setup>
import { computed } from 'vue'
const props = defineProps({ modelValue: { type: Array, default: () => [] }, disabled: Boolean, uom: { type: String, default: '' } })
const emit = defineEmits(['update:modelValue'])
const display = computed(() => {
  const kinds = new Set(props.modelValue.filter(row => row.enabled !== false).map(row => row.kind))
  return kinds.size === 2 ? 'Both' : kinds.has('Count') ? 'Pieces' : 'Weight'
})
function setDisplay(value) {
  emit('update:modelValue', props.modelValue.map(row => ({ ...row, enabled: value === 'Both' || row.kind === (value === 'Pieces' ? 'Count' : 'Weight') })))
}
function add() {
  emit('update:modelValue', [...props.modelValue, { id: crypto.randomUUID(), label: '', kind: props.uom === 'Nos' ? 'Count' : 'Weight', quantity: '', estimated_weight: '', billing: props.uom === 'Nos' ? 'Pack' : 'Weight', piece_price: '', pack_price: '', enabled: true }])
}
function update(index, field, value) {
  emit('update:modelValue', props.modelValue.map((row, i) => i === index ? { ...row, [field]: value, ...(field === 'kind' && value !== row.kind ? { quantity: '', estimated_weight: '', billing: value === 'Weight' ? 'Weight' : 'Pieces', piece_price: '' } : {}) } : row))
}
function remove(index) { emit('update:modelValue', props.modelValue.filter((_, i) => i !== index)) }
</script>
<template>
  <section class="selling-options-editor">
    <div class="selling-options-heading"><div><h3>Selling options</h3><p>Offer fixed-price piece packs or weight options for this product.</p></div><button type="button" :disabled="disabled || !['Kg', 'Nos'].includes(uom) || modelValue.length >= 20" @click="add">+ Add option</button></div>
    <p v-if="uom === 'Nos'" class="muted">Set the whole pack price: for example, 6 Bangde for ₹100 or 15 for ₹200. Stock is counted in individual pieces; buying two 6-piece packs uses 12 pieces.</p>
    <p v-else-if="uom !== 'Kg'" class="muted">Create this product with unit Kg to use shared stock and pricing by packed weight.</p>
    <p v-else class="muted">Selling price above is per kg. For fish weight packs, enter the weighed quantity, such as 0.500, 0.530 or 0.600 kg; no packing confirmation is needed. count weights are estimates for stock. Piece pricing stays fixed after packing.</p>
    <label v-if="modelValue.length && uom === 'Kg'">Show to customers<select :value="display" :disabled="disabled" @change="setDisplay($event.target.value)"><option>Weight</option><option>Pieces</option><option>Both</option></select></label>
    <fieldset :disabled="disabled" class="selling-options-list">
      <article v-for="(row, index) in modelValue" :key="row.id" class="selling-option-editor-row">
        <label>Option name<input :value="row.label" required maxlength="100" placeholder="e.g. Small family pack" @input="update(index, 'label', $event.target.value)"></label>
        <label v-if="uom === 'Kg'">Sell by<select :value="row.kind" @change="update(index, 'kind', $event.target.value)"><option value="Count">Pieces</option><option value="Weight">Weight</option></select></label>
        <label>{{ row.kind === 'Count' ? 'Number of pieces' : 'Weight (kg)' }}<input :value="row.quantity" type="number" :min="row.kind === 'Count' ? '1' : '0.000001'" :step="row.kind === 'Count' ? '1' : 'any'" :placeholder="row.kind === 'Count' ? 'e.g. 5' : 'e.g. 0.5'" required @input="update(index, 'quantity', $event.target.value)"><small v-if="row.kind === 'Count' && uom === 'Kg'">Whole pieces only. Enter the estimated pack weight below.</small></label>
        <label v-if="row.kind === 'Count' && uom === 'Kg'">Approx. weight (kg)<input :value="row.estimated_weight" type="number" min="0.000001" step="any" placeholder="e.g. 0.5" required @input="update(index, 'estimated_weight', $event.target.value)"></label>
        <label v-if="row.kind === 'Count' && uom === 'Kg'">Pricing<select :value="row.billing || 'Weight'" @change="update(index, 'billing', $event.target.value)"><option value="Pieces">Per piece</option><option value="Weight">Actual weight</option></select></label>
        <label v-if="row.kind === 'Count' && row.billing === 'Pieces'">Price per piece<input :value="row.piece_price" type="number" min="0.01" step="0.01" required @input="update(index, 'piece_price', $event.target.value)"></label>
        <label v-if="row.billing === 'Pack'">Price for the whole pack<input :value="row.pack_price" type="number" min="0.01" step="0.01" placeholder="e.g. 100" required @input="update(index, 'pack_price', $event.target.value)"><small>This is the total pack price, not the price per fish.</small></label>
        <label class="check-label"><input :checked="row.enabled !== false" type="checkbox" @change="update(index, 'enabled', $event.target.checked)">Show this option</label>
        <button type="button" class="selling-option-remove" @click="remove(index)">Remove</button>
      </article>
    </fieldset>
  </section>
</template>
