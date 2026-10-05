<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { call } from './api.js'
const config = ref(null), current = ref(0), holding = ref(false), focused = ref(false)
const slides = computed(() => config.value?.slides || [])
let timer, startX = null, motion, pointerId = null, pressedAt = 0, suppressClick = false, disposed = false
function schedule() {
  window.clearTimeout(timer)
  if (disposed || !config.value?.autoplay || slides.value.length < 2 || holding.value || focused.value || document.hidden || motion?.matches) return
  timer = window.setTimeout(() => { current.value = (current.value + 1) % slides.value.length; schedule() }, config.value.interval * 1000)
}
function move(delta) { current.value = (current.value + delta + slides.value.length) % slides.value.length; schedule() }
function press(event) {
  if (!event.isPrimary || event.button !== 0) return
  pointerId = event.pointerId; startX = event.clientX; pressedAt = Date.now(); suppressClick = false
  holding.value = true; schedule()
}
function release(event) {
  if (event.pointerId !== pointerId) return
  const distance = event.clientX - startX
  suppressClick = Math.abs(distance) > 45 || Date.now() - pressedAt > 350
  holding.value = false; pointerId = null; startX = null
  if (event.type === 'pointerup' && Math.abs(distance) > 45) move(distance < 0 ? 1 : -1)
  else schedule()
}
function click(event) {
  if (suppressClick && event.detail !== 0) { event.preventDefault(); event.stopPropagation(); suppressClick = false }
}
function focus(event) {
  focused.value = !!event.target.matches(':focus-visible'); schedule()
}
function blur() { holding.value = false; pointerId = null; schedule() }
onMounted(async () => {
  motion = window.matchMedia('(prefers-reduced-motion: reduce)')
  motion.addEventListener('change', schedule)
  window.addEventListener('pointerup', release)
  window.addEventListener('pointercancel', release)
  window.addEventListener('blur', blur)
  document.addEventListener('visibilitychange', schedule)
  try { config.value = await call('storefront.promotions') } catch { return }
  schedule()
})
onBeforeUnmount(() => {
  disposed = true; window.clearTimeout(timer)
  motion?.removeEventListener('change', schedule)
  window.removeEventListener('pointerup', release)
  window.removeEventListener('pointercancel', release)
  window.removeEventListener('blur', blur)
  document.removeEventListener('visibilitychange', schedule)
})
</script>
<template>
  <section v-if="slides.length" class="promotion-slider" aria-label="Shop offers" aria-roledescription="carousel" @focusin="focus" @focusout="focused = false; schedule()">
    <div class="promotion-frame" :class="{ holding }" @pointerdown="press" @click.capture="click" @contextmenu.prevent @dragstart.prevent>
      <template v-for="(slide, index) in slides" :key="index">
        <div v-if="index === current" role="group" aria-roledescription="slide" :aria-label="`${index + 1} of ${slides.length}: ${slide.title}`">
          <RouterLink v-if="slide.link" :to="slide.link"><img :src="slide.image" :alt="slide.title"></RouterLink>
          <img v-else :src="slide.image" :alt="slide.title">
        </div>
      </template>
    </div>
    <div class="promotion-caption"><strong>{{ slides[current].title }}</strong><div v-if="slides.length > 1" class="promotion-controls"><button type="button" aria-label="Previous offer" @click="move(-1)">‹</button><span>{{ current + 1 }} / {{ slides.length }}</span><button type="button" aria-label="Next offer" @click="move(1)">›</button></div></div>
  </section>
</template>
<style>
#lc-app .promotion-slider { margin: 20px 0; overflow: hidden; border: 1px solid #dce6dc; border-radius: 18px; background: #fff; box-shadow: 0 5px 20px #173e2008; }
#lc-app .promotion-frame { background: #f0f4eb; touch-action: pan-y; user-select: none; -webkit-user-select: none; -webkit-touch-callout: none; }
#lc-app .promotion-frame img { display: block; width: 100%; height: clamp(140px, 23vw, 280px); object-fit: contain; -webkit-user-drag: none; -webkit-touch-callout: none; }
#lc-app .promotion-caption { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 16px; }
#lc-app .promotion-caption strong { font-size: 14px; overflow-wrap: anywhere; min-width: 0; }
#lc-app .promotion-controls { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
#lc-app .promotion-controls button { min-width: 44px; min-height: 44px; padding: 6px 10px; border-radius: 50%; font-size: 24px; line-height: 1; background: #f0f5ee; color: #176547; border: 1px solid #e0e8dc; }
#lc-app .promotion-frame.holding { cursor: grabbing; }
#lc-app .promotion-controls span { min-width: 40px; text-align: center; font-variant-numeric: tabular-nums; font-size: 12px; color: #627568; }
@media (max-width: 600px) { #lc-app .promotion-caption { flex-wrap: wrap; padding: 8px 12px; } #lc-app .promotion-controls { margin-left: auto; } }
</style>
