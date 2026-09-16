<script setup>
defineProps({ name: { type: String, default: 'overview' } })
const paths = {
  overview: 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
  shops: 'M3 10h18L19 3H5z M5 10v11h14V10 M9 21v-7h6v7',
  orders: 'M7 3h10v3h3v15H4V6h3z M8 11h8 M8 16h5',
  inventory: 'm3 7 9-4 9 4-9 4z M3 7v10l9 4 9-4V7 M12 11v10',
  people: 'M16 21v-3a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v3 M9 10a4 4 0 1 0 0-8 4 4 0 0 0 0 8 M18 3a4 4 0 0 1 0 7 M18 14a4 4 0 0 1 4 4v3',
  customers: 'M20 21v-2a7 7 0 0 0-14 0v2 M13 11a5 5 0 1 0 0-10 5 5 0 0 0 0 10',
  payments: 'M2 5h20v14H2z M2 10h20 M6 15h4',
  storefront: 'M3 3h18v18H3z M3 8h18 M8 8v13 M12 12h5 M12 16h3',
  settings: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M12 2v3 M12 19v3 M2 12h3 M19 12h3 M5 5l2 2 M17 17l2 2 M5 19l2-2 M17 7l2-2',
}
</script>
<template><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path :d="paths[name] || paths.overview" /></svg></template>
