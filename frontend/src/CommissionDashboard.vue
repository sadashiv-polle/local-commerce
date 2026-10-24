<script setup>
import { computed, inject, ref, watch } from 'vue'
import { call } from './api.js'
const props = defineProps({ shop: { type: String, default: '' } })
const session = inject('session')
const today = new Date().toLocaleDateString('en-CA')
const start = ref(today.slice(0,8)+'01'), end = ref(today), method = ref(''), order = ref('')
const data = ref(null), busy = ref(false), error = ref(''), message = ref(''), history = ref(null)
const selected = ref(null), amount = ref(''), bank = ref(''), shopBank = ref(''), utr = ref(''), date = ref(today)
const admin = computed(()=>session?.value?.platform_admin)
const filters = computed(()=>({ start:start.value,end:end.value,shop:props.shop,method:method.value,order:order.value.trim() }))
const download = computed(()=>'/api/method/local_commerce.api.commissions.report?'+new URLSearchParams({...filters.value,download:1}))
const currency = value=>value == null ? '—' : new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR'}).format(Number(value))
let revision = 0
async function load() {
  const current = ++revision
  busy.value=true; error.value=''; data.value=null
  try { const result=await call('commissions.report',filters.value); if(current===revision) data.value=result }
  catch(e) { if(current===revision) error.value=e.message }
  finally { if(current===revision) busy.value=false }
}
async function showHistory(row) {
  error.value=''
  try { history.value={invoice:row.invoice,...await call('commissions.history',{document:row.document})} }
  catch(e) { error.value=e.message }
}
async function receive() {
  busy.value=true;error.value='';message.value=''
  try {
    const result=await call('commissions.receive',{document:selected.value.document,amount:amount.value,bank:bank.value,shop_bank:shopBank.value,utr:utr.value,date:date.value},true)
    message.value='Payment recorded: '+result.payment_entry; selected.value=null;utr.value='';await load()
  } catch(e) { error.value=e.message }
  finally {busy.value=false}
}
watch(()=>props.shop,()=>{selected.value=null;history.value=null;load()},{immediate:true})
</script>
<template>
  <section class="commission-panel admin-card">
    <h3>Commission &amp; statements</h3>
    <p>Delivered orders, service charges and invoice balances. Monthly statements summarise existing invoices; they do not charge the shop again.</p>
    <form class="commission-filters" @submit.prevent="load">
      <label>From<input v-model="start" type="date" required></label><label>Through<input v-model="end" type="date" required></label>
      <label>Payment method<select v-model="method"><option value="">All methods</option><option>Cashfree</option><option>Cash on Delivery</option><option>Manual UPI</option></select></label>
      <label>Order ID<input v-model="order" placeholder="Full order reference"></label><button :disabled="busy">{{ busy ? 'Loading…' : 'Apply filters' }}</button>
    </form>
    <p v-if="error" class="lc-notice" role="alert">{{ error }}</p><p v-if="message" role="status">{{ message }}</p>
    <template v-if="data">
      <div class="commission-totals">
        <article><small>Completed orders</small><strong>{{ data.totals.orders }}</strong></article>
        <article><small>Online sales</small><strong>{{ currency(data.totals.online_sales) }}</strong></article>
        <article><small>COD sales</small><strong>{{ currency(data.totals.cod_sales) }}</strong></article>
        <article><small>Commission before GST</small><strong>{{ currency(data.totals.commission) }}</strong></article>
        <article><small>Commission GST</small><strong>{{ currency(data.totals.gst) }}</strong></article>
        <article><small>Native invoice balance</small><strong>{{ currency(data.totals.outstanding) }}</strong></article>
        <article><small>COD commission due</small><strong>{{ currency(data.totals.cod_outstanding) }}</strong></article>
        <article><small>Online commission in verified bank allocations</small><strong>{{ currency(data.totals.online_bank_received) }}</strong></article>
        <article><small>Overdue</small><strong>{{ currency(data.totals.overdue) }}</strong></article>
      </div>
      <p>{{ data.note }}</p><details v-if="admin"><summary>Shop-wise native balances</summary><p v-for="(balance,name) in data.balances" :key="name">{{ balance.name }} · {{ currency(balance.amount) }}</p></details><a :href="download">Download statement CSV</a><p v-if="admin"><a :href="'/api/method/local_commerce.api.commissions.advance_workpaper?'+new URLSearchParams({start,end,download:1})">Download advance GST adjustments</a> · <a :href="'/api/method/local_commerce.api.commissions.tcs_review?'+new URLSearchParams({start,end})">TCS classification review</a></p><p v-if="admin">TCS registration, eligible supplies and rates need separate configuration. The review download does not calculate TCS or file GSTR-8.</p>
      <p v-if="!data.rows.length">No commission documents in this period.</p>
      <div v-else class="inventory-table-wrap">
        <table class="inventory-table">
          <thead><tr><th>Shop / order</th><th>Invoice</th><th>Method</th><th>Commission + GST</th><th>Outstanding</th><th>Actions</th></tr></thead>
          <tbody>
            <tr v-for="r in data.rows" :key="r.document">
              <td>{{ r.shop_name }}<small>{{ r.order.slice(0,8) }} · {{ r.date }}</small></td>
              <td><a :href="'/api/method/local_commerce.api.gst.invoice?name='+encodeURIComponent(r.document)" target="_blank" rel="noopener">{{ r.invoice || r.document }}</a><small>{{ r.kind }} · {{ r.rate }}%</small></td>
              <td>{{ r.method }}</td><td>{{ currency(r.total) }}<small>GST {{ currency(r.gst) }}</small></td><td>{{ currency(r.outstanding) }}<small :class="{'commission-overdue':r.overdue}">{{ r.overdue ? 'Overdue' : r.status }} {{ r.due_date }}</small></td>
              <td><button type="button" @click="showHistory(r)">History</button><button v-if="admin && r.invoice && r.kind==='Commission Invoice' && r.method!=='Cashfree' && Number(r.outstanding)>0" type="button" @click="selected=r; amount=r.outstanding">Record receipt</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
    <section v-if="history" class="commission-detail"><h4>Payment history · {{ history.invoice }}</h4><p>{{ history.note }}</p><p v-if="!history.payments.length">No native Payment Entries recorded.</p><p v-for="p in history.payments" :key="p.name">{{ p.posting_date }} · {{ p.name }} · {{ p.reference_no }} · {{ currency(p.allocated_amount) }}</p><button @click="history=null">Close history</button></section>
    <form v-if="selected && admin" class="commission-detail" @submit.prevent="receive">
      <h4>Record received payment · {{ selected.invoice }}</h4><p>Record only a completed transfer. This creates accounting entries in both Companies; it does not transfer money. Do not record a receipt already posted in ERPNext.</p><div class="commission-filters">
        <label>Amount<input v-model="amount" type="number" min="0.01" :max="selected.outstanding" step="0.01" required></label>
        <label>Platform bank ledger<input v-model="bank" required></label><label>Shop bank ledger<input v-model="shopBank" required></label>
        <label>Bank UTR<input v-model="utr" maxlength="140" required></label><label>Received on<input v-model="date" type="date" :max="today" required></label>
      </div><button class="lc-primary" :disabled="busy">Record receipt</button><button type="button" :disabled="busy" @click="selected=null">Cancel</button>
    </form>
  </section>
</template>
<style scoped>
.commission-panel{min-width:0}.commission-filters{display:flex;flex-wrap:wrap;align-items:end;gap:1rem;margin:1rem 0}.commission-filters label{display:grid;gap:.4rem;flex:1 1 160px}.commission-filters input,.commission-filters select{width:100%;min-height:44px}.commission-totals{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:.75rem;margin:1rem 0}.commission-totals article{padding:1rem;background:#f1f6ef;border-radius:12px;display:grid;gap:.5rem}.commission-totals strong{font-size:1.15rem}.commission-detail{padding:1rem;margin-top:1rem;border:1px solid #d8e5da;border-radius:12px}.commission-panel td small{display:block;margin-top:.35rem}.commission-panel td button{display:block;margin:.25rem 0;min-height:40px}.commission-overdue{color:#a13024}@media(max-width:600px){.commission-totals{grid-template-columns:repeat(2,minmax(0,1fr))}.commission-totals article{padding:.8rem}.commission-totals strong{font-size:1rem}.commission-filters label{flex-basis:100%}}
</style>
