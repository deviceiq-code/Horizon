<script setup lang="ts">
/**
 * One setting as a row (the Haze settings layout): its title and a line about it on the left,
 * the control on the right (default slot). Wide controls go below the text (`below` slot).
 * On phones the control drops under the text.
 */
defineProps<{ title: string; description?: string }>()
</script>

<template>
  <div class="setting-row">
    <div class="setting-row__main">
      <div class="setting-row__text">
        <div class="setting-row__title">{{ title }}</div>
        <div v-if="description || $slots.description" class="setting-row__description">
          <slot name="description">{{ description }}</slot>
        </div>
      </div>
      <div v-if="$slots.default" class="setting-row__control">
        <slot />
      </div>
    </div>
    <div v-if="$slots.below" class="setting-row__below">
      <slot name="below" />
    </div>
  </div>
</template>

<style scoped>
.setting-row {
  padding: 20px 24px;
}
.setting-row + .setting-row {
  border-top: thin solid rgba(var(--v-border-color), var(--v-border-opacity));
}
.setting-row__main {
  display: flex;
  align-items: center;
  gap: 16px 24px;
  flex-wrap: wrap;
}
.setting-row__text {
  flex: 1 1 280px;
  min-width: 0;
}
.setting-row__title {
  font-weight: 600;
}
.setting-row__description {
  font-size: 0.875rem;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.setting-row__control {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex: 0 1 auto;
  max-width: 100%;
}
.setting-row__below {
  margin-top: 16px;
}
</style>
