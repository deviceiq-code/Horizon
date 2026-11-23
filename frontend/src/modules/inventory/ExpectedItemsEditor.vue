<script setup lang="ts">
/**
 * A receiving's expected list as an editable grid: model, serial number (optional; then one
 * unit) and quantity. Rows are typed in, or pasted from a spreadsheet (columns Model, Serial,
 * Quantity) — the server finds each model and flags what it could not read.
 */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import AssetModelPicker from '@/modules/catalogs/asset-models/AssetModelPicker.vue'
import type { AssetModel } from '@/modules/catalogs/asset-models/api'
import { parseExpected } from './api'
import { isInvalid, newKey, type EditorRow } from './expectedRows'

const rows = defineModel<EditorRow[]>({ required: true })
defineProps<{ readonly?: boolean }>()

const { t } = useI18n()

const totals = computed(() => ({
  lines: rows.value.length,
  units: rows.value.reduce((sum, row) => sum + (row.quantity ?? 0), 0),
}))

function addRow() {
  rows.value = [
    ...rows.value,
    {
      key: newKey(),
      asset_model: null,
      asset_model_label: '',
      tracking: null,
      serial: '',
      quantity: 1,
      errors: [],
    },
  ]
}

function removeRow(key: number) {
  rows.value = rows.value.filter((row) => row.key !== key)
}

function onModel(row: EditorRow, model: AssetModel | null) {
  row.asset_model = model?.id ?? null
  row.asset_model_label = model ? `${model.manufacturer_name} ${model.name}` : ''
  row.tracking = model?.tracking ?? null
  row.errors = []
}

function onSerial(row: EditorRow, value: string) {
  row.serial = value.replace(/\s+/g, '').toUpperCase()
  if (row.serial) row.quantity = 1
}

// --- Paste from a spreadsheet ------------------------------------------------------------------

const pasteOpen = ref(false)
const pasted = ref('')
const parsing = ref(false)
const pasteError = ref('')

async function importPasted() {
  parsing.value = true
  pasteError.value = ''
  try {
    const { rows: parsedRows } = await parseExpected(pasted.value)
    rows.value = [
      ...rows.value.filter((row) => row.asset_model !== null || row.serial),
      ...parsedRows.map((row) => ({ ...row, key: newKey() })),
    ]
    pasteOpen.value = false
    pasted.value = ''
  } catch (error) {
    pasteError.value = error instanceof ApiError ? error.message : t('common.saveError')
  } finally {
    parsing.value = false
  }
}

/** Rows that cannot be saved (the form refuses while any is left). */
const invalid = computed(() => rows.value.filter(isInvalid))
defineExpose({ invalid })
</script>

<template>
  <div>
    <div class="d-flex flex-wrap align-center ga-2 mb-2">
      <span class="text-body-2 text-medium-emphasis" data-testid="expected-totals">
        {{ $t('inventory.expected.totals', { lines: totals.lines, units: totals.units }) }}
      </span>
      <v-spacer />
      <template v-if="!readonly">
        <v-btn
          variant="tonal"
          prepend-icon="mdi-content-paste"
          data-testid="paste"
          @click="pasteOpen = true"
        >
          {{ $t('inventory.expected.paste') }}
        </v-btn>
        <v-btn variant="tonal" prepend-icon="mdi-plus" data-testid="add-row" @click="addRow">
          {{ $t('inventory.expected.addRow') }}
        </v-btn>
      </template>
    </div>

    <v-table density="compact" class="expected-table" data-testid="expected-table">
      <thead>
        <tr>
          <th style="width: 48px">#</th>
          <th>{{ $t('inventory.fields.assetModel') }}</th>
          <th style="width: 220px">{{ $t('inventory.fields.serial') }}</th>
          <th style="width: 120px">{{ $t('inventory.expected.quantity') }}</th>
          <th v-if="!readonly" style="width: 56px" />
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="(row, index) in rows"
          :key="row.key"
          :class="{ 'row-error': row.errors.length || row.asset_model === null }"
          data-testid="expected-row"
        >
          <td class="text-medium-emphasis">{{ index + 1 }}</td>
          <td>
            <template v-if="readonly">{{ row.asset_model_label }}</template>
            <AssetModelPicker
              v-else
              :model-value="row.asset_model"
              :label="''"
              :initial-option="
                row.asset_model ? { id: row.asset_model, label: row.asset_model_label } : null
              "
              density="compact"
              hide-details
              @selected="onModel(row, $event)"
            />
            <div v-for="error in row.errors" :key="error" class="text-caption text-error">
              {{ error }}
            </div>
          </td>
          <td>
            <template v-if="readonly">{{ row.serial || '—' }}</template>
            <v-text-field
              v-else
              :model-value="row.serial"
              density="compact"
              hide-details
              maxlength="100"
              @update:model-value="onSerial(row, $event)"
            />
          </td>
          <td>
            <template v-if="readonly">{{ row.quantity }}</template>
            <v-text-field
              v-else
              :model-value="row.quantity ?? ''"
              :disabled="!!row.serial"
              inputmode="numeric"
              density="compact"
              hide-details
              @update:model-value="row.quantity = /^\d+$/.test($event) ? Number($event) : null"
            />
          </td>
          <td v-if="!readonly">
            <v-btn
              icon="mdi-close"
              size="small"
              variant="text"
              tabindex="-1"
              :aria-label="$t('common.delete')"
              @click="removeRow(row.key)"
            />
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="readonly ? 4 : 5" class="text-medium-emphasis text-center py-4">
            {{ $t('inventory.expected.empty') }}
          </td>
        </tr>
      </tbody>
    </v-table>

    <v-dialog v-model="pasteOpen" max-width="720">
      <v-card :title="$t('inventory.expected.pasteTitle')">
        <v-card-text>
          <p class="text-body-2 text-medium-emphasis mb-3">
            {{ $t('inventory.expected.pasteText') }}
          </p>
          <v-textarea
            v-model="pasted"
            rows="10"
            class="font-monospace"
            :error-messages="pasteError"
            autofocus
            data-testid="paste-text"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="pasteOpen = false">{{ $t('common.cancel') }}</v-btn>
          <v-btn
            color="primary"
            variant="flat"
            :loading="parsing"
            :disabled="!pasted.trim()"
            data-testid="paste-import"
            @click="importPasted"
          >
            {{ $t('inventory.expected.import') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<style scoped>
.row-error td {
  background: rgba(var(--v-theme-error), 0.06);
}
.expected-table :deep(td) {
  vertical-align: top;
  padding-top: 6px !important;
  padding-bottom: 6px !important;
}
</style>
