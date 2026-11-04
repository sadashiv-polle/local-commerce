<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { call } from './api.js'
import { campaignSuggestions, orderCampaignSuggestions } from './campaign-copy.js'
const shops = ref([]), products = ref([]), rows = ref([])
const shop = ref(''), item = ref(''), title = ref(''), message = ref(''), saved = ref(''), sendAt = ref('')
const templates = ref([]), templateSettings = ref({ disabled: [], fish_tags: {}, script: 'latin', automatic: false, start: 8, end: 19 })
const style = ref('existing'), script = ref('latin'), templateId = ref(''), audience = ref('All'), period = ref('')
const eligibleTemplates = computed(() => templates.value.filter(row => !templateSettings.value.disabled.includes(row.id) &&
  templateSettings.value.fish_tags[item.value] && (row.fish === 'fish' || row.fish === templateSettings.value.fish_tags[item.value])))
const selectedTemplate = computed(() => templates.value.find(row => row.id === templateId.value))
watch([style, script, item], () => { templateId.value = ''; suggestionCycle = null; suggestionIndex = 0 })
watch([templateId, script], () => {
  if (selectedTemplate.value) {
    title.value = selectedTemplate.value[script.value].title
    message.value = selectedTemplate.value[script.value].message
  }
})
async function saveTemplateSettings() {
  await action(async () => {
    templateSettings.value = await call('campaigns.template_settings', { value: JSON.stringify(templateSettings.value) }, true)
    suggestionCycle = null; suggestionIndex = 0
    notice.value = 'Template settings saved.'
  })
}
const busy = ref(false), error = ref(''), notice = ref('')
const product = computed(() => products.value.find(row => row.name === item.value))
const shopName = computed(() => shops.value.find(row => row.name === shop.value)?.shop_name || '')
let generation = 0, suggestionIndex = 0, suggestionCycle = null
watch([shop, item], () => { suggestionIndex = 0; suggestionCycle = null })
watch([shop, item, title, message, style, script, templateId, audience, period], () => { saved.value = '' })
watch(shop, async value => {
  const current = ++generation
  item.value = ''; products.value = []
  try { const result = await call('campaigns.options', { shop: value }); if (current === generation) products.value = result.products }
  catch (e) { if (current === generation) error.value = e.message }
})
async function refresh() { rows.value = await call('campaigns.listing') }
async function action(fn) {
  busy.value = true; error.value = ''; notice.value = ''
  try { await fn() } catch (e) { error.value = e.message } finally { busy.value = false }
}
async function suggest() {
  await action(async () => {
    if (!suggestionCycle) {
      const history = await call('campaigns.wording_history', { shop: shop.value, item: item.value })
      suggestionCycle = orderCampaignSuggestions(style.value === 'goan' ? eligibleTemplates.value.map(row => ({ ...row[script.value], id: row.id })) : campaignSuggestions(product.value, shopName.value), history)
    }
    if (!suggestionCycle.length) throw new Error('Select a product, save its fish type, and enable a matching template first.')
    const suggestion = suggestionCycle[suggestionIndex % suggestionCycle.length]
    suggestionIndex++
    templateId.value = suggestion.id || ''
    title.value = suggestion.title
    message.value = suggestion.message
  })
}

