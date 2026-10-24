<script setup>
import { ref, onMounted } from 'vue'
import { call } from './api.js'
import CommissionDashboard from './CommissionDashboard.vue'
import GstinLookup from './GstinLookup.vue'
const data = ref(null), busy = ref(false), error = ref(''), message = ref(''), report = ref(null)
const today = new Date().toISOString().slice(0,10)
const start = ref(today.slice(0,8)+'01'), end = ref(today)
const platformFields = [
  ['gst_clearing','Gateway retained-funds clearing','Asset'],['gst_receivable','Amounts due from shops','Asset'],
  ['gst_income','Commission income','Income'],['gst_cgst','Commission CGST payable','Liability'],
  ['gst_sgst','Commission SGST payable','Liability'],['gst_igst','Commission IGST payable','Liability'],
  ['gst_eco_cgst','Section 9(5) CGST payable','Liability'],['gst_eco_sgst','Section 9(5) SGST payable','Liability'],
  ['gst_eco_igst','Section 9(5) IGST payable','Liability'],['gst_bank','Platform bank','Asset'],
  ['gst_fee','Gateway and Easy Split expense','Expense'],['gst_fee_tax','Gateway fee GST expense','Expense'],
]
const identityFields = [['gst_legal_name','Legal name'],['gst_number','GSTIN'],['gst_state','GST state code (Goa: 30)'],['gst_address','Complete billing address']]
const settlement = ref({order:'',net:'',fee:'',fee_tax:'',utr:'',date:today,evidence:'',shop_bank:''})
const refund = ref({order:'',credit_note:'',payment_entry:''})
function applyIdentity(target, value) {
  if (String(target.gst_number || '').trim().toUpperCase() !== value.gstin) return
  Object.assign(target, { gst_number: value.gstin, gst_legal_name: value.legal_name, gst_state: value.state, gst_address: value.address })
}
function accounts(company,root) { return data.value.accounts.filter(a=>a.company===company && a.root_type===root && !['Receivable','Payable'].includes(a.account_type)) }
async function run(action) { busy.value=true;error.value='';message.value='';try { await action();message.value='Saved successfully.' } catch(e) { error.value=e.message } finally {busy.value=false} }
async function load() { data.value=await call('gst.settings') }
onMounted(()=>run(load))
function saveShop(shop) { const values=Object.fromEntries(Object.entries(shop).filter(([key])=>key.startsWith('gst_') || key.startsWith('commission_') || key==='cashfree_commission_account')); return run(()=>call('gst.save_shop',{shop:shop.name,values},true)) }
async function loadReport() { report.value=await call('gst.report',{start:start.value,end:end.value}) }
function bankAllocation() { const {shop_bank: _shopBank,...values}=settlement.value;return run(()=>call('gst.record_platform_bank',values,true)) }
</script>
<template>
  <div class="gst-settings">
    <h2>Marketplace GST</h2>
    <p>Save your setup now. Enable each shop only after your platform GSTIN, tax treatment and accounting ledgers are confirmed. Your own shop under the same Company should remain in Legacy mode.</p>
    <p v-if="error" class="lc-notice" role="alert">{{ error }}</p><p v-if="message" role="status">{{ message }}</p>
    <template v-if="data">
      <CommissionDashboard />
      <form class="admin-card" @submit.prevent="run(()=>call('gst.save_platform',{values:data.platform},true))">
        <h3>Platform identity and accounts</h3><p>Draft settings do not start collecting GST. Gateway fees and their tax are expensed here; input tax credit is not claimed automatically.</p>
        <fieldset :disabled="busy">
          <div class="form-columns">
            <label>Platform Company<select v-model="data.platform.gst_company"><option value="">Choose Company</option><option v-for="c in data.companies" :key="c">{{ c }}</option></select></label>
            <label v-for="[key,label] in identityFields" :key="key">{{ label }}<input v-model="data.platform[key]" :maxlength="key==='gst_address'?1000:140"></label><GstinLookup :number="data.platform.gst_number || ''" @apply="applyIdentity(data.platform, $event)" />
            <label>Commission SAC confirmed by your accountant<input v-model="data.platform.gst_sac" maxlength="6"></label>
            <label>Commission GST rate (%)<input v-model.number="data.platform.gst_rate" type="number" min="18" max="18"></label>
            <label>Cost center<select v-model="data.platform.gst_cost_center"><option value="">Choose</option><option v-for="c in data.cost_centers.filter(c=>c.company===data.platform.gst_company)" :key="c.name">{{ c.name }}</option></select></label>
            <label v-for="[key,label,root] in platformFields" :key="key">{{ label }}<select v-model="data.platform[key]"><option value="">Choose ledger</option><option v-for="a in accounts(data.platform.gst_company,root)" :key="a.name">{{ a.name }}</option></select></label>
          </div><h4>Native commission billing — new orders only</h4>
          <p>Use a non-stock service item with a fractional service UOM (₹1 per billing unit, allowing exact partial credits). Configure each vendor’s billing Customer and prepaid account first. Existing orders retain their original accounting. Commission is earned at delivery; GST on Cashfree advances is recorded separately. Confirm advance tax treatment and invoice configuration before enabling.</p>
          <div class="form-columns">
            <label>Receivable control account<select v-model="data.platform.commission_receivable"><option value="">Choose</option><option v-for="a in data.accounts.filter(a=>a.company===data.platform.gst_company && a.account_type==='Receivable')" :key="a.name">{{ a.name }}</option></select></label>
            <label>Commission advances liability<select v-model="data.platform.commission_deferred"><option value="">Choose</option><option v-for="a in accounts(data.platform.gst_company,'Liability')" :key="a.name">{{ a.name }}</option></select></label>
            <label>Marketplace service item<select v-model="data.platform.commission_item"><option value="">Choose</option><option v-for="i in data.service_items" :key="i.name" :value="i.name">{{ i.item_name }} · {{ i.name }}</option></select></label>
            <label>Payment terms (days)<input v-model.number="data.platform.commission_due_days" type="number" min="0" max="90"></label>
          </div>
          <label class="check-label"><input v-model="data.platform.commission_billing_enabled" type="checkbox">Enable native delivery commission billing for new GST-enabled orders</label>
          <label class="check-label"><input v-model="data.platform.commission_reminders" type="checkbox">Email monthly statements and weekly overdue reminders to configured shop emails</label>
          <button class="lc-primary">Save platform draft</button>
        </fieldset>
      </form>
      <form v-for="shop in data.shops" :key="shop.name" class="admin-card" @submit.prevent="saveShop(shop)">
        <h3>{{ shop.shop_name }}</h3><p>{{ shop.company }}</p>
        <fieldset :disabled="busy">
          <div class="form-columns">
            <label>Shop registration<select v-model="shop.gst_registration"><option>Unverified</option><option>Registered</option><option>Unregistered</option></select></label>
            <label v-for="[key,label] in identityFields" :key="key">{{ label }}<input v-model="shop[key]" :disabled="key==='gst_number' && shop.gst_registration==='Unregistered'" :maxlength="key==='gst_address'?1000:140"></label><GstinLookup :number="shop.gst_number || ''" @apply="applyIdentity(shop, $event)" />
            <label>Supply treatment<select v-model="shop.gst_mode"><option>Legacy</option><option>Exempt goods</option><option>Seller GST</option><option>Restaurant 9(5)</option></select></label>
            <label>Platform billing Customer<select v-model="shop.commission_customer"><option value="">Choose</option><option v-for="c in data.customers" :key="c.name" :value="c.name">{{ c.customer_name }} · {{ c.name }}</option></select><small>A dedicated Customer in the platform’s accounts for this vendor.</small></label>
            <label>Prepaid commission asset<select v-model="shop.commission_prepaid"><option value="">Choose</option><option v-for="a in accounts(shop.company,'Asset')" :key="a.name">{{ a.name }}</option></select></label>
            <label>Commission percentage<input v-model.number="shop.gst_commission_rate" type="number" min="0.01" max="99.99" step="0.01"></label>
            <label>Commission expense account<select v-model="shop.cashfree_commission_account"><option value="">Choose</option><option v-for="a in accounts(shop.company,'Expense')" :key="a.name">{{ a.name }}</option></select></label>
            <label>Amounts owed to platform<select v-model="shop.gst_shop_payable"><option value="">Choose liability ledger</option><option v-for="a in accounts(shop.company,'Liability')" :key="a.name">{{ a.name }}</option></select></label>
            <label v-if="shop.gst_mode==='Restaurant 9(5)'">Restaurant GST collected for ECO<select v-model="shop.gst_shop_eco_account"><option value="">Choose liability ledger</option><option v-for="a in accounts(shop.company,'Liability')" :key="a.name">{{ a.name }}</option></select></label>
          </div>
          <label class="check-label"><input v-model="shop.gst_commission_inclusive" type="checkbox">Commission percentage includes GST</label>
          <p>Commission applies to the pre-tax item value after discounts, excluding delivery. The platform bears gateway/Easy Split fees. Confirm merchant-borne fees in Cashfree before enabling Easy Split.</p>
          <p v-if="shop.gst_mode==='Restaurant 9(5)'">For eligible restaurant services only. Customer prices must exclude GST. The app adds 5% once on food and restaurant delivery charges. Remove the seller tax template. Do not mix ordinary retail goods or specified-premises services in this profile.</p>
          <label class="check-label"><input v-model="shop.gst_enabled" type="checkbox">Enable this reviewed GST model for new orders</label>
          <button class="lc-primary">Save shop GST settings</button>
        </fieldset>
      </form>
      <section class="admin-card">
        <h3>Invoices and filing workpapers</h3>
        <form @submit.prevent="run(loadReport)"><div class="form-columns"><label>From<input v-model="start" type="date" required></label><label>Through<input v-model="end" type="date" required></label></div><button :disabled="busy">Load report</button></form>
        <template v-if="report">
          <p>{{ report.note }}</p><a :href="`/api/method/local_commerce.api.gst.report?start=${start}&end=${end}&download=1`">Download CSV for your accountant</a>
          <div class="inventory-table-wrap"><table class="inventory-table"><thead><tr><th>Invoice</th><th>Type</th><th>Taxable</th><th>CGST</th><th>SGST</th><th>IGST</th><th>Return</th></tr></thead><tbody><tr v-for="r in report.rows" :key="r.invoice"><td><a :href="'/api/method/local_commerce.api.gst.invoice?name='+encodeURIComponent(r.invoice)" target="_blank" rel="noopener">{{ r.invoice }}</a><small>{{ r.date }}</small></td><td>{{ r.kind }}<small>{{ r.order.slice(0,8) }}</small></td><td>{{ r.taxable }}</td><td>{{ r.cgst }}</td><td>{{ r.sgst }}</td><td>{{ r.igst }}</td><td>{{ r.gstr1 }}<small>3B {{ r.gstr3b }}</small></td></tr></tbody></table></div>
        </template>
      </section>
      <section class="admin-card">
        <h3>Platform bank reconciliation</h3><p>Record only this order’s allocation from the completed merchant settlement statement, not the entire batch. This records accounting; it does not send money. Do not use it if you already posted the transfer in ERPNext.</p>
        <fieldset :disabled="busy">
          <div class="form-columns"><label>Full order ID<input v-model="settlement.order"></label><label>Bank UTR<input v-model="settlement.utr"></label><label>Settlement date<input v-model="settlement.date" type="date"></label><label>Net received<input v-model="settlement.net" type="number" min="0" step="0.01"></label><label>Gateway + Split fees before GST<input v-model="settlement.fee" type="number" min="0" step="0.01"></label><label>GST on fees<input v-model="settlement.fee_tax" type="number" min="0" step="0.01"></label><label>Statement/invoice allocation reference<input v-model="settlement.evidence"></label></div><button @click="bankAllocation">Record Cashfree platform receipt</button>
          <h4>COD / Manual UPI remittance</h4><p>For legacy orders, record commission and Section 9(5) GST. For native-billing orders, this action records only Section 9(5) GST; record commission receipts in the dashboard above. Use the order, UTR and date above.</p><label>Shop bank ledger<input v-model="settlement.shop_bank"></label><button @click="run(()=>call('gst.record_shop_remittance',{order:settlement.order,shop_bank:settlement.shop_bank,utr:settlement.utr,date:settlement.date},true))">Record shop remittance</button>
        </fieldset>
      </section>
      <section class="admin-card"><h3>COD / Manual UPI refund adjustments</h3><p>First submit the item-specific credit note and refund Payment Entry in ERPNext. Cashfree refunds use verified provider evidence automatically.</p><fieldset :disabled="busy"><div class="form-columns"><label>Order ID<input v-model="refund.order"></label><label>Submitted credit note<input v-model="refund.credit_note"></label><label>Submitted refund Payment Entry<input v-model="refund.payment_entry"></label></div><button @click="run(()=>call('gst.record_manual_refund',refund,true))">Record commission and GST credit notes</button></fieldset></section>
    </template>
  </div>
</template>
