<script setup>
import { ref } from 'vue'
const selected = ref('All essentials')
const browse = ref(null)
const categories = [
  ['All essentials', '🛍️'], ['Vegetables', '🥬'], ['Fruits', '🍊'], ['Fish & meat', '🐟'],
  ['Dairy & eggs', '🥛'], ['Bakery', '🥖'], ['Groceries', '🫘'], ['Meals', '🍲'],
]
</script>

<template>
  <div class="store-page">
    <section class="store-hero">
      <div><span class="eyebrow">GOOD THINGS, CLOSE TO HOME</span><h1>Your neighbourhood.<br>Your everyday essentials.</h1><p>Fresh finds and familiar favourites.<br>Discover a better way to shop local.</p><button class="primary" @click="browse?.scrollIntoView()">Explore the neighbourhood <span>↗</span></button></div>
      <div class="hero-art" aria-hidden="true"><span class="art-label">FRESH · LOCAL · EVERYDAY</span><div class="produce">🥬<span>🍊</span>🥖</div><div class="market-bag">local<span>good things inside.</span></div><span class="art-sticker">A little<br>closer.</span></div>
    </section>
    <section ref="browse" class="browse-section">
      <div class="section-title"><div><span class="eyebrow">WHAT'S ON YOUR LIST?</span><h2>Shop your everyday</h2></div><span class="muted">A whole neighbourhood of possibilities</span></div>
      <div class="category-grid"><button v-for="[label, emoji] in categories" :key="label" :aria-pressed="selected === label" :class="{ chosen: selected === label }" @click="selected = label"><span aria-hidden="true">{{ emoji }}</span><strong>{{ label }}</strong></button></div>
    </section>
    <section class="opening-card"><div class="opening-icon" aria-hidden="true">⌂</div><div><span class="eyebrow">YOUR NEIGHBOURHOOD MARKETPLACE</span><h2>{{ selected === 'All essentials' ? 'Something good is coming.' : `${selected}, closer to home.` }}</h2><p>We're getting the shelves ready. Shops and products will appear here when customer shopping opens.</p><span class="status-pill">Shopping opens soon</span></div></section>
    <div class="values"><div><strong>Local at heart</strong><p>Your neighbourhood businesses, together.</p></div><div><strong>Everyday made easier</strong><p>One place for the things you need.</p></div><div><strong>More choice, closer by</strong><p>From fresh produce to familiar favourites.</p></div></div>
  </div>
</template>
