<script setup lang="ts">
/**
 * One average price: what is priced, its values per term, the monthly curve (computed by the
 * API) and every version of the row. Any version can be opened from the history.
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { formatMoney } from '@/utils/money'
import {
  getAveragePrice,
  getAveragePriceHistory,
  type AveragePrice,
  type AveragePriceDetail,
} from './api'

const props = defineProps<{ rowId: number | null }>()
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ newVersion: [row: AveragePrice] }>()

const { t, locale, n, d } = useI18n()

const shownId = ref<number | null>(null)
const row = ref<AveragePriceDetail | null>(null)
const history = ref<AveragePrice[]>([])
const loading = ref(false)
const loadError = ref(false)
const tab = ref<'terms' | 'curve' | 'history'>('terms')

async function load(id: number) {
  shownId.value = id
  loading.value = true
  loadError.value = false
  try {
    const [detail, versions] = await Promise.all([getAveragePrice(id), getAveragePriceHistory(id)])
    row.value = detail
    history.value = versions
  } catch {
    loadError.value = true
  } finally {
    loading.value = false
  }
}

watch(open, (isOpen) => {
  if (!isOpen || props.rowId === null) return
  row.value = null
  history.value = []
  tab.value = 'terms'
  load(props.rowId)
})

const money = (value: string) => formatMoney(value, row.value?.currency ?? 'BRL', locale.value)
const percent = (value: string) => `${n(Number(value), 'percentValue')}%`
const dateTime = (value: string) => d(new Date(value), 'dateTime')

const status = computed(() => {
  if (!row.value) return null
  if (row.value.deleted_at) return { color: 'error', text: t('averagePrices.status.deleted') }
  if (!row.value.is_current) return { color: undefined, text: t('averagePrices.status.previous') }
  return { color: 'success', text: t('averagePrices.status.current') }
})

const versionNumber = (version: AveragePrice) =>
  history.value.length - history.value.findIndex((v) => v.id === version.id)
</script>

<template>
  <v-dialog v-model="open" max-width="980" scrollable>
    <v-card>
      <v-card-item>
        <template v-if="row" #prepend>
          <v-avatar color="primary" variant="tonal" size="48" rounded>
            <v-icon :icon="row.asset_class.icon" />
          </v-avatar>
        </template>
        <v-card-title>
          <span v-if="row">{{ row.manufacturer.name }} {{ row.model }}</span>
          <span v-else>{{ $t('averagePrices.title') }}</span>
        </v-card-title>
        <v-card-subtitle v-if="row">
          {{ row.asset_class.name }} · {{ row.sub_vertical.label }}
        </v-card-subtitle>
        <template #append>
          <v-chip v-if="status" :color="status.color" size="small" variant="tonal" label>
            {{ status.text }}
          </v-chip>
        </template>
      </v-card-item>

      <v-card-text style="min-height: 240px">
        <v-progress-linear v-if="loading" indeterminate class="mb-4" />
        <v-alert v-if="loadError" type="error" variant="tonal">{{
          $t('common.loadError')
        }}</v-alert>

        <template v-if="row">
          <!-- Summary -->
          <v-row dense class="mb-2">
            <v-col cols="12" sm="4">
              <div class="text-caption text-medium-emphasis">
                {{ $t('averagePrices.fields.originalValue') }}
              </div>
              <div class="text-h6" data-testid="detail-original">
                {{ money(row.original_value) }}
              </div>
            </v-col>
            <v-col cols="12" sm="4">
              <div class="text-caption text-medium-emphasis">
                {{ $t('averagePrices.fields.createdAt') }}
              </div>
              <div>{{ dateTime(row.created_at) }}</div>
              <div v-if="row.created_by_name" class="text-caption text-medium-emphasis">
                {{ row.created_by_name }}
              </div>
            </v-col>
            <v-col cols="12" sm="4">
              <div class="text-caption text-medium-emphasis">
                {{ $t('averagePrices.fields.manufacturer') }}
              </div>
              <div>{{ row.manufacturer.name }}</div>
            </v-col>
          </v-row>
          <div class="text-caption text-medium-emphasis">
            {{ $t('averagePrices.fields.description') }}
          </div>
          <p class="mb-3" style="white-space: pre-line">{{ row.description }}</p>
          <div
            v-if="row.specs.length"
            class="d-flex flex-wrap ga-2 mb-4"
            data-testid="detail-specs"
          >
            <v-chip v-for="spec in row.specs" :key="spec.key" size="small" variant="outlined">
              <span class="text-medium-emphasis mr-1">{{ spec.label }}:</span>
              <span class="font-weight-medium">{{ spec.value || '—' }}</span>
              <span v-if="spec.value && spec.unit" class="ml-1">{{ spec.unit }}</span>
            </v-chip>
          </div>

          <v-alert
            v-if="row.increasing_terms.length"
            type="warning"
            variant="tonal"
            density="compact"
            class="mb-3"
          >
            {{ $t('averagePrices.increasingWarning', { terms: row.increasing_terms.join(', ') }) }}
          </v-alert>

          <v-tabs v-model="tab" color="primary" density="compact" class="mb-2">
            <v-tab value="terms">{{ $t('averagePrices.tabs.terms') }}</v-tab>
            <v-tab value="curve" data-testid="tab-curve">{{
              $t('averagePrices.tabs.curve')
            }}</v-tab>
            <v-tab value="history" data-testid="tab-history">
              {{ $t('averagePrices.tabs.history', history.length) }}
            </v-tab>
          </v-tabs>

          <v-window v-model="tab">
            <v-window-item value="terms">
              <v-table density="compact" data-testid="detail-terms">
                <thead>
                  <tr>
                    <th>{{ $t('averagePrices.fields.term') }}</th>
                    <th>{{ $t('averagePrices.fields.enteredAs') }}</th>
                    <th class="text-end">{{ $t('averagePrices.fields.value') }}</th>
                    <th class="text-end">%</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="point in row.points" :key="point.term_months">
                    <td>{{ $t('verticals.months', point.term_months) }}</td>
                    <td class="text-medium-emphasis">
                      {{ $t(`averagePrices.modes.${point.mode}`) }}
                    </td>
                    <td class="text-end font-weight-medium">{{ money(point.value) }}</td>
                    <td class="text-end">{{ percent(point.percent) }}</td>
                  </tr>
                </tbody>
              </v-table>
            </v-window-item>

            <v-window-item value="curve">
              <p class="text-body-2 text-medium-emphasis mb-2">
                {{ $t('averagePrices.curveHint') }}
              </p>
              <v-table density="compact" fixed-header height="360" data-testid="detail-curve">
                <thead>
                  <tr>
                    <th>{{ $t('averagePrices.fields.month') }}</th>
                    <th class="text-end">{{ $t('averagePrices.fields.value') }}</th>
                    <th class="text-end">%</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="point in row.curve"
                    :key="point.month"
                    :class="{ 'font-weight-bold bg-surface-light': point.is_anchor }"
                    data-testid="curve-row"
                  >
                    <td>{{ point.month }}</td>
                    <td class="text-end">{{ money(point.value) }}</td>
                    <td class="text-end">{{ percent(point.percent) }}</td>
                  </tr>
                </tbody>
              </v-table>
            </v-window-item>

            <v-window-item value="history">
              <v-list density="compact" data-testid="detail-history">
                <v-list-item
                  v-for="version in history"
                  :key="version.id"
                  :active="version.id === shownId"
                  color="primary"
                  data-testid="history-item"
                  @click="version.id !== shownId && load(version.id)"
                >
                  <v-list-item-title>
                    {{ $t('averagePrices.version', { n: versionNumber(version) }) }} ·
                    {{ dateTime(version.created_at) }}
                    <span v-if="version.created_by_name" class="text-medium-emphasis">
                      · {{ version.created_by_name }}
                    </span>
                  </v-list-item-title>
                  <v-list-item-subtitle>
                    {{ version.manufacturer.name }} {{ version.model }} ·
                    {{ money(version.original_value) }}
                  </v-list-item-subtitle>
                  <template #append>
                    <v-chip
                      v-if="version.deleted_at"
                      color="error"
                      size="x-small"
                      variant="tonal"
                      label
                    >
                      {{ $t('averagePrices.status.deleted') }}
                    </v-chip>
                    <v-chip
                      v-else-if="version.is_current"
                      color="success"
                      size="x-small"
                      variant="tonal"
                      label
                    >
                      {{ $t('averagePrices.status.current') }}
                    </v-chip>
                  </template>
                </v-list-item>
              </v-list>
            </v-window-item>
          </v-window>
        </template>
      </v-card-text>

      <v-card-actions>
        <v-btn
          v-if="row && row.is_current && !row.deleted_at"
          variant="tonal"
          color="primary"
          prepend-icon="mdi-file-replace-outline"
          data-testid="detail-new-version"
          @click="emit('newVersion', row)"
        >
          {{ $t('averagePrices.newVersion') }}
        </v-btn>
        <v-spacer />
        <v-btn variant="text" @click="open = false">{{ $t('common.close') }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
