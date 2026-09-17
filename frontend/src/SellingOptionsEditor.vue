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
  emit('update:modelValue', [...props.modelValue, { id: crypto.randomUUID(), label: '', kind: 'Count', quantity: '', estimated_weight: '', billing: 'Pieces', piece_price: '', enabled: true }])
}
function update(index, field, value) {
  emit('update:modelValue', props.modelValue.map((row, i) => i === index ? { ...row, [field]: value, ...(field === 'kind' && value !== row.kind ? { quantity: '', estimated_weight: '', billing: value === 'Weight' ? 'Weight' : 'Pieces', piece_price: '' } : {}) } : row))
}
function remove(index) { emit('update:modelValue', props.modelValue.filter((_, i) => i !== index)) }
</script>
<template>
  <section class="selling-options-editor">
    <div class="selling-options-heading"><div><h3>Selling options</h3><p>Set weight prices and piece prices for the same product.</p></div><button type="button" :disabled="disabled || uom !== 'Kg' || modelValue.length >= 20" @click="add">+ Add option</button></div>
    <p v-if="uom !== 'Kg'" class="muted">Create this product with unit Kg to use shared stock and pricing by packed weight.</p>
    <p v-else class="muted">Selling price above is per kg. Names and quantities are yours to choose; count weights are estimates for stock. Piece pricing stays fixed after packing.</p>
    <label v-if="modelValue.length">Show to customers<select :value="display" :disabled="disabled" @change="setDisplay($event.target.value)"><option>Weight</option><option>Pieces</option><option>Both</option></select></label>
    <fieldset :disabled="disabled" class="selling-options-list">
      <article v-for="(row, index) in modelValue" :key="row.id" class="selling-option-editor-row">
        <label>Option name<input :value="row.label" required maxlength="100" placeholder="e.g. Small family pack" @input="update(index, 'label', $event.target.value)"></label>
        <label>Sell by<select :value="row.kind" @change="update(index, 'kind', $event.target.value)"><option value="Count">Pieces</option><option value="Weight">Weight</option></select></label>
        <label>{{ row.kind === 'Count' ? 'Number of pieces' : 'Weight (kg)' }}<input :value="row.quantity" type="number" :min="row.kind === 'Count' ? '1' : '0.000001'" :step="row.kind === 'Count' ? '1' : 'any'" :placeholder="row.kind === 'Count' ? 'e.g. 5' : 'e.g. 0.5'" required @input="update(index, 'quantity', $event.target.value)"><small v-if="row.kind === 'Count'">Whole pieces only. Enter the estimated pack weight below.</small></label>
        <label v-if="row.kind === 'Count'">Approx. weight (kg)<input :value="row.estimated_weight" type="number" min="0.000001" step="any" placeholder="e.g. 0.5" required @input="update(index, 'estimated_weight', $event.target.value)"></label>
        <label v-if="row.kind === 'Count'">Pricing<select :value="row.billing || 'Weight'" @change="update(index, 'billing', $event.target.value)"><option value="Pieces">Per piece</option><option value="Weight">Actual weight</option></select></label>
        <label v-if="row.kind === 'Count' && row.billing === 'Pieces'">Price per piece<input :value="row.piece_price" type="number" min="0.01" step="0.01" required @input="update(index, 'piece_price', $event.target.value)"></label>
        <label class="check-label"><input :checked="row.enabled !== false" type="checkbox" @change="update(index, 'enabled', $event.target.checked)">Show this option</label>
        <button type="button" class="selling-option-remove" @click="remove(index)">Remove</button>
      </article>
    </fieldset>
  </section>
</template>
