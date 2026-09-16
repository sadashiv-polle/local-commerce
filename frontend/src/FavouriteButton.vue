<script setup>
import { computed, inject, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { call } from './api.js'
import { favouriteItems, loadFavourites, setFavourite } from './favourites-state.js'
const props = defineProps({ item: { type: String, required: true }, shop: { type: String, required: true } })
const session = inject('session'), router = useRouter()
const saved = computed(() => favouriteItems.value.has(props.item)), busy = ref(false), error = ref('')
onMounted(async () => {
  if (session.value.user === 'Guest') return
  try { await loadFavourites(session.value.user) } catch { /* Retry when saving. */ }
})
async function toggle() {
  if (session.value.user === 'Guest') { router.push({ path: '/login', query: { next: `/store/${props.shop}?item=${encodeURIComponent(props.item)}` } }); return }
  busy.value = true; error.value = ''
  try { const result = await call('favourites.toggle', { shop: props.shop, item: props.item, saved: saved.value ? 0 : 1 }, true); setFavourite(props.item, result.saved) }
  catch (e) { error.value = e.message }
  finally { busy.value = false }
}
</script>

<template>
  <div class="favourite-control"><button type="button" class="favourite-heart" :class="{ saved }" :aria-label="saved ? 'Remove from favourites' : 'Save to favourites'" :aria-pressed="saved" :disabled="busy" @click.stop="toggle"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20s-8-5-8-11a4.5 4.5 0 0 1 8-2.8A4.5 4.5 0 0 1 20 9c0 6-8 11-8 11Z" /></svg></button><small v-if="error" class="favourite-error" role="alert">{{ error }}</small></div>
</template>
