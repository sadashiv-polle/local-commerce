<script setup>
defineProps({ value: { type: String, default: '' } })
</script>
<template>
  <span v-if="value === 'Veg' || value === 'Non-veg'" class="food-type-badge" :class="{ 'non-veg': value === 'Non-veg' }">
    <span class="food-type-symbol" aria-hidden="true"><span /></span>{{ value }}
  </span>
</template>
<style scoped>
.food-type-badge { display: inline-flex; align-items: center; gap: 6px; color: #18733b; font-size: .8rem; font-weight: 650; }
.food-type-badge.non-veg { color: #bd2929; }
.food-type-symbol { display: inline-flex; align-items: center; justify-content: center; width: 17px; height: 17px; border: 1.5px solid currentColor; border-radius: 2px; flex-shrink: 0; }
.food-type-symbol span { width: 9px; height: 9px; border-radius: 50%; background: currentColor; }
.non-veg .food-type-symbol span { border-radius: 0; clip-path: polygon(50% 0, 100% 100%, 0 100%); }
</style>
