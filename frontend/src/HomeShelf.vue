<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
defineProps({ label: { type: String, required: true } })
const rail = ref(null), canBack = ref(false), canNext = ref(false)
let observer
function update() {
  const el = rail.value
  if (!el) return
  canBack.value = el.scrollLeft > 2
  canNext.value = el.scrollLeft + el.clientWidth < el.scrollWidth - 2
}
function move(direction) {
  rail.value?.scrollBy({ left: direction * rail.value.clientWidth * .85, behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' })
}
onMounted(async () => {
  await nextTick()
  observer = new ResizeObserver(update)
  observer.observe(rail.value)
  for (const child of rail.value.children) observer.observe(child)
  update()
})
onBeforeUnmount(() => observer?.disconnect())
</script>
<template>
  <div class="home-shelf">
    <div ref="rail" class="home-shelf-rail" tabindex="0" role="region" :aria-label="label" @scroll.passive="update"><slot /></div>
    <div v-if="canBack || canNext" class="home-shelf-controls">
      <span>Explore more <span aria-hidden="true">↔</span></span>
      <div><button type="button" :disabled="!canBack" :aria-label="`Previous ${label}`" @click="move(-1)">←</button><button type="button" :disabled="!canNext" :aria-label="`Next ${label}`" @click="move(1)">→</button></div>
    </div>
  </div>
</template>
