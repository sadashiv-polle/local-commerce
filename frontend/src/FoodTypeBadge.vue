<script setup>
defineProps({ value: { type: String, default: '' } })
</script>
<template>
  <span v-if="value === 'Veg' || value === 'Non-veg'" class="food-type-badge" :class="{ 'non-veg': value === 'Non-veg' }">
    <svg class="food-type-symbol" viewBox="0 0 20 20" aria-hidden="true" focusable="false">
      <rect x="1" y="1" width="18" height="18" rx="3" fill="none" stroke="currentColor" stroke-width="1.5" />
      <path v-if="value === 'Non-veg'" d="M10 5 L15 14 H5 Z" fill="currentColor" />
      <circle v-else cx="10" cy="10" r="4.5" fill="currentColor" />
    </svg>
    <span>{{ value }}</span>
  </span>
</template>
<style scoped>
.food-type-badge { display: inline-flex; align-items: center; gap: 8px; padding: 5px 9px; border-radius: 7px; background: #eef7f0; color: #18733b; font-family: inherit; font-size: 13px; font-weight: 600; line-height: 20px; letter-spacing: .01em; white-space: nowrap; vertical-align: middle; }
.food-type-badge.non-veg { color: #b52b2b; background: #fff1f0; }
.food-type-symbol { display: block; width: 20px; height: 20px; flex: 0 0 20px; }
</style>
