<script setup lang="ts">
/**
 * Horizon's logo: the mark over the name and the slogan ("One Step Ahead"), in the theme's font.
 * `inverse`: on a dark background (the name turns light).
 */
import HorizonMark from './HorizonMark.vue'

withDefaults(defineProps<{ markHeight?: number; inverse?: boolean }>(), {
  markHeight: 72,
  inverse: false,
})
</script>

<template>
  <div class="horizon-logo" :class="{ inverse }" data-testid="horizon-logo">
    <HorizonMark :height="markHeight" />
    <div class="name" :style="{ fontSize: `${markHeight * 0.42}px` }">{{ $t('app.name') }}</div>
    <div class="slogan" :style="{ fontSize: `${Math.max(markHeight * 0.14, 10)}px` }">
      {{ $t('app.slogan') }}
    </div>
  </div>
</template>

<style scoped>
.horizon-logo {
  display: flex;
  flex-direction: column;
  align-items: center;
  line-height: 1.1;
}
.name {
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #3a3a3a;
  margin-top: 4px;
}
.slogan {
  font-weight: 500;
  letter-spacing: 0.4em;
  text-transform: uppercase;
  color: #6b6b6b;
  margin-top: 4px;
  /* Letter spacing also follows the last letter: keep it centered */
  padding-left: 0.4em;
}
/* Dark themes and the dark side menu: light letters */
.v-theme--dark .name,
.inverse .name {
  color: #f4f4f4;
}
.v-theme--dark .slogan,
.inverse .slogan {
  color: #b9c0c8;
}
</style>
