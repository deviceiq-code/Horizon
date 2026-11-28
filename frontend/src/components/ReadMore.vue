<script setup lang="ts">
/**
 * Long content kept to a comfortable reading height: past `maxHeight` it is cut (fading out)
 * and "Read More" unfolds all of it ("Read Less" folds it again). `more`: there is more than
 * what is shown even when it fits (e.g. older entries not loaded yet) — the button shows and
 * `expand` asks the parent for them the first time.
 */
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

const props = withDefaults(defineProps<{ maxHeight?: number; more?: boolean }>(), {
  maxHeight: 320,
  more: false,
})
const emit = defineEmits<{ expand: [] }>()

const content = ref<HTMLElement | null>(null)
const expanded = ref(false)
const overflowing = ref(false)
let asked = false

function measure() {
  const el = content.value
  overflowing.value = !!el && el.scrollHeight > props.maxHeight + 1
}

let observer: ResizeObserver | undefined
onMounted(async () => {
  await nextTick()
  measure()
  if (typeof ResizeObserver !== 'undefined' && content.value) {
    observer = new ResizeObserver(measure)
    observer.observe(content.value)
  }
})
onBeforeUnmount(() => observer?.disconnect())

function toggle() {
  expanded.value = !expanded.value
  if (expanded.value && !asked) {
    asked = true
    emit('expand')
  }
}

defineExpose({ measure })
</script>

<template>
  <div class="read-more">
    <div
      ref="content"
      class="read-more__content"
      :class="{ 'read-more__content--cut': !expanded && overflowing }"
      :style="expanded ? undefined : { maxHeight: `${maxHeight}px` }"
      data-testid="read-more-content"
    >
      <slot />
    </div>
    <v-btn
      v-if="overflowing || more || expanded"
      variant="text"
      size="small"
      color="primary"
      class="px-1 mt-1"
      :append-icon="expanded ? 'mdi-chevron-up' : 'mdi-chevron-down'"
      data-testid="read-more"
      @click="toggle"
    >
      {{ expanded ? $t('common.readLess') : $t('common.readMore') }}
    </v-btn>
  </div>
</template>

<style scoped>
.read-more__content {
  overflow: hidden;
}
/* The cut end fades out (the page's own background) */
.read-more__content--cut {
  mask-image: linear-gradient(to bottom, black calc(100% - 64px), transparent);
}
</style>
