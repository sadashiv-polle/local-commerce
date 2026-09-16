<script setup>
import { computed, inject, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { call } from './api.js'
import AdminIcon from './AdminIcon.vue'
import Products from './Products.vue'
import Orders from './Orders.vue'
import CashReconciliation from './CashReconciliation.vue'
import StoreSettings from './StoreSettings.vue'
const session = inject('session'), route = useRoute(), router = useRouter()
const modules = [
  { id: 'overview', title: 'Overview', description: 'Your platform at a glance' },
  { id: 'shops', title: 'Shops', description: 'Businesses, locations and ordering controls' },
  { id: 'orders', title: 'Orders', description: 'Prepare, assign and follow every order' },
  { id: 'inventory', title: 'Inventory', description: 'Products, stock and selling prices' },
  { id: 'people', title: 'Team & riders', description: 'Shop memberships and delivery partners' },
  { id: 'customers', title: 'Customers', description: 'Customer accounts and business records' },
  { id: 'payments', title: 'Payments', description: 'COD collections and cash handovers' },
  { id: 'storefront', title: 'Storefront', description: 'Categories, artwork and featured products' },
  { id: 'settings', title: 'Settings', description: 'Accounting, communication and platform setup' },
]
const section = computed(() => modules.find(module => module.id === route.params.section)?.id || 'overview')
const currentModule = computed(() => modules.find(module => module.id === section.value))
const selectedShop = computed(() => typeof route.query.shop === 'string' ? route.query.shop : '')
const adminNavigation = ref(null)
const summary = ref(null), rows = ref([]), recent = ref([]), loading = ref(false), rowsLoading = ref(false), error = ref(''), rowError = ref(''), busy = ref('')
const search = ref(''), status = ref(''), start = ref(0), hasMore = ref(false)
const embedded = computed(() => selectedShop.value && ['orders', 'inventory', 'payments'].includes(section.value))
const statuses = computed(() => ({ shops: ['Draft', 'Active', 'Temporarily Closed', 'Disabled'], orders: ['Requested', 'Accepted', 'Preparing', 'Ready', 'Picked Up', 'Out for Delivery', 'Delivered', 'Cancelled'], people: ['Owner', 'Staff', 'Driver'], payments: ['Awaiting Handover', 'Reconciled'] })[section.value] || [])
const pipeline = ['Requested', 'Accepted', 'Preparing', 'Ready', 'Picked Up', 'Out for Delivery']
const chart = computed(() => {
  const today = summary.value?.date
  if (!today) return []
  const anchor = new Date(`${today}T12:00:00`)
  const days = Array.from({ length: 7 }, (_, index) => {
    const day = new Date(anchor); day.setDate(day.getDate() - 6 + index)
    const key = `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, '0')}-${String(day.getDate()).padStart(2, '0')}`
    return { label: day.toLocaleDateString([], { weekday: 'short' }), count: summary.value.trend.filter(row => String(row.day).slice(0, 10) === key).reduce((sum, row) => sum + Number(row.orders), 0) }
  })
  const max = Math.max(1, ...days.map(day => day.count))
  return days.map(day => ({ ...day, height: day.count ? Math.max(5, day.count / max * 100) : 2 }))
})
const metrics = computed(() => summary.value ? [
  { title: 'New orders today', value: summary.value.new_orders_today, hint: `${summary.value.pending_orders} waiting for a response`, icon: 'orders', target: 'orders' },
  { title: 'Active shops', value: summary.value.active_shops, hint: `${summary.value.shops} shops on your platform`, icon: 'shops', target: 'shops' },
  { title: 'Delivery partners', value: summary.value.riders, hint: `${summary.value.out_for_delivery} orders out for delivery`, icon: 'people', target: 'people' },
  { title: 'Customers', value: summary.value.customers, hint: `${summary.value.products} enabled products`, icon: 'customers', target: 'customers' },
] : [])
const systemLinks = [
  { title: 'Companies & accounts', links: [['Companies', '/app/company'], ['Chart of accounts', '/app/account'], ['Cost centers', '/app/cost-center'], ['Tax templates', '/app/sales-taxes-and-charges-template']] },
  { title: 'Stock & pricing', links: [['Warehouses', '/app/warehouse'], ['Item groups', '/app/item-group'], ['Price lists', '/app/price-list'], ['Selling settings', '/app/selling-settings']] },
  { title: 'Accounts & communication', links: [['Users & roles', '/app/user'], ['Email accounts', '/app/email-account'], ['Website settings', '/app/website-settings'], ['Notification records', '/app/lc-notification']] },
]
const setupDialog = ref(null), setupKind = ref('shop'), setup = ref(null), setupLoading = ref(false), setupSaving = ref(false), setupError = ref('')
const shopForm = ref({ shop_name: '', company: '', country: '', currency: '' })
const memberForm = ref({ name: '', shop: '', user: '', membership_role: 'Driver', enabled: true }), userSearch = ref('')
let generation = 0, searchTimer, refreshTimer, userTimer, userGeneration = 0
async function openSetup(kind, row = null) {
  setupKind.value = kind; setupError.value = ''; setupLoading.value = true
  shopForm.value = { shop_name: '', company: '', country: '', currency: '' }
  memberForm.value = row ? { name: row.name, shop: row.shop, user: row.user, membership_role: row.membership_role, enabled: !!row.enabled } : { name: '', shop: selectedShop.value, user: '', membership_role: 'Driver', enabled: true }
  userSearch.value = ''
  await nextTick(); setupDialog.value.showModal()
  try { setup.value = await call('admin.setup_options'); shopForm.value.country = setup.value.country || ''; shopForm.value.currency = setup.value.currency || '' }
  catch (e) { setupError.value = e.message } finally { setupLoading.value = false }
}
function closeSetup(event) { if (setupSaving.value) { event?.preventDefault(); return }; setupDialog.value.close(); userGeneration++ }
async function saveSetup() {
  setupSaving.value = true; setupError.value = ''
  try {
    if (setupKind.value === 'shop') {
      const result = await call('admin.create_shop', shopForm.value, true)
      setupSaving.value = false; closeSetup()
      await refresh(); await router.push({ name: 'shop-workspace', params: { shop: result.name }, query: { tab: 'settings' } })
    } else {
      await call('admin.save_membership', { ...memberForm.value, enabled: memberForm.value.enabled ? 1 : 0 }, true)
      setupSaving.value = false; closeSetup(); await refresh()
    }
  } catch (e) { setupError.value = e.message } finally { setupSaving.value = false }
}
watch(userSearch, () => {
  window.clearTimeout(userTimer); const current = ++userGeneration
  userTimer = window.setTimeout(async () => {
    try { const result = await call('admin.setup_options', { search: userSearch.value }); if (current === userGeneration && setup.value) setup.value.users = result.users }
    catch (e) { if (current === userGeneration) setupError.value = e.message }
  }, 250)
})
async function revealSection() {
  await nextTick()
  const nav = adminNavigation.value, active = nav?.querySelector('[aria-current="page"]')
  if (!nav || !active || nav.scrollWidth <= nav.clientWidth) return
  const rect = active.getBoundingClientRect(), viewport = nav.getBoundingClientRect()
  nav.scrollTo({ left: nav.scrollLeft + rect.left - viewport.left - (nav.clientWidth - rect.width) / 2, behavior: 'smooth' })
}
watch(section, revealSection, { flush: 'post' })
function go(target, shop = '', filter = '') { router.push({ path: `/admin/${target}`, query: { ...(shop ? { shop } : {}), ...(filter ? { status: filter } : {}) } }) }
function chooseShop(event) { go(section.value, event.target.value) }
function money(value, currency) { return value == null || !currency ? '—' : new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(Number(value)) }
function when(value) { return value ? new Date(String(value).replace(' ', 'T')).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : '—' }
function record(type, name) { return `/app/${type}/${encodeURIComponent(name)}` }
async function loadRows(delta = 0) {
  const current = ++generation
  if (!session.value.platform_admin || ['overview', 'storefront', 'settings'].includes(section.value) || embedded.value) { rows.value = []; rowsLoading.value = false; return }
  start.value = Math.max(0, start.value + delta); rowsLoading.value = true; rowError.value = ''
  try {
    const result = await call('admin.listing', { section: section.value, shop: selectedShop.value, search: search.value, status: status.value, start: start.value })
    if (current === generation) { rows.value = result.items; hasMore.value = result.has_more }
  } catch (e) { if (current === generation) rowError.value = e.message }
  finally { if (current === generation) rowsLoading.value = false }
}
async function refresh() {
  if (!session.value.platform_admin || loading.value) return
  loading.value = true; error.value = ''
  try {
    const [overview, latest] = await Promise.all([call('admin.overview'), call('admin.listing', { section: 'orders' })])
    summary.value = overview; recent.value = latest.items.slice(0, 5)
    await loadRows()
  } catch (e) { error.value = e.message } finally { loading.value = false }
}
async function toggleShop(row) {
  busy.value = row.name; rowError.value = ''
  try { const result = await call('admin.set_accepting', { shop: row.name, enabled: row.accepting_orders ? 0 : 1 }, true); row.accepting_orders = result.accepting_orders }
  catch (e) { rowError.value = e.message } finally { busy.value = '' }
}
watch([section, selectedShop, () => route.query.status], () => { window.clearTimeout(searchTimer); search.value = ''; status.value = statuses.value.includes(route.query.status) ? route.query.status : ''; start.value = 0; rows.value = []; rowError.value = ''; loadRows() }, { immediate: true })
watch([search, status], () => { window.clearTimeout(searchTimer); generation++; start.value = 0; searchTimer = window.setTimeout(() => loadRows(), 300) })
onMounted(() => { revealSection(); refresh(); refreshTimer = window.setInterval(() => { if (document.visibilityState === 'visible' && !busy.value && section.value === 'overview') refresh() }, 30000) })
onBeforeUnmount(() => { generation++; window.clearTimeout(searchTimer); window.clearInterval(refreshTimer); window.clearTimeout(userTimer); userGeneration++ })
</script>
<template>
  <section v-if="!session.platform_admin" class="admin-access-denied"><AdminIcon name="settings" /><h1>Administrator access required</h1><p>This dashboard is available to platform administrators.</p><RouterLink to="/store">Back to store</RouterLink></section>
  <div v-else class="master-admin">
    <aside class="master-admin-sidebar"><div class="admin-sidebar-heading"><span class="admin-platform-mark">L<span>●</span></span><div><strong>Local control</strong><small>PLATFORM ADMIN</small></div></div><div class="admin-navigation-wrapper"><nav ref="adminNavigation" aria-label="Administration"><RouterLink v-for="module in modules" :key="module.id" :to="`/admin/${module.id}`" :class="{ active: section === module.id }" :aria-current="section === module.id ? 'page' : undefined"><AdminIcon :name="module.id" /><span>{{ module.title }}</span><b v-if="module.id === 'orders' && summary?.pending_orders">{{ summary.pending_orders }}</b></RouterLink></nav><label class="admin-section-picker"><span class="admin-sr-only">All dashboard sections</span><AdminIcon name="overview" /><small>Menu</small><select :value="section" @change="go($event.target.value)"><option v-for="module in modules" :key="module.id" :value="module.id">{{ module.title }}</option></select></label></div><div class="admin-sidebar-bottom"><span class="admin-avatar">{{ session.full_name.slice(0, 1) }}</span><div><strong>{{ session.full_name }}</strong><small>Platform administrator</small></div></div></aside>
    <div class="master-admin-content">
      <header class="admin-page-header"><div><span class="eyebrow">PLATFORM / {{ currentModule.title.toUpperCase() }}</span><h1>{{ currentModule.title }}</h1><p>{{ currentModule.description }}</p></div><div class="admin-header-actions"><RouterLink to="/store">View store ↗</RouterLink><button type="button" :disabled="loading" @click="refresh"><span aria-hidden="true">↻</span>{{ loading ? 'Refreshing…' : 'Refresh' }}</button></div></header>
      <p v-if="error" class="lc-notice" role="alert">{{ error }}</p>
      <template v-if="section === 'overview'">
        <div class="admin-welcome"><div><span class="admin-live-label"><i />YOUR OPERATIONS, CONNECTED</span><h2>Every shop. One clear view.</h2><p>Keep orders moving and your neighbourhood businesses growing.</p></div><RouterLink to="/admin/shops">Manage shops <span>→</span></RouterLink></div>
        <p v-if="loading && !summary" role="status">Loading your platform…</p>
        <template v-if="summary">
          <div class="admin-metric-grid"><RouterLink v-for="metric in metrics" :key="metric.title" :to="`/admin/${metric.target}`" class="admin-metric"><div><span>{{ metric.title }}</span><AdminIcon :name="metric.icon" /></div><strong>{{ metric.value }}</strong><small>{{ metric.hint }}</small></RouterLink></div>
          <div class="admin-overview-grid"><section class="admin-card admin-delivery-chart"><header><div><h2>Completed deliveries</h2><p>Last 7 days · all shops</p></div><span class="admin-soft-badge">{{ chart.reduce((sum, day) => sum + day.count, 0) }} delivered</span></header><div class="admin-bar-chart" role="img" :aria-label="chart.map(day => `${day.label}: ${day.count} deliveries`).join(', ')"><div v-for="day in chart" :key="day.label"><strong>{{ day.count }}</strong><div class="admin-bar-column"><span :style="{ height: `${day.height}%` }" /></div><small>{{ day.label }}</small></div></div></section><section class="admin-card admin-money-card"><header><div><h2>Money overview</h2><p>Amounts grouped by currency</p></div><AdminIcon name="payments" /></header><div class="admin-money-block"><small>DELIVERED SALES TODAY</small><strong v-for="row in summary.sales_today" :key="row.currency">{{ money(row.amount, row.currency) }}</strong><strong v-if="!summary.sales_today.length">No delivered sales yet</strong><span>Order totals for completed deliveries</span></div><div class="admin-money-block cash"><small>CASH AWAITING HANDOVER</small><strong v-for="row in summary.cash_pending" :key="row.currency">{{ money(row.amount, row.currency) }}</strong><strong v-if="!summary.cash_pending.length">All caught up</strong><RouterLink to="/admin/payments">Review collections →</RouterLink></div></section></div>
          <section class="admin-card admin-pipeline"><header><div><h2>Orders in progress</h2><p>{{ summary.active_orders }} active orders across your shops</p></div><RouterLink to="/admin/orders">View orders →</RouterLink></header><div><button v-for="stage in pipeline" :key="stage" type="button" @click="go('orders', '', stage)"><span>{{ stage }}</span><strong>{{ summary.statuses[stage] || 0 }}</strong></button></div></section>
          <div class="admin-overview-grid"><section class="admin-card"><header><div><h2>Latest orders</h2><p>The latest activity across your platform</p></div><RouterLink to="/admin/orders">View all →</RouterLink></header><div class="admin-recent-orders"><RouterLink v-for="order in recent" :key="order.name" :to="{ path: '/admin/orders', query: { shop: order.shop } }"><span class="admin-row-symbol"><AdminIcon name="orders" /></span><div><strong>{{ order.recipient }}</strong><small>{{ order.shop_name }} · {{ when(order.creation) }}</small></div><span class="admin-order-summary"><b>{{ money(order.amount, order.currency) }}</b><small class="admin-state" :class="{ good: order.status === 'Delivered', warning: order.status === 'Requested' }">{{ order.status }}</small></span></RouterLink><p v-if="!recent.length" class="admin-empty">Orders will appear here when customers start shopping.</p></div></section><section class="admin-card"><header><div><h2>Keep things moving</h2><p>Your next actions</p></div></header><div class="admin-action-list"><RouterLink to="/admin/orders"><AdminIcon name="orders" /><div><strong>Respond to new orders</strong><small>{{ summary.pending_orders }} waiting for confirmation</small></div><span>→</span></RouterLink><RouterLink to="/admin/shops"><AdminIcon name="shops" /><div><strong>Review shop setup</strong><small>{{ summary.inventory_setup_pending }} active shops without a warehouse</small></div><span>→</span></RouterLink><RouterLink to="/admin/storefront"><AdminIcon name="storefront" /><div><strong>Refresh your storefront</strong><small>Manage categories and featured product lists</small></div><span>→</span></RouterLink></div></section></div>
        </template>
      </template>
      <template v-else-if="section === 'storefront'"><StoreSettings embedded /></template>
      <template v-else-if="section === 'settings'"><div class="admin-settings-grid"><section v-for="group in systemLinks" :key="group.title" class="admin-card"><header><h2>{{ group.title }}</h2></header><a v-for="link in group.links" :key="link[1]" :href="link[1]" class="admin-settings-link">{{ link[0] }}<span>↗</span></a></section></div></template>
      <template v-else>
        <section class="admin-toolbar"><label v-if="section !== 'customers'">Shop<select :value="selectedShop" @change="chooseShop"><option value="">All shops</option><option v-for="shop in summary?.shop_options || []" :key="shop.name" :value="shop.name">{{ shop.shop_name }}</option><option v-if="selectedShop && !summary?.shop_options.some(shop => shop.name === selectedShop)" :value="selectedShop">Selected shop</option></select></label><label v-if="!embedded" class="admin-search">Search<input v-model="search" type="search" maxlength="140" placeholder="Search names, shops and records…"></label><label v-if="statuses.length && !embedded">{{ section === 'people' ? 'Role' : 'Status' }}<select v-model="status"><option value="">All {{ section === 'people' ? 'roles' : 'statuses' }}</option><option v-for="value in statuses" :key="value">{{ value }}</option></select></label><button v-if="section === 'shops'" type="button" class="admin-primary" @click="openSetup('shop')">+ Add shop</button><button v-if="section === 'people'" type="button" class="admin-primary" @click="openSetup('membership')">+ Add membership</button></section>
        <p v-if="embedded" class="admin-selected-note">Managing one shop. Choose “All shops” to return to the platform overview for this section.</p>
        <Orders v-if="embedded && section === 'orders'" :key="selectedShop" :shop="selectedShop" editable />
        <Products v-else-if="embedded && section === 'inventory'" :key="selectedShop" :shop="selectedShop" editable />
        <CashReconciliation v-else-if="embedded && section === 'payments'" :key="selectedShop" :shop="selectedShop" />
        <template v-else>
          <p v-if="rowError" class="lc-notice" role="alert">{{ rowError }}</p><p v-if="rowsLoading" role="status" class="admin-loading">Loading records…</p>
          <section class="admin-card admin-records" :aria-busy="rowsLoading">
            <div class="admin-table-wrap">
              <table>
                <thead><tr><th>{{ section === 'shops' ? 'Shop' : section === 'orders' ? 'Customer & order' : section === 'inventory' ? 'Product' : section === 'people' ? 'Team member' : section === 'customers' ? 'Customer' : 'Collection' }}</th><th>{{ section === 'customers' ? 'Customer record' : section === 'shops' ? 'Company / location' : 'Shop' }}</th><th>{{ section === 'people' ? 'Role' : section === 'orders' ? 'Amount / payment' : section === 'payments' ? 'Collected / difference' : section === 'inventory' ? 'Available stock' : 'Account / setup' }}</th><th>Status</th><th><span class="admin-sr-only">Actions</span></th></tr></thead><tbody>
                  <tr v-for="row in rows" :key="row.name">
                    <td><strong>{{ row.shop_name && section === 'shops' ? row.shop_name : section === 'orders' ? row.recipient : section === 'inventory' ? row.item_name : section === 'people' || section === 'customers' ? row.full_name : row.order?.slice(-10) }}</strong><small>{{ section === 'orders' ? when(row.creation) : section === 'inventory' ? row.item_group : section === 'people' ? row.user : section === 'customers' ? row.email : section === 'payments' ? row.delivery_user : row.accepting_orders ? 'Accepting orders' : 'Ordering paused' }}</small></td>
                    <td data-label="Shop / record"><span>{{ section === 'shops' ? row.company : section === 'customers' ? row.customer : row.shop_name }}</span><small v-if="section === 'shops'">{{ row.city || 'Location not set' }}</small></td>
                    <td data-label="Details"><template v-if="section === 'orders'"><strong>{{ money(row.amount, row.currency) }}</strong><small>{{ row.payment_status }}</small></template><template v-else-if="section === 'payments'"><strong>{{ money(row.collected_amount, row.currency) }}</strong><small :class="{ 'admin-variance': row.variance }">Difference: {{ money(row.variance, row.currency) }}</small></template><template v-else-if="section === 'inventory'"><strong>{{ row.available ?? '—' }} {{ row.stock_uom }}</strong></template><template v-else-if="section === 'people'">{{ row.membership_role }}</template><template v-else-if="section === 'shops'">{{ row.warehouse ? 'Warehouse set' : 'Warehouse needed' }}</template><template v-else>{{ row.mobile_no || 'No phone added' }}</template></td>
                    <td data-label="Status"><span class="admin-state" :class="{ good: ['Active', 'Delivered', 'Reconciled', 'In stock'].includes(row.status || row.stock_status) || (['people', 'customers'].includes(section) && row.enabled && row.account_enabled !== 0), warning: ['Requested', 'Awaiting Handover', 'Low stock', 'Setup needed'].includes(row.status || row.stock_status) }">{{ section === 'inventory' ? row.stock_status : section === 'people' || section === 'customers' ? row.enabled && row.account_enabled !== 0 ? 'Enabled' : 'Disabled' : row.status }}</span></td>
                    <td><div class="admin-table-actions"><template v-if="section === 'shops'"><RouterLink :to="{ name: 'shop-workspace', params: { shop: row.name } }">Open shop →</RouterLink><button type="button" :disabled="!!busy" @click="toggleShop(row)">{{ busy === row.name ? 'Saving…' : row.accepting_orders ? 'Pause orders' : 'Resume orders' }}</button><a :href="record('lc-shop', row.name)">Setup ↗</a></template><button v-else-if="['orders', 'inventory', 'payments'].includes(section)" type="button" @click="go(section, row.shop)">Manage →</button><template v-else-if="section === 'people'"><button type="button" @click="openSetup('membership', row)">Edit membership</button><a :href="record('user', row.user)">User account ↗</a></template><a v-else :href="record('customer', row.customer)">Open record ↗</a></div></td>
                  </tr>
                </tbody>
              </table>
            </div><p v-if="!rowsLoading && !rows.length" class="admin-empty">{{ search || status || selectedShop ? 'No matching records. Try changing your filters.' : 'No records yet. They will appear here as your platform grows.' }}</p>
          </section>
          <div class="admin-pagination"><span>Page {{ start / 20 + 1 }}</span><button type="button" :disabled="!start || rowsLoading" @click="loadRows(-20)">Previous</button><button type="button" :disabled="!hasMore || rowsLoading" @click="loadRows(20)">Next</button></div>
        </template>
      </template>
      <dialog ref="setupDialog" class="admin-setup-dialog" :aria-labelledby="setupKind === 'shop' ? 'admin-new-shop-title' : 'admin-membership-title'" @cancel="closeSetup">
        <header><div><span class="eyebrow">PLATFORM ADMINISTRATION</span><h2 v-if="setupKind === 'shop'" id="admin-new-shop-title">Create a shop</h2><h2 v-else id="admin-membership-title">{{ memberForm.name ? 'Edit membership' : 'Connect a team member' }}</h2></div><button type="button" aria-label="Close" :disabled="setupSaving" @click="closeSetup">×</button></header>
        <p v-if="setupLoading" role="status">Loading setup options…</p><p v-if="setupError" class="lc-notice" role="alert">{{ setupError }}</p>
        <form v-if="setup && !setupLoading" @submit.prevent="saveSetup">
          <fieldset :disabled="setupSaving">
            <template v-if="setupKind === 'shop'"><label>Shop name<input v-model="shopForm.shop_name" maxlength="140" required placeholder="Your shop's name"></label><label>Company<select v-model="shopForm.company"><option value="">Create a company with the same shop name</option><option v-for="company in setup.companies" :key="company">{{ company }}</option></select></label><template v-if="!shopForm.company"><div class="admin-dialog-row"><label>Country<select v-model="shopForm.country" required><option value="">Choose country</option><option v-for="country in setup.countries" :key="country">{{ country }}</option></select></label><label>Currency<select v-model="shopForm.currency" required><option value="">Choose currency</option><option v-for="currency in setup.currencies" :key="currency">{{ currency }}</option></select></label></div></template><p class="admin-dialog-note">The shop starts in Draft. Set its warehouse, address, delivery and payment options before opening it to customers.</p></template>
            <template v-else><label>Shop<select v-model="memberForm.shop" required :disabled="!!memberForm.name"><option value="">Choose a shop</option><option v-for="shop in summary?.shop_options || []" :key="shop.name" :value="shop.name">{{ shop.shop_name }}</option><option v-if="memberForm.shop && !summary?.shop_options.some(shop => shop.name === memberForm.shop)" :value="memberForm.shop">Selected shop</option></select></label><template v-if="!memberForm.name"><label>Find an existing user<input v-model="userSearch" type="search" placeholder="Search a name or email"></label><label>User<select v-model="memberForm.user" required><option value="">Choose user</option><option v-for="user in setup.users" :key="user.name" :value="user.name">{{ user.full_name }} · {{ user.name }}</option><option v-if="memberForm.user && !setup.users.some(user => user.name === memberForm.user)" :value="memberForm.user">{{ memberForm.user }}</option></select></label></template><p v-else class="admin-dialog-note">{{ memberForm.user }}</p><label>Membership role<select v-model="memberForm.membership_role"><option value="Owner">Shop owner</option><option value="Staff">Shop staff</option><option value="Driver">Delivery partner</option></select></label><label class="admin-dialog-checkbox"><input v-model="memberForm.enabled" type="checkbox">Membership enabled</label><p class="admin-dialog-note">The matching app role is assigned automatically. A rider can have memberships in multiple shops.</p></template>
            <div class="admin-dialog-actions"><button type="button" @click="closeSetup">Cancel</button><button type="submit" class="admin-primary">{{ setupSaving ? 'Saving…' : setupKind === 'shop' ? 'Create shop' : 'Save membership' }}</button></div>
          </fieldset>
        </form>
      </dialog>
      <footer class="admin-page-footer"><span>Local Commerce · Platform administration</span><small v-if="summary">Updated {{ when(summary.updated_at) }}</small></footer>
    </div>
  </div>
</template>
