<script setup>
const props = defineProps({ modelValue: { type: Array, default: () => [] }, disabled: Boolean, uom: { type: String, default: '' } })
const emit = defineEmits(['update:modelValue'])
function add() {
  emit('update:modelValue', [...props.modelValue, { id: crypto.randomUUID(), label: '', kind: 'Count', quantity: '', estimated_weight: '' }])
}
function update(index, field, value) {
  emit('update:modelValue', props.modelValue.map((row, i) => i === index ? { ...row, [field]: value } : row))
}
function remove(index) { emit('update:modelValue', props.modelValue.filter((_, i) => i !== index)) }
</script>
<template>
  <section class="selling-options-editor">
    <div class="selling-options-heading"><div><h3>Selling options</h3><p>Offer counts or weights from one product. Final price uses the actual packed weight.</p></div><button type="button" :disabled="disabled || uom !== 'Kg' || modelValue.length >= 20" @click="add">+ Add option</button></div>
    <p v-if="uom !== 'Kg'" class="muted">Create this product with unit Kg to use shared stock and pricing by packed weight.</p>
    <p v-else class="muted">Selling price above is per kg. Names and quantities are yours to choose; count weights are estimates.</p>
    <fieldset :disabled="disabled" class="selling-options-list">
      <article v-for="(row, index) in modelValue" :key="row.id" class="selling-option-editor-row">
        <label>Option name<input :value="row.label" required maxlength="100" placeholder="e.g. Small family pack" @input="update(index, 'label', $event.target.value)"></label>
        <label>Sell by<select :value="row.kind" @change="update(index, 'kind', $event.target.value)"><option>Count</option><option>Weight</option></select></label>
        <label>{{ row.kind === 'Count' ? 'Number of pieces' : 'Weight (kg)' }}<input :value="row.quantity" type="number" min="0.000001" :step="row.kind === 'Count' ? '1' : '0.001'" required @input="update(index, 'quantity', $event.target.value)"></label>
        <label v-if="row.kind === 'Count'">Approx. weight (kg)<input :value="row.estimated_weight" type="number" min="0.000001" step="0.001" required @input="update(index, 'estimated_weight', $event.target.value)"></label>
        <button type="button" class="selling-option-remove" @click="remove(index)">Remove</button>
      </article>
    </fieldset>
  </section>
</template>
