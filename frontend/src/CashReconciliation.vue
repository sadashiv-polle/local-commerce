<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { call } from './api.js'

const props = defineProps({ shop: { type: String, required: true }, editable: Boolean })
const collections = ref([]), view = ref('pending'), start = ref(0)
const loading = ref(false), error = ref(''), busy = ref('')
const reconcileDialog = ref(null), selected = ref(null), ownerNote = ref(''), dialogError = ref('')

const pageTotals = computed(() => {
  const totals = {}
  for (const row of collections.value) {
    totals[row.currency] ||= { expected: 0, collected: 0 }
    totals[row.currency].expected += Number(row.expected_amount)
    totals[row.currency].collected += Number(row.collected_amount)
  }
  return Object.entries(totals).map(([currency, amounts]) => ({ currency, ...amounts }))
})

function money(value, currency) { return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(value) }
function when(value) { return value ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : '' }
async function load(delta = 0) {
  start.value = Math.max(0, start.value + delta); loading.value = true; error.value = ''
  try { collections.value = await call('orders.cod_collections', { shop: props.shop, view: view.value, start: start.value }) }
  catch (e) { error.value = e.message }
  finally { loading.value = false }
}
async function switchView(target) { view.value = target; start.value = 0; await load() }
function requestReconcile(row) { selected.value = row; ownerNote.value = ''; dialogError.value = ''; reconcileDialog.value.showModal() }
function cancelReconcile() { reconcileDialog.value.close(); selected.value = null; ownerNote.value = ''; dialogError.value = '' }
async function confirmReconcile() {
  if (selected.value.variance && ownerNote.value.trim().length < 3) { dialogError.value = 'Add a note explaining how the cash difference was settled.'; return }
  const name = selected.value.name
  reconcileDialog.value.close(); selected.value = null; busy.value = name; error.value = ''
  try {
    await call('orders.reconcile_cod', { collection: name, owner_note: ownerNote.value.trim() }, true)
    await load()
  } catch (e) { error.value = e.message }
  finally { busy.value = ''; ownerNote.value = '' }
}
watch(() => props.shop, () => { start.value = 0; load() })
onMounted(load)
</script>

<template>
  <section class="cash-page">
    <header class="cash-heading"><div><span class="eyebrow">CASH CONTROL</span><h2>Cash handover</h2><p>Match the rider’s Cash on Delivery collections with the money handed to your shop.</p></div><button :disabled="loading || busy" @click="load()">Refresh</button></header>
    <div class="cash-tabs" role="tablist" aria-label="Cash collection lists"><button role="tab" :aria-selected="view === 'pending'" @click="switchView('pending')">Awaiting handover</button><button role="tab" :aria-selected="view === 'history'" @click="switchView('history')">Reconciled history</button></div>
    <div v-if="pageTotals.length" class="cash-totals">
      <article v-for="total in pageTotals" :key="total.currency"><span>{{ view === 'pending' ? 'DUE FROM RIDERS' : 'COLLECTED' }}</span><strong>{{ money(total.collected, total.currency) }}</strong><small>Expected {{ money(total.expected, total.currency) }} · this page</small></article>
    </div>
    <p v-if="error" class="lc-notice" role="alert">{{ error }}</p>
    <p v-if="loading" role="status">Loading cash records…</p>
    <div v-else-if="!collections.length" class="lc-empty cash-empty"><div aria-hidden="true">✓</div><h3>{{ view === 'pending' ? 'No cash waiting' : 'No reconciliation history yet' }}</h3><p>{{ view === 'pending' ? 'All recorded rider cash has been handed over.' : 'Completed handovers will appear here.' }}</p></div>
    <div v-else class="cash-list">
      <article v-for="row in collections" :key="row.name" class="cash-card">
        <header><div><span class="eyebrow">{{ row.order }}</span><h3>{{ row.delivery_name }}</h3><p>{{ when(row.collected_at) }}</p></div><span class="status-pill">{{ row.status }}</span></header>
        <dl class="cash-amounts"><div><dt>Expected</dt><dd>{{ money(row.expected_amount, row.currency) }}</dd></div><div><dt>Rider received</dt><dd>{{ money(row.collected_amount, row.currency) }}</dd></div><div :class="{ variance: row.variance }"><dt>Difference</dt><dd>{{ row.variance > 0 ? '+' : '' }}{{ money(row.variance, row.currency) }}</dd></div></dl>
        <p v-if="row.driver_note" class="cash-note"><strong>Rider note</strong>{{ row.driver_note }}</p>
        <p v-if="row.owner_note" class="cash-note"><strong>Owner note</strong>{{ row.owner_note }}</p>
        <footer v-if="row.status === 'Awaiting Handover'"><span>Confirm only after receiving the cash.</span><button v-if="editable" class="lc-primary" :disabled="!!busy" @click="requestReconcile(row)">{{ busy === row.name ? 'Saving…' : 'Confirm handover' }}</button></footer>
        <footer v-else><span>Confirmed by {{ row.reconciled_by }} · {{ when(row.reconciled_at) }}</span></footer>
      </article>
    </div>
    <div class="lc-pagination"><button :disabled="!start || loading || busy" @click="load(-20)">Previous</button><span>Page {{ start / 20 + 1 }}</span><button :disabled="collections.length < 20 || loading || busy" @click="load(20)">Next</button></div>

    <dialog ref="reconcileDialog" class="payment-dialog" aria-labelledby="reconcile-title">
      <div class="cash-symbol" aria-hidden="true">✓</div><span class="eyebrow">OWNER CONFIRMATION</span><h2 id="reconcile-title">Confirm cash handover</h2>
      <template v-if="selected"><p>You are confirming receipt of <strong>{{ money(selected.collected_amount, selected.currency) }}</strong> from {{ selected.delivery_name }} for {{ selected.order }}.</p><p v-if="selected.variance" class="variance-note" :class="{ shortage: selected.variance < 0 }">Order difference: {{ selected.variance > 0 ? '+' : '' }}{{ money(selected.variance, selected.currency) }}</p></template>
      <label class="cash-field">Reconciliation note <small>{{ selected?.variance ? 'Required for a cash difference' : 'Optional' }}</small><textarea v-model="ownerNote" maxlength="500" placeholder="Add handover details"></textarea></label>
      <p v-if="dialogError" class="lc-notice" role="alert">{{ dialogError }}</p>
      <p class="muted">This creates the ERPNext Payment Entry and keeps an audit record. The action cannot be undone here.</p>
      <div class="logout-actions"><button @click="cancelReconcile">Go back</button><button class="logout-confirm" @click="confirmReconcile">Cash received by shop</button></div>
    </dialog>
  </section>
</template>
