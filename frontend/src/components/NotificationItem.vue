<script setup lang="ts">
/**
 * One notification (the top bar's menu and the Notifications page): its severity's icon and
 * color (information, warning, error, completion), the title ("System" beside it when global),
 * the message, how long ago; unread ones are tinted and marked with a dot.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { alertLook, alertText, alertTitle, relativeTime } from '@/alerts'
import type { Alert } from '@/modules/inventory/api'

const props = defineProps<{ alert: Alert }>()
defineEmits<{ open: [] }>()
const { t, te, locale } = useI18n()

const look = computed(() => alertLook(props.alert.severity))
</script>

<template>
  <div
    class="notification-item"
    :class="{ unread: !alert.read }"
    role="button"
    tabindex="0"
    data-testid="alert"
    @click="$emit('open')"
    @keydown.enter="$emit('open')"
  >
    <v-avatar
      :color="look.color"
      variant="tonal"
      size="40"
      class="flex-shrink-0"
      :data-testid="`severity-${alert.severity}`"
    >
      <v-icon :icon="look.icon" size="22" />
    </v-avatar>
    <div class="flex-grow-1 min-w-0">
      <div class="d-flex align-center flex-wrap ga-2">
        <span class="title" data-testid="alert-title">{{ alertTitle(alert, t, te) }}</span>
        <!-- A global notice (sent to everyone), not about the user's own work -->
        <v-chip
          v-if="alert.scope === 'system'"
          size="x-small"
          variant="tonal"
          prepend-icon="mdi-earth"
          data-testid="scope-system"
        >
          {{ $t('notifications.scopes.system') }}
        </v-chip>
      </div>
      <div class="text-body-2 text-medium-emphasis" data-testid="alert-text">
        {{ alertText(alert, t) }}
      </div>
      <div class="text-caption text-disabled mt-1" :title="alert.created_at">
        {{ relativeTime(alert.created_at, locale) }}
      </div>
    </div>
    <span v-if="!alert.read" class="dot bg-primary" data-testid="unread-dot" />
  </div>
</template>

<style scoped>
.notification-item {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 16px 20px;
  cursor: pointer;
  transition: background-color 0.15s;
}
.notification-item:hover {
  background: rgba(var(--v-theme-on-surface), 0.04);
}
.notification-item.unread {
  background: rgba(var(--v-theme-primary), 0.06);
}
.notification-item.unread:hover {
  background: rgba(var(--v-theme-primary), 0.1);
}
.notification-item:focus-visible {
  outline: 2px solid rgb(var(--v-theme-primary));
  outline-offset: -2px;
}
.title {
  font-weight: 600;
  line-height: 1.4;
}
.min-w-0 {
  min-width: 0;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-top: 8px;
  flex-shrink: 0;
}
</style>
