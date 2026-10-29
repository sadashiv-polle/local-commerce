<script setup>
import Home from '@primeicons/vue/home'
import Shop from '@primeicons/vue/shop'
import Receipt from '@primeicons/vue/receipt'
import User from '@primeicons/vue/user'
import List from '@primeicons/vue/list'
import MapIcon from '@primeicons/vue/map'
import MapMarker from '@primeicons/vue/map-marker'
import Truck from '@primeicons/vue/truck'
import ShoppingBag from '@primeicons/vue/shopping-bag'
import Building from '@primeicons/vue/building'
const props = defineProps({ name: { type: String, required: true } })
const icons = { home: Home, shop: Shop, orders: Receipt, account: User, list: List, map: MapIcon, location: MapMarker, delivery: Truck, shopping: ShoppingBag, work: Building }
</script>
<template>
  <component :is="icons[props.name] || MapMarker" class="app-icon" :size="24" aria-hidden="true" focusable="false" />
</template>
<style>
.app-icon { display: inline-block; flex-shrink: 0; vertical-align: middle; }
</style>
