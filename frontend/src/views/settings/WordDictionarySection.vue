<script setup lang="ts">
/**
 * The word dictionary (Settings › App Settings › Administration, administrators): each word's
 * spelling and the other ways it may be typed. Shared by everyone; applied by the Word
 * Dictionary Smart Tool when a form's field is left (whole words, any case). As the rest of
 * Settings, every change is saved on its own: the spelling when left, the ways to type it when
 * they change. A field below tries it out.
 */
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import ListItemsField from '@/components/ListItemsField.vue'
import SettingRow from '@/components/SettingRow.vue'
import { useDictionaryStore } from '@/stores/dictionary'
import { useNotificationsStore } from '@/stores/notifications'
import {
  applyDictionary,
  deleteDictionaryWord,
  listDictionaryWords,
  saveDictionaryWord,
} from '@/wordDictionary'

interface Row {
  key: number
  id?: number
  replacement: string
  variants: string[]
  errors: string[]
}

const { t } = useI18n()
const notifications = useNotificationsStore()
const dictionary = useDictionaryStore()

const rows = ref<Row[]>([])
const loading = ref(true)
const loadFailed = ref(false)
const trial = ref('')
let next = 0

async function load() {
  loading.value = true
  loadFailed.value = false
  try {
    rows.value = (await listDictionaryWords()).map((w) => ({
      key: ++next,
      id: w.id,
      replacement: w.replacement,
      variants: [...w.variants],
      errors: [],
    }))
  } catch {
    loadFailed.value = true
  } finally {
    loading.value = false
  }
}
onMounted(load)

/** Saved: the shared copy every form uses follows */
async function save(row: Row) {
  if (!row.replacement.trim()) return
  row.errors = []
  try {
    const saved = await saveDictionaryWord({
      id: row.id,
      replacement: row.replacement,
      variants: row.variants,
    })
    Object.assign(row, { id: saved.id, replacement: saved.replacement, variants: saved.variants })
    notifications.notify(t('settings.saved'))
    await dictionary.load()
  } catch (error) {
    const fields = error instanceof ApiError && error.status === 400 ? error.fieldErrors() : {}
    row.errors = Object.values(fields).flat()
    if (!row.errors.length) row.errors = [t('settings.saveError')]
  }
}

function add() {
  rows.value.push({ key: ++next, replacement: '', variants: [], errors: [] })
}

async function remove(row: Row) {
  try {
    if (row.id) await deleteDictionaryWord(row.id)
    rows.value = rows.value.filter((r) => r.key !== row.key)
    await dictionary.load()
  } catch {
    notifications.notify(t('settings.saveError'), 'error')
  }
}

const tried = computed(() =>
  applyDictionary(
    trial.value,
    rows.value.filter((r) => r.replacement.trim()),
  ),
)
</script>

<template>
  <v-progress-linear v-if="loading" indeterminate class="mb-6" />
  <v-alert v-else-if="loadFailed" type="error" variant="tonal" class="mb-6">
    {{ $t('common.loadError') }}
  </v-alert>
  <template v-else>
    <div class="group-title">{{ $t('dictionary.title') }}</div>
    <v-card class="mb-6" data-testid="word-dictionary-section" data-no-dictionary>
      <SettingRow :title="$t('dictionary.title')" :description="$t('dictionary.hint')">
        <template #below>
          <div v-for="row in rows" :key="row.key" class="word-row" data-testid="dictionary-word">
            <v-text-field
              v-model="row.replacement"
              :label="$t('dictionary.replacement')"
              density="compact"
              maxlength="60"
              hide-details="auto"
              :error-messages="row.errors"
              data-testid="dictionary-replacement"
              @blur="save(row)"
              @keydown.enter.prevent="save(row)"
            />
            <ListItemsField
              v-model="row.variants"
              :label="$t('dictionary.variants')"
              :max-length="60"
              :fixed="row.replacement.trim() ? [row.replacement.trim().toLowerCase()] : []"
              :fixed-title="$t('dictionary.anyCase')"
              data-testid="dictionary-variants"
              @update:model-value="save(row)"
            />
            <v-btn
              icon="mdi-delete-outline"
              variant="text"
              size="small"
              color="error"
              :aria-label="$t('dictionary.remove')"
              :title="$t('dictionary.remove')"
              data-testid="dictionary-remove"
              @click="remove(row)"
            />
          </div>
          <v-btn
            variant="tonal"
            prepend-icon="mdi-plus"
            class="mt-2"
            data-testid="dictionary-add"
            @click="add"
            >{{ $t('dictionary.add') }}</v-btn
          >
        </template>
      </SettingRow>
      <!-- Try it -->
      <SettingRow :title="$t('dictionary.tryIt')" :description="$t('dictionary.tryHint')">
        <template #below>
          <v-text-field
            v-model="trial"
            :placeholder="$t('dictionary.tryPlaceholder')"
            density="compact"
            hide-details
            data-testid="dictionary-try"
          />
          <div v-if="trial" class="text-body-2 mt-2" data-testid="dictionary-tried">
            <span class="text-medium-emphasis">{{ $t('dictionary.becomes') }}</span>
            <strong class="ml-1">{{ tried }}</strong>
          </div>
        </template>
      </SettingRow>
    </v-card>
  </template>
</template>

<style scoped>
.word-row {
  display: grid;
  grid-template-columns: minmax(140px, 220px) 1fr auto;
  gap: 12px;
  align-items: start;
  margin-bottom: 12px;
}
@media (max-width: 599.98px) {
  .word-row {
    grid-template-columns: 1fr;
  }
}
</style>
