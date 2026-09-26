<script setup>
import { computed, ref, watch } from 'vue'
const props = defineProps({ name: String, image: String })
const failed = ref(false)
watch(() => props.image, () => { failed.value = false })
const initial = computed(() => (props.name || '').trim().slice(0, 1).toUpperCase() || '?')
</script>

<template>
  <span class="profile-photo-avatar" aria-hidden="true">
    <img v-if="image && !failed" :src="image" alt="" @error="failed = true">
    <template v-else>{{ initial }}</template>
  </span>
</template>

<style scoped>
.profile-photo-avatar { overflow: hidden; }
.profile-photo-avatar img { display: block; width: 100%; height: 100%; object-fit: cover; border-radius: inherit; }
</style>
