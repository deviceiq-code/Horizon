<script setup lang="ts">
/**
 * How users are shown everywhere (top bar, "created by", history…): username, first name or
 * full name ("First Last" or "Last, First"). Settings → System, administrators only.
 */
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { useNotificationsStore } from '@/stores/notifications'
import {
  useSystemSettingsStore,
  type FullNameOrder,
  type UserNameDisplay,
} from '@/stores/systemSettings'

const { t } = useI18n()
const store = useSystemSettingsStore()
const auth = useAuthStore()
const notifications = useNotificationsStore()

const display = ref<UserNameDisplay>('full_name')
const order = ref<FullNameOrder>('first_last')
const saving = ref(false)

onMounted(async () => {
  try {
    const settings = await store.load()
    display.value = settings.user_name_display
    order.value = settings.full_name_order
  } catch {
    notifications.notify(t('common.loadError'), 'error')
  }
})

// Example with a made-up person, so the choice is clear before saving
const example = computed(() => {
  const first = t('system.userName.exampleFirst')
  const last = t('system.userName.exampleLast')
  if (display.value === 'username') return t('system.userName.exampleUsername')
  if (display.value === 'first_name') return first
  return order.value === 'last_first' ? `${last}, ${first}` : `${first} ${last}`
})

async function save() {
  saving.value = true
  try {
    await store.save({ user_name_display: display.value, full_name_order: order.value })
    await auth.refresh() // the top bar shows the new format
    notifications.notify(t('system.saved'))
  } catch {
    notifications.notify(t('settings.saveError'), 'error')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <v-card data-testid="user-name-display">
    <v-card-item prepend-icon="mdi-card-account-details-outline">
      <v-card-title>{{ $t('system.userName.title') }}</v-card-title>
      <v-card-subtitle class="text-wrap">{{ $t('system.userName.hint') }}</v-card-subtitle>
    </v-card-item>
    <v-card-text>
      <v-radio-group
        v-model="display"
        :label="$t('system.userName.show')"
        hide-details
        data-testid="name-display"
      >
        <v-radio value="username" :label="$t('system.userName.options.username')" />
        <v-radio value="first_name" :label="$t('system.userName.options.firstName')" />
        <v-radio value="full_name" :label="$t('system.userName.options.fullName')" />
      </v-radio-group>
      <v-radio-group
        v-model="order"
        :label="$t('system.userName.order')"
        :disabled="display === 'username'"
        inline
        hide-details
        class="mt-2"
        data-testid="name-order"
      >
        <v-radio value="first_last" :label="$t('system.userName.orders.firstLast')" />
        <v-radio value="last_first" :label="$t('system.userName.orders.lastFirst')" />
      </v-radio-group>
      <p class="text-caption text-medium-emphasis mt-1 mb-0">
        {{ $t('system.userName.orderHint') }}
      </p>
      <div class="d-flex flex-wrap align-center ga-3 mt-4">
        <span class="text-body-2 text-medium-emphasis">{{ $t('system.userName.example') }}</span>
        <v-chip prepend-icon="mdi-account" data-testid="name-example">{{ example }}</v-chip>
        <v-spacer />
        <v-btn
          color="primary"
          :loading="saving"
          prepend-icon="mdi-content-save-outline"
          data-testid="name-save"
          @click="save"
        >
          {{ $t('common.save') }}
        </v-btn>
      </div>
    </v-card-text>
  </v-card>
</template>
