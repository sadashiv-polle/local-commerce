<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { call } from './api.js'
import { campaignSuggestions, orderCampaignSuggestions } from './campaign-copy.js'
const shops = ref([]), products = ref([]), rows = ref([])
const shop = ref(''), item = ref(''), title = ref(''), message = ref(''), saved = ref(''), sendAt = ref('')
const busy = ref(false), error = ref(''), notice = ref('')
const product = computed(() => products.value.find(row => row.name === item.value))
const shopName = computed(() => shops.value.find(row => row.name === shop.value)?.shop_name || '')
let generation = 0, suggestionIndex = 0, suggestionCycle = null
watch([shop, item], () => { suggestionIndex = 0; suggestionCycle = null })
watch([shop, item, title, message], () => { saved.value = '' })
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
      suggestionCycle = orderCampaignSuggestions(campaignSuggestions(product.value, shopName.value), history)
    }
    const suggestion = suggestionCycle[suggestionIndex % suggestionCycle.length]
    suggestionIndex++
    title.value = suggestion.title
    message.value = suggestion.message
  })
}

async function save() {
  await action(async () => {
    const result = await call('campaigns.save', { shop: shop.value, item: item.value, title: title.value, message: message.value }, true)
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
onMounted(() => action(async () => { shops.value = (await call('campaigns.options')).shops; await refresh() }))
</script>
<template>
  <section class="campaign-page">
    <h2>Promotional campaigns</h2>
    <p>Customers who allow promotions receive one daily product suggestion while a shop is open. Approved campaigns count toward that daily limit. Automatic suggestions use available products; shops need opening hours configured.</p>
    <p v-if="error" class="lc-notice" role="alert">{{ error }}</p>
    <p v-if="notice" role="status">{{ notice }}</p>
    <form class="admin-card campaign-form" @submit.prevent="save">
      <fieldset :disabled="busy">
        <label>Shop<select v-model="shop" required><option value="">Choose a shop</option><option v-for="row in shops" :key="row.name" :value="row.name">{{ row.shop_name }}</option></select></label>
        <label>Product (optional)<select v-model="item"><option value="">Whole shop</option><option v-for="row in products" :key="row.name" :value="row.name">{{ row.item_name }}</option></select></label>
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
    <header><h3>Recent campaigns</h3><button :disabled="busy" @click="action(refresh)">Refresh</button></header>
    <p>Queued counts are notification records, not confirmed phone deliveries. Read counts reflect in-app reads.</p>
    <article v-for="row in rows" :key="row.name" class="admin-card campaign-record">
      <h3>{{ row.title }}</h3><p>{{ row.message }}</p>
      <p>{{ row.automatic_key ? 'Automatic daily · ' : '' }}{{ row.status }} <span v-if="row.send_at">· {{ row.send_at }} (site time)</span></p>
      <p>{{ row.queued_count }} queued · {{ row.skipped_count }} skipped · {{ row.read_count }} read</p>
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