async function save() {
  await action(async () => {
    const result = await call('campaigns.save', { shop: shop.value, item: item.value, title: title.value, message: message.value, template_id: style.value === 'goan' ? templateId.value : '', template_script: script.value, campaign_audience: audience.value, campaign_period: period.value }, true)
    saved.value = result.name; suggestionCycle = null; suggestionIndex = 0; notice.value = 'Draft saved. Review the preview before sending.'; await refresh()
  })
}
async function test(name) {
  await action(async () => { await call('campaigns.test', { name }, true); notice.value = 'Test queued to your account. Check your phone.' })
}
async function send(name, scheduled = '') {
  if (!window.confirm('Send this campaign to customers who opted into promotions?')) return
  await action(async () => {
    await call('campaigns.send', { name, send_at: scheduled.replace('T', ' ') }, true)
    notice.value = 'Campaign queued. Delivery waits until the shop is open.'; await refresh()
  })
}
async function cancel(name) {
  await action(async () => { await call('campaigns.cancel', { name }, true); await refresh() })
}
onMounted(() => action(async () => { const result = await call('campaigns.options'); shops.value = result.shops; templates.value = result.templates; templateSettings.value = result.template_settings; await refresh() }))
</script>
<template>
  <section class="campaign-page">
    <h2>Promotional campaigns</h2>
    <p>Customers who allow promotions receive up to five automatic product suggestions per day, at least 2½ hours apart while shops are open. Manual campaigns have no frequency limit. Automatic suggestions use available products; shops need opening hours configured.</p>
    <p v-if="error" class="lc-notice" role="alert">{{ error }}</p>
    <p v-if="notice" role="status">{{ notice }}</p>
    <form class="admin-card campaign-form" @submit.prevent="save">
      <fieldset :disabled="busy">
        <label>Shop<select v-model="shop" required><option value="">Choose a shop</option><option v-for="row in shops" :key="row.name" :value="row.name">{{ row.shop_name }}</option></select></label>
        <label>Product (optional)<select v-model="item"><option value="">Whole shop</option><option v-for="row in products" :key="row.name" :value="row.name">{{ row.item_name }}</option></select></label>
        <label>Wording style<select v-model="style"><option value="existing">Existing wording</option><option value="goan">O Baiii! 🐟 — Goan Konkani</option></select></label>
        <template v-if="style === 'goan'">
          <label>Script<select v-model="script"><option value="latin">English letters</option><option value="devanagari">देवनागरी</option></select></label>
          <label v-if="item">Product fish type<select v-model="templateSettings.fish_tags[item]"><option :value="undefined">Choose fish type</option><option value="fish">Other fish</option><option value="bangde">Bangde / Makrel</option><option value="talle">Talle</option><option value="isvon">Isvon</option><option value="chonak">Chonak</option></select></label>
          <button v-if="item" type="button" @click="saveTemplateSettings">Save fish type</button>
          <small>Choose the actual fish in this product. Specific fish messages only match that fish type.</small>
          <label>Template<select v-model="templateId" required><option value="">Choose a template</option><option v-for="row in eligibleTemplates" :key="row.id" :value="row.id">{{ row.category }} · {{ row[script].title }}</option></select></label>
          <small v-if="selectedTemplate">{{ selectedTemplate.weekdays.length ? (selectedTemplate.weekdays[0] === 6 ? 'Sunday only. ' : 'Saturday only. ') : '' }}{{ selectedTemplate.period ? `Use the ${selectedTemplate.period} window. ` : '' }}Goan sending hours: {{ templateSettings.start }}:00–{{ templateSettings.end }}:00 (site time).</small>
          <small>Review local wording before sending. Edits must still describe the selected product accurately.</small>
        </template>
        <label>Audience<select v-model="audience"><option>All</option><option>Shop customers</option></select></label>
        <small>Shop customers means eligible accounts with an order at this shop. All audiences respect promotional preferences.</small>
        <label>Sending window<select v-model="period"><option value="">Shop opening hours</option><option value="morning">Morning · 08:00–10:00</option><option value="lunch">Lunch · 12:00–14:00</option><option value="evening">Evening · 17:00–19:00</option></select></label>
        <small v-if="product?.item_group">Suggestions for {{ product.item_group }}</small>
        <button type="button" :disabled="!shop" @click="suggest">Suggest wording · try another</button>
        <small>Tap again for another idea. Edit the title and message to suit your shop before sending.</small>
        <label>Title<input v-model="title" maxlength="80" required></label>
        <label>Message<textarea v-model="message" maxlength="240" required /></label>
        <aside class="campaign-preview" aria-label="Notification preview"><strong>{{ title || 'Notification title' }}</strong><p>{{ message || 'Your message appears here.' }}</p><small>Opens {{ product?.item_name || shopName || 'your shop' }}</small></aside>
        <button class="lc-primary" type="submit">Save draft</button>
      </fieldset>
    </form>
    <div v-if="saved" class="admin-card campaign-form">
      <button :disabled="busy" @click="test(saved)">Send test to myself</button>
      <label>Schedule (optional, site time)<input v-model="sendAt" type="datetime-local"></label>
      <button :disabled="busy" class="lc-primary" @click="send(saved, sendAt)">{{ sendAt ? 'Schedule campaign' : 'Send campaign' }}</button>
    </div>
    <details class="admin-card campaign-form">
      <summary>Goan template settings · 50 bilingual ideas</summary>
      <label><input v-model="templateSettings.automatic" type="checkbox"> Use eligible Goan templates in automatic campaigns</label>
      <small>Uses the existing five-per-day limit, not extra sends. Other products continue using existing wording.</small>
      <label>Automatic script<select v-model="templateSettings.script"><option value="latin">English letters</option><option value="devanagari">देवनागरी</option></select></label>
      <label>Goan sending hours start<input v-model.number="templateSettings.start" type="number" min="0" max="23"></label>
      <label>Goan sending hours end<input v-model.number="templateSettings.end" type="number" min="1" max="24"></label>
      <small>Checked together with shop hours and template day/time restrictions. Selected templates below are disabled.</small>
      <label v-for="row in templates" :key="row.id"><span><input v-model="templateSettings.disabled" type="checkbox" :value="row.id"> Disable {{ row.latin.title }}</span></label>
      <button :disabled="busy" type="button" @click="saveTemplateSettings">Save template settings</button>
    </details>
    <header><h3>Recent campaigns</h3><button :disabled="busy" @click="action(refresh)">Refresh</button></header>
    <p>Queued counts are notification records, not confirmed phone deliveries. Read counts reflect in-app reads.</p>
    <article v-for="row in rows" :key="row.name" class="admin-card campaign-record">
      <small v-if="row.template_id">{{ row.template_id }} · {{ row.template_script }} · {{ row.campaign_audience || 'All' }}</small><h3>{{ row.title }}</h3><p>{{ row.message }}</p>
      <p>{{ row.automatic_key ? 'Automatic daily · ' : '' }}{{ row.status }} <span v-if="row.send_at">· {{ row.send_at }} (site time)</span></p>
      <p>{{ row.queued_count }} queued · {{ row.skipped_count }} skipped · {{ row.suppressed_count || 0 }} expired/suppressed · {{ row.read_count }} read</p>
      <div class="campaign-actions">
        <button v-if="row.status === 'Draft'" :disabled="busy" @click="test(row.name)">Test to myself</button>
        <button v-if="row.status === 'Draft'" :disabled="busy" @click="send(row.name)">Send campaign</button>
        <button v-if="['Draft', 'Queued'].includes(row.status) || (row.automatic_key && row.status !== 'Cancelled')" :disabled="busy" @click="cancel(row.name)">Cancel campaign</button>
      </div>
    </article>
  </section>
</template>
<style scoped>
.campaign-page { min-width: 0; }
.campaign-form { margin-bottom: 18px; display: grid; gap: 14px; }
.campaign-form fieldset { border: 0; padding: 0; margin: 0; min-width: 0; display: grid; gap: 14px; }
.campaign-form label { display: grid; gap: 6px; }
.campaign-preview { padding: 18px; background: #eef5eb; border-radius: 14px; overflow-wrap: anywhere; }
.campaign-record { margin: 12px 0; overflow-wrap: anywhere; }
.campaign-actions { display: flex; flex-wrap: wrap; gap: 10px; }
</style>
