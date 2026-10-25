<script setup>
import { onMounted, ref } from 'vue'
import { call } from './api.js'
const props = defineProps({ shop: { type: String, required: true }, modelValue: { type: Object, required: true } })
const emit = defineEmits(['update:modelValue'])
const options = ref({ accounts: [], suppliers: [] }), error = ref(''), supplierName = ref(''), busy = ref(false)
function set(field, value) {
  const next = { ...props.modelValue, [field]: value }
  if (field === 'stock_source') { next.payment_account = ''; next.supplier = '' }
  emit('update:modelValue', next)
}
async function load() {
  try { options.value = await call('owner.purchase_options', { shop: props.shop }, true) }
  catch (e) { error.value = e.message }
}
async function addSupplier() {
  busy.value = true; error.value = ''
  try {
    const name = await call('owner.add_purchase_supplier', { shop: props.shop, supplier_name: supplierName.value }, true)
    await load(); set('supplier', name); supplierName.value = ''
  } catch (e) { error.value = e.message }
  finally { busy.value = false }
}
onMounted(load)
</script>
<template>
  <div class="purchase-funding">
    <label>Receive stock as<select :value="modelValue.stock_source" required @change="set('stock_source', $event.target.value)"><option disabled value="">Choose purchase payment or adjustment</option><option value="Personal funds">Shop purchase — owner's personal money</option><option value="Shop cash or bank">Shop purchase — paid from shop cash / bank</option><option value="Supplier credit">Shop purchase — pay supplier later</option><option value="Stock adjustment">Stock count correction — not a purchase</option></select></label>
    <label v-if="modelValue.stock_source === 'Shop cash or bank'">Paid from<select :value="modelValue.payment_account || ''" required @change="set('payment_account', $event.target.value)"><option disabled value="">Select shop cash or bank ledger</option><option v-for="account in options.accounts" :key="account.name" :value="account.name">{{ account.name }} ({{ account.account_type }})</option></select><small>Records money already paid. This does not send money or initiate a bank transfer.</small></label>
    <template v-if="modelValue.stock_source === 'Supplier credit'">
      <label>Supplier<select :value="modelValue.supplier || ''" required @change="set('supplier', $event.target.value)"><option disabled value="">Select supplier for this shop</option><option v-for="supplier in options.suppliers" :key="supplier.name" :value="supplier.name">{{ supplier.supplier_name }}</option></select></label>
      <label>New supplier name<input v-model="supplierName" maxlength="140" placeholder="Name of the person or business supplying stock"></label><button type="button" :disabled="busy || supplierName.trim().length < 2" @click="addSupplier">{{ busy ? 'Adding…' : 'Add supplier' }}</button>
      <small>Records an unpaid amount against this supplier. Settle the payable through accounting when you pay.</small>
    </template>
    <small v-if="modelValue.stock_source === 'Personal funds'">The shop owns the stock; the purchase amount is recorded as owed to the owner.</small>
    <small v-if="modelValue.stock_source === 'Stock adjustment'">This affects profit through Stock Adjustment. Do not choose it for a purchase.</small>
    <small v-else>Enter purchase cost separately from selling price. This creates a stock receipt and accounting journal, not a supplier tax invoice; no input GST is claimed. Do not receive this stock again.</small>
    <p v-if="error" role="alert">{{ error }}</p>
  </div>
</template>
<style scoped>
.purchase-funding { display: grid; gap: .75rem; padding: 1rem; border: 1px solid #d7e4dc; border-radius: 12px; }
label { display: grid; gap: .4rem; }
small { display: block; line-height: 1.5; }
select, input { max-width: 100%; min-width: 0; width: 100%; }
</style>
