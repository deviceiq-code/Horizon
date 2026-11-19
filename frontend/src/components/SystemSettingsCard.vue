<script setup lang="ts">
/** Photo search through SearXNG (Settings → System, administrators only). */
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import { useNotificationsStore } from '@/stores/notifications'
import { useSystemSettingsStore } from '@/stores/systemSettings'

const { t } = useI18n()
const store = useSystemSettingsStore()
const notifications = useNotificationsStore()

const searxngUrl = ref('')
const errors = ref<string[]>([])
const saving = ref(false)
const testing = ref(false)
const testResult = ref<{ ok: boolean; text: string } | null>(null)

onMounted(async () => {
  try {
    searxngUrl.value = (await store.load()).searxng_url ?? ''
  } catch {
    notifications.notify(t('common.loadError'), 'error')
  }
})

function messageOf(error: unknown, field: string, fallback: string) {
  if (error instanceof ApiError) {
    const messages = error.fieldErrors()[field]
    if (messages?.length) return messages.join(' ')
    if (error.message) return error.message
  }
  return fallback
}

async function save() {
  saving.value = true
  errors.value = []
  try {
    await store.save({ searxng_url: searxngUrl.value.trim() })
    searxngUrl.value = store.settings?.searxng_url ?? ''
    notifications.notify(t('system.saved'))
  } catch (error) {
    errors.value = [messageOf(error, 'searxng_url', t('settings.saveError'))]
  } finally {
    saving.value = false
  }
}

async function test() {
  testing.value = true
  testResult.value = null
  try {
    const { results } = await store.testSearxng(searxngUrl.value.trim())
    testResult.value = { ok: true, text: t('system.searxng.testOk', results) }
  } catch (error) {
    testResult.value = {
      ok: false,
      text: messageOf(error, 'searxng_url', t('system.searxng.testError')),
    }
  } finally {
    testing.value = false
  }
}
</script>

<template>
  <v-card data-testid="system-settings">
    <v-card-item prepend-icon="mdi-image-search-outline">
      <v-card-title>{{ $t('system.searxng.title') }}</v-card-title>
      <v-card-subtitle class="text-wrap">{{ $t('system.searxng.hint') }}</v-card-subtitle>
    </v-card-item>
    <v-card-text>
      <div class="d-flex flex-wrap ga-2 align-start">
        <v-text-field
          v-model="searxngUrl"
          :label="$t('system.searxng.url')"
          placeholder="http://192.168.0.22:30053"
          :error-messages="errors"
          :hint="$t('system.searxng.urlHint')"
          persistent-hint
          clearable
          style="min-width: 280px; max-width: 460px"
          data-testid="searxng-url"
          @update:model-value="errors = []"
        />
        <v-btn
          variant="tonal"
          :loading="testing"
          :disabled="!searxngUrl?.trim()"
          prepend-icon="mdi-connection"
          class="mt-2"
          data-testid="searxng-test"
          @click="test"
        >
          {{ $t('system.searxng.test') }}
        </v-btn>
        <v-btn
          color="primary"
          :loading="saving"
          prepend-icon="mdi-content-save-outline"
          class="mt-2"
          data-testid="system-save"
          @click="save"
        >
          {{ $t('common.save') }}
        </v-btn>
      </div>
      <v-alert
        v-if="testResult"
        :type="testResult.ok ? 'success' : 'error'"
        variant="tonal"
        density="compact"
        class="mt-3"
        data-testid="searxng-test-result"
      >
        {{ testResult.text }}
      </v-alert>
    </v-card-text>
  </v-card>
</template>
