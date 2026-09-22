<script setup>
import { inject, nextTick, onMounted, ref } from 'vue'
import { reuseSlot, tomorrowInZone } from './reuse-slot.js'
import { call } from './api.js'
import BatchActions from './BatchActions.vue'
import BatchRoute from './ScheduledRoute.vue'
const props = defineProps({ shop: { type: String, required: true } })
const session = inject('session'), settings = ref(null), error = ref(''), message = ref(''), busy = ref(false)
const pageStart = ref(0), editor = ref(null), reuseSource = ref(null), reuseDate = ref(''), activeBatch = ref('')
const daily = ref(true)
const editing = ref(''), routeSlot = ref(''), drivers = ref([]), rider = ref(''), products = ref([])
const blank = () => ({ title: '', enabled: 1, ordering_start: '', ordering_end: '', delivery_start: '', delivery_end: '', capacity: 20, radius_km: 5, products: '', postcodes: '' })
const form = ref(blank()), selectedItems = ref([]), search = ref('')
async function load() {
  try { settings.value = await call('scheduled.settings', { shop: props.shop, start: pageStart.value }); drivers.value = await call('orders.drivers', { shop: props.shop }) }
  catch (e) { error.value = e.message }
}
async function run(fn, text) { busy.value = true; error.value = ''; message.value = ''; try { await fn(); message.value = text; await load() } catch(e) { error.value = e.message } finally { busy.value = false } }
function edit(row, recurring = false) { daily.value = recurring; reuseSource.value = null; editing.value = row.name; form.value = { ...row }; for (const key of ['ordering_start', 'ordering_end', 'delivery_start', 'delivery_end']) form.value[key] = recurring ? String(row[key]).padStart(8, '0').slice(0, 5) : String(row[key]).replace(' ', 'T').slice(0, 16); selectedItems.value = (row.products || '').split('\n').filter(Boolean) }
async function startReuse(row) {
  daily.value = false; reuseSource.value = row; reuseDate.value = tomorrowInZone(settings.value.timezone)
  editing.value = ''; applyReuse(); await nextTick(); editor.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
function applyReuse() {
  try { form.value = reuseSlot(reuseSource.value, reuseDate.value); selectedItems.value = (form.value.products || '').split('\n').filter(Boolean); error.value = '' } catch(e) { error.value = e.message }
}
async function page(delta) { pageStart.value = Math.max(0, pageStart.value + delta); activeBatch.value = ''; await load() }
async function toggle(row, enabled, recurring = false) { await run(() => call(recurring ? 'scheduled.save_schedule' : 'scheduled.save_slot', { shop: props.shop, name: row.name, values: { enabled: enabled ? 1 : 0 } }, true), enabled ? (recurring ? 'Daily slot enabled. Bookings open during its ordering window every day.' : 'Slot shown to customers when its dates are eligible.') : 'Slot hidden from customers. Existing orders are unchanged.') }
async function save() {
  await run(async () => { await call(daily.value ? 'scheduled.save_schedule' : 'scheduled.save_slot', { shop: props.shop, name: editing.value || null, values: { ...form.value, products: selectedItems.value.join('\n') } }, true); editing.value = ''; reuseSource.value = null; form.value = blank(); selectedItems.value = []; pageStart.value = 0 }, 'Delivery slot saved.')
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
      <form v-if="session.platform_admin" ref="editor" class="scheduled-editor" @submit.prevent="save">
        <h4>{{ reuseSource ? 'Reuse slot for another day' : editing ? 'Edit delivery slot' : 'Create daily delivery slot' }}</h4><p>Daily slots repeat automatically in the site timezone. Each day has its own batch and capacity. Changes apply to unbooked dates; existing bookings keep their original times. Ordering must close before delivery starts. Use 00:00 for a midnight delivery end.</p>
        <label v-if="!editing && !reuseSource" class="check-label"><input v-model="daily" type="checkbox" @change="form = blank()">Repeat every day (times only)</label><label v-if="reuseSource">New delivery date<input v-model="reuseDate" type="date" required @change="applyReuse"><small>A new slot will be saved. Past orders and their original dates stay unchanged.</small></label><fieldset :disabled="busy">
          <label>Slot name<input v-model="form.title" required placeholder="Morning neighbourhood delivery"></label><div class="form-columns"><label v-for="field in [['ordering_start','Ordering starts'],['ordering_end','Ordering closes'],['delivery_start','Delivery starts'],['delivery_end','Delivery ends']]" :key="field[0]">{{ field[1] }}<input v-model="form[field[0]]" :type="daily ? 'time' : 'datetime-local'" required></label><label>Maximum orders<input v-model.number="form.capacity" type="number" min="1" max="30" required></label><label>Delivery radius (km)<input v-model.number="form.radius_km" type="number" min="0.1" max="500" step="0.1" required></label></div>
          <label>Delivery postal codes<textarea v-model="form.postcodes" placeholder="Optional: one postal code per line. Radius applies too."></textarea></label>
          <label class="check-label"><input v-model="form.enabled" type="checkbox" :true-value="1" :false-value="0">Show to customers / accept bookings</label>
          <h4>Products available in this slot</h4><p>Leave the selection empty for all available shop products.</p><div class="button-row"><input v-model="search" placeholder="Find products"><button type="button" @click="findProducts">Search</button></div><label v-for="item in products" :key="item.item" class="check-label"><input v-model="selectedItems" type="checkbox" :value="item.item">{{ item.item_name }}</label><p>{{ selectedItems.length }} selected</p><button v-if="selectedItems.length" type="button" @click="selectedItems = []">Use all products</button>
          <button class="lc-primary" type="submit">Save slot</button><button v-if="editing || reuseSource" type="button" @click="editing = ''; reuseSource = null; form = blank(); selectedItems = []">Cancel editing</button>
        </fieldset>
      </form>
      <h4>Daily time slots</h4>
      <p v-if="!settings.schedules?.length">Create a daily slot above. No daily date changes needed.</p>
      <article v-for="schedule in settings.schedules" :key="schedule.name" class="scheduled-slot">
        <h4>{{ schedule.title }} · Every day</h4>
        <p>Order: {{ schedule.ordering_start }} – {{ schedule.ordering_end }}</p>
        <p>Delivery: {{ schedule.delivery_start }} – {{ schedule.delivery_end }}</p>
        <label v-if="session.platform_admin" class="check-label"><input type="checkbox" :checked="!!schedule.enabled" :disabled="busy" @change="toggle(schedule, $event.target.checked, true)">Show to customers every day</label>
        <button v-if="session.platform_admin" type="button" @click="edit(schedule, true); editor?.scrollIntoView({ behavior: 'smooth' })">Edit daily slot</button>
      </article>
      <h4>Dated batches &amp; history</h4>
      <article v-for="slot in settings.slots" :key="slot.name" class="scheduled-slot"><h4>{{ slot.title }} <small v-if="slot.past">· Past slot</small></h4><label v-if="session.platform_admin && !slot.daily_schedule" class="check-label"><input :checked="!!slot.enabled" type="checkbox" :disabled="busy" @change="toggle(slot, $event.target.checked)">Show to customers</label><p v-if="slot.past" class="muted">Kept for reuse and history. Use “Reuse for another day” to offer this slot again.</p><p>Order: {{ slot.ordering_start }} – {{ slot.ordering_end }}</p><p>Delivery: {{ slot.delivery_start }} – {{ slot.delivery_end }}</p><p>{{ slot.order_count }} / {{ slot.capacity }} orders · {{ slot.compiled ? 'Compiled' : 'Awaiting ordering cutoff' }}</p><div class="button-row"><button v-if="session.platform_admin && !slot.has_bookings && !slot.daily_schedule" type="button" @click="edit(slot)">Edit slot</button><button v-if="session.platform_admin && !slot.daily_schedule" type="button" @click="startReuse(slot)">Reuse for another day</button><button type="button" @click="activeBatch = activeBatch === slot.name ? '' : slot.name">{{ activeBatch === slot.name ? 'Hide batch controls' : 'Manage batch' }}</button><button type="button" @click="routeSlot = slot.name">View batch route</button></div><BatchActions v-if="activeBatch === slot.name" :slot-name="slot.name" @changed="load" /><div v-if="activeBatch === slot.name" class="button-row"><select v-model="rider"><option value="">Choose delivery person</option><option v-for="driver in drivers" :key="driver.user" :value="driver.user">{{ driver.full_name }}</option></select><button type="button" :disabled="busy || !rider" @click="run(() => call('scheduled.assign', { slot: slot.name, delivery_user: rider }, true), 'Batch assigned.')">Assign ready batch</button></div></article>
      <div class="lc-pagination"><button type="button" :disabled="!pageStart || busy" @click="page(-100)">Previous slots</button><span>Page {{ pageStart / 100 + 1 }}</span><button type="button" :disabled="settings.slots.length < 100 || busy" @click="page(100)">More slots</button></div><BatchRoute v-if="routeSlot" :slot-name="routeSlot" />
    </template>
  </section>
</template>
