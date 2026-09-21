<script setup>
import { inject, onMounted, ref } from 'vue'
import { call } from './api.js'
import BatchRoute from './ScheduledRoute.vue'
const props = defineProps({ shop: { type: String, required: true } })
const session = inject('session'), settings = ref(null), error = ref(''), message = ref(''), busy = ref(false)
const editing = ref(''), routeSlot = ref(''), drivers = ref([]), rider = ref(''), products = ref([])
const blank = () => ({ title: '', enabled: 1, ordering_start: '', ordering_end: '', delivery_start: '', delivery_end: '', capacity: 20, radius_km: 5, products: '', postcodes: '' })
const form = ref(blank()), selectedItems = ref([]), search = ref('')
async function load() {
  try { settings.value = await call('scheduled.settings', { shop: props.shop }); drivers.value = await call('orders.drivers', { shop: props.shop }) }
  catch (e) { error.value = e.message }
}
async function run(fn, text) { busy.value = true; error.value = ''; message.value = ''; try { await fn(); message.value = text; await load() } catch(e) { error.value = e.message } finally { busy.value = false } }
function edit(row) { editing.value = row.name; form.value = { ...row }; for (const key of ['ordering_start', 'ordering_end', 'delivery_start', 'delivery_end']) form.value[key] = String(row[key]).replace(' ', 'T').slice(0, 16); selectedItems.value = (row.products || '').split('\n').filter(Boolean) }
async function save() {
  await run(async () => { await call('scheduled.save_slot', { shop: props.shop, name: editing.value || null, values: { ...form.value, products: selectedItems.value.join('\n') } }, true); editing.value = ''; form.value = blank(); selectedItems.value = [] }, 'Delivery slot saved.')
}
async function findProducts() { try { const result = await call('owner.catalog', { shop: props.shop, search: search.value }); products.value = result.items.map(item => ({ ...item, item: item.name })) } catch(e) { error.value = e.message } }
onMounted(load)
</script>
<template>
  <section class="scheduled-panel">
    <span class="eyebrow">DELIVERY BOOKINGS</span><h3>Normal &amp; scheduled delivery</h3>
    <p v-if="error" role="alert" class="lc-error">{{ error }}</p><p v-if="message" role="status">{{ message }}</p>
    <template v-if="settings">
      <p>Times use {{ settings.timezone }}. Scheduled delivery has no delivery fee.</p>
      <div class="form-columns"><label class="check-label"><input v-model="settings.normal" type="checkbox" :disabled="!session.platform_admin">Normal delivery</label><label class="check-label"><input v-model="settings.scheduled" type="checkbox" :disabled="!session.platform_admin">Scheduled delivery</label></div>
      <button v-if="session.platform_admin" type="button" :disabled="busy" @click="run(() => call('scheduled.configure', { shop, normal: settings.normal ? 1 : 0, scheduled_enabled: settings.scheduled ? 1 : 0 }, true), 'Delivery options saved.')">Save delivery options</button>
      <form v-if="session.platform_admin" class="scheduled-editor" @submit.prevent="save">
        <h4>{{ editing ? 'Edit delivery slot' : 'Create delivery slot' }}</h4><p>One slot forms one shop delivery batch. After the first booking, timing and area are locked to protect customer commitments.</p>
        <fieldset :disabled="busy">
          <label>Slot name<input v-model="form.title" required placeholder="Morning neighbourhood delivery"></label><div class="form-columns"><label v-for="field in [['ordering_start','Ordering starts'],['ordering_end','Ordering closes'],['delivery_start','Delivery starts'],['delivery_end','Delivery ends']]" :key="field[0]">{{ field[1] }}<input v-model="form[field[0]]" type="datetime-local" required></label><label>Maximum orders<input v-model.number="form.capacity" type="number" min="1" max="30" required></label><label>Delivery radius (km)<input v-model.number="form.radius_km" type="number" min="0.1" max="500" step="0.1" required></label></div>
          <label>Delivery postal codes<textarea v-model="form.postcodes" placeholder="Optional: one postal code per line. Radius applies too."></textarea></label>
          <label class="check-label"><input v-model="form.enabled" type="checkbox" :true-value="1" :false-value="0">Accept bookings</label>
          <h4>Products available in this slot</h4><p>Leave the selection empty for all available shop products.</p><div class="button-row"><input v-model="search" placeholder="Find products"><button type="button" @click="findProducts">Search</button></div><label v-for="item in products" :key="item.item" class="check-label"><input v-model="selectedItems" type="checkbox" :value="item.item">{{ item.item_name }}</label><p>{{ selectedItems.length }} selected</p><button v-if="selectedItems.length" type="button" @click="selectedItems = []">Use all products</button>
          <button class="lc-primary" type="submit">Save slot</button><button v-if="editing" type="button" @click="editing = ''; form = blank(); selectedItems = []">Cancel editing</button>
        </fieldset>
      </form>
      <article v-for="slot in settings.slots" :key="slot.name" class="scheduled-slot"><h4>{{ slot.title }}</h4><p>Order: {{ slot.ordering_start }} – {{ slot.ordering_end }}</p><p>Delivery: {{ slot.delivery_start }} – {{ slot.delivery_end }}</p><p>{{ slot.order_count }} / {{ slot.capacity }} orders · {{ slot.compiled ? 'Compiled' : 'Awaiting ordering cutoff' }}</p><div class="button-row"><button v-if="session.platform_admin" type="button" @click="edit(slot)">Edit slot</button><button type="button" @click="routeSlot = slot.name">View batch route</button></div><div v-if="session.platform_admin" class="button-row"><select v-model="rider"><option value="">Choose delivery person</option><option v-for="driver in drivers" :key="driver.user" :value="driver.user">{{ driver.full_name }}</option></select><button type="button" :disabled="busy || !rider" @click="run(() => call('scheduled.assign', { slot: slot.name, delivery_user: rider }, true), 'Batch assigned.')">Assign ready batch</button></div></article>
      <BatchRoute v-if="routeSlot" :slot-name="routeSlot" />
    </template>
  </section>
</template>
