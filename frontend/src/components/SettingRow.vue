<script setup lang="ts">
/**
 * One setting as a row (the Haze settings layout): its title and a line about it on the left,
 * the control on the right (default slot). Wide controls go below the text (`below` slot).
 * On phones the control drops under the text. `child`: a setting that depends on the one
 * above (e.g. the threshold of Automatic Scope) — indented, with no separator between them.
 */
defineProps<{ title: string; description?: string; child?: boolean }>()
</script>

<template>
  <div class="setting-row" :class="{ 'setting-row--child': child }">
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
.setting-row + .setting-row:not(.setting-row--child) {
  border-top: thin solid rgba(var(--v-border-color), var(--v-border-opacity));
}
/* Under its parent: indented, close to it, no separator */
.setting-row--child {
  padding-top: 0;
  padding-left: 48px;
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
