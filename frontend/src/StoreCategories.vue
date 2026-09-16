<script setup>
import { computed, onMounted, ref } from 'vue'
import { call } from './api.js'
const menu = ref({ categories: [] }), activeSection = ref(''), loading = ref(true), error = ref('')
const headings = computed(() => [...new Set(menu.value.categories.map(row => row.section))])
const sections = computed(() => headings.value.filter(name => !activeSection.value || activeSection.value === name).map(name => ({ name, categories: menu.value.categories.filter(row => row.section === name) })))
function icon(group) {
  return ({ Fish: '🐟', Seafood: '🦐', Rice: '🍚', Groceries: '🛒', Fruits: '🍎', Vegetables: '🥬', 'Meat & Poultry': '🍗', 'Dairy & Eggs': '🥛', Bakery: '🥖', 'Fast Food': '🍔', Snacks: '🍿', Beverages: '🧃', 'Household Essentials': '🧹', 'Personal Care': '🧴' })[group] || '🛍️'
}
async function load() {
  loading.value = true; error.value = ''
  try { menu.value = await call('storefront.category_menu') }
  catch (e) { error.value = e.message } finally { loading.value = false }
}
onMounted(load)
</script>
<template>
  <div class="store-page all-categories-page">
    <RouterLink to="/store" class="categories-back">← Back to store</RouterLink>
    <header class="all-categories-heading"><h1>Shop by category</h1><p>Find your everyday favourites.</p></header>
    <p v-if="loading" role="status">Loading categories…</p><p v-if="error" role="alert" class="lc-notice">{{ error }} <button type="button" @click="load">Retry</button></p>
    <p v-if="!loading && !error && !menu.categories.length" class="lc-empty">Browse the store to find products from local shops.</p>
    <section v-if="menu.categories.length" class="store-category-menu" aria-label="Shop by category">
      <nav class="category-section-tabs" aria-label="Category sections"><button type="button" :class="{ active: !activeSection }" :aria-pressed="!activeSection" @click="activeSection = ''"><span aria-hidden="true">🛍️</span>All</button><button v-for="(name, index) in headings" :key="name" type="button" :class="{ active: activeSection === name }" :aria-pressed="activeSection === name" @click="activeSection = name"><span aria-hidden="true">{{ index % 2 ? '🍽️' : '🛒' }}</span>{{ name }}</button></nav>
      <section v-for="section in sections" :key="section.name" class="category-tile-section"><h2>{{ section.name }}</h2><div class="category-tile-grid"><RouterLink v-for="category in section.categories" :key="category.item_group" class="category-tile" :to="{ path: '/store', query: { category: category.item_group } }"><span class="category-tile-art"><img v-if="category.image" :src="category.image" alt="" loading="lazy" @error="category.image = ''"><span v-else aria-hidden="true">{{ icon(category.item_group) }}</span></span><strong>{{ category.label }}</strong></RouterLink></div></section>
    </section>
  </div>
</template>
