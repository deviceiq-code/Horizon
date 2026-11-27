<script setup lang="ts">
/**
 * Horizon's mark: the sun rising over the horizon (the logo without its name). Fixed brand
 * colors in any theme (orange sun, emerald horizon); `height` in px (the width follows, 200:112).
 */
import { useId } from 'vue'

withDefaults(defineProps<{ height?: number }>(), { height: 40 })
// Each instance its own gradients (one hidden copy would blank the others' references)
const id = useId()
</script>

<template>
  <svg
    viewBox="0 0 200 112"
    :height="height"
    :width="(height * 200) / 112"
    role="img"
    aria-hidden="true"
    class="horizon-mark"
  >
    <defs>
      <linearGradient :id="`${id}-sun`" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#FBC531" />
        <stop offset="1" stop-color="#F39C12" />
      </linearGradient>
      <linearGradient :id="`${id}-sea`" x1="0" y1="0" x2="1" y2="0">
        <!-- The system's emerald (Emerald Slate) -->
        <stop offset="0" stop-color="#00A883" />
        <stop offset="0.5" stop-color="#00926F" />
        <stop offset="1" stop-color="#00A883" />
      </linearGradient>
    </defs>
    <!-- Rays, long and short in turn (made by a script: thin triangles around the sun) -->
    <path
      :fill="`url(#${id}-sun)`"
      d="M126.3 73.1 L169.3 70.3 L127.2 79.4 Z M125.3 70.0 L150.3 66.7 L126.9 76.2 Z M123.9 67.1 L165.1 54.2 L126.3 73.0 Z M122.2 64.3 L145.7 55.2 L125.3 69.9 Z M120.2 61.8 L157.1 39.5 L123.9 67.0 Z M117.9 59.5 L138.6 45.1 L122.2 64.3 Z M115.3 57.5 L145.9 27.2 L120.1 61.7 Z M112.5 55.9 L129.2 37.0 L117.8 59.5 Z M109.6 54.5 L132.2 17.8 L115.3 57.5 Z M106.5 53.6 L118.2 31.3 L112.5 55.8 Z M103.3 53.0 L116.6 12.0 L109.5 54.5 Z M100.1 52.8 L106.2 28.4 L106.4 53.6 Z M96.8 53.0 L100.0 10.0 L103.2 53.0 Z M93.6 53.6 L93.9 28.4 L100.0 52.8 Z M90.5 54.5 L83.5 12.0 L96.8 53.0 Z M87.6 55.8 L81.8 31.3 L93.6 53.6 Z M84.8 57.5 L67.9 17.8 L90.5 54.5 Z M82.2 59.4 L70.8 36.9 L87.5 55.9 Z M79.9 61.7 L54.1 27.1 L84.7 57.5 Z M77.9 64.2 L61.5 45.1 L82.2 59.5 Z M76.1 67.0 L42.9 39.5 L79.8 61.8 Z M74.8 69.9 L54.3 55.1 L77.8 64.3 Z M73.7 73.0 L35.0 54.1 L76.1 67.0 Z M73.1 76.1 L49.8 66.6 L74.7 70.0 Z M72.8 79.4 L30.7 70.2 L73.7 73.0 Z"
    />
    <path :fill="`url(#${id}-sun)`" d="M77 80 A23 23 0 0 1 123 80 Z" />
    <!-- The horizon -->
    <path :fill="`url(#${id}-sea)`" d="M4 96 Q100 60 196 96 Q100 76 4 96 Z" />
  </svg>
</template>
