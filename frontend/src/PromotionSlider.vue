<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { call } from './api.js'
const config = ref(null), current = ref(0), paused = ref(false), hovering = ref(false), focused = ref(false)
const slides = computed(() => config.value?.slides || [])
let timer, startX = null, motion
function move(delta) { current.value = (current.value + delta + slides.value.length) % slides.value.length }
function touchEnd(event) {
  if (startX != null) {
    const distance = event.changedTouches[0].clientX - startX
    if (Math.abs(distance) > 45) move(distance < 0 ? 1 : -1)
  }
  startX = null
}
onMounted(async () => {
  motion = window.matchMedia('(prefers-reduced-motion: reduce)')
  try { config.value = await call('storefront.promotions') } catch { return }
  timer = window.setInterval(() => {
    if (slides.value.length > 1 && config.value.autoplay && !paused.value && !hovering.value && !focused.value && !document.hidden && !motion.matches) move(1)
  }, config.value.interval * 1000)
})
onBeforeUnmount(() => window.clearInterval(timer))
</script>
<template>
  <section v-if="slides.length" class="promotion-slider" aria-label="Shop offers" aria-roledescription="carousel" @mouseenter="hovering = true" @mouseleave="hovering = false" @focusin="focused = true" @focusout="focused = $event.currentTarget.contains($event.relatedTarget)">
    <div class="promotion-frame" @touchstart.passive="startX = $event.touches[0].clientX" @touchend.passive="touchEnd" @touchcancel="startX = null">
      <template v-for="(slide, index) in slides" :key="index">
        <div v-if="index === current" role="group" aria-roledescription="slide" :aria-label="`${index + 1} of ${slides.length}: ${slide.title}`">
          <RouterLink v-if="slide.link" :to="slide.link"><img :src="slide.image" :alt="slide.title"></RouterLink>
          <img v-else :src="slide.image" :alt="slide.title">
        </div>
      </template>
    </div>
    <div class="promotion-caption"><strong>{{ slides[current].title }}</strong><div v-if="slides.length > 1" class="promotion-controls"><button type="button" aria-label="Previous offer" @click="move(-1)">‹</button><span>{{ current + 1 }} / {{ slides.length }}</span><button type="button" aria-label="Next offer" @click="move(1)">›</button><button v-if="config.autoplay" type="button" :aria-pressed="paused" @click="paused = !paused">{{ paused ? 'Play' : 'Pause' }}</button></div></div>
  </section>
</template>
<style>
#lc-app .promotion-slider { margin: 20px 0; overflow: hidden; border: 1px solid #dce6dc; border-radius: 18px; background: #fff; }
#lc-app .promotion-frame { background: #f0f4eb; touch-action: pan-y; }
#lc-app .promotion-frame img { display: block; width: 100%; height: clamp(140px, 23vw, 280px); object-fit: contain; }
#lc-app .promotion-caption { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 16px; }
#lc-app .promotion-caption strong { font-size: 14px; overflow-wrap: anywhere; min-width: 0; }
#lc-app .promotion-controls { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
#lc-app .promotion-controls button { min-width: 44px; min-height: 44px; padding: 6px 10px; border-radius: 10px; font-size: 13px; }
#lc-app .promotion-controls span { font-size: 12px; color: #627568; }
@media (max-width: 600px) { #lc-app .promotion-caption { flex-wrap: wrap; padding: 8px 12px; } #lc-app .promotion-controls { margin-left: auto; } }
</style>
