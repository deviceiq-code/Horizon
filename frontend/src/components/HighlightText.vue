<script setup lang="ts">
/** A text with the words searched for marked (accents and letter case ignored). */
import { computed } from 'vue'
import { highlight } from '@/search'

const props = defineProps<{ text: string; q: string }>()
const parts = computed(() => highlight(props.text, props.q))
</script>

<template>
  <span
    ><template v-for="(part, index) in parts" :key="index"
      ><mark v-if="part.match" class="search-match">{{ part.text }}</mark
      ><template v-else>{{ part.text }}</template></template
    ></span
  >
</template>

<style scoped>
.search-match {
  background: rgba(var(--v-theme-primary), 0.16);
  color: inherit;
  border-radius: 3px;
  padding: 0 1px;
}
</style>
