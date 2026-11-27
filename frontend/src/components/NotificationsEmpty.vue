<script setup lang="ts">
/** No notifications (the top bar's menu and the Notifications page): a bell crossed out. */
</script>

<template>
  <div class="notifications-empty" data-testid="notifications-empty">
    <v-icon icon="mdi-bell-off-outline" size="48" class="icon mb-4" />
    <div class="text-h6 font-weight-medium">{{ $t('notifications.empty') }}</div>
    <div class="text-body-1 text-medium-emphasis mt-1">{{ $t('notifications.emptyHint') }}</div>
  </div>
</template>

<style scoped>
.notifications-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 40px 24px;
}
.icon {
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
</style>
