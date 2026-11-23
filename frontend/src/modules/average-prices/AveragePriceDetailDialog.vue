<script setup lang="ts">
/**
 * One average price: what is priced, its values per term, the monthly curve (computed by the
 * API) and every version of the row with their average (also computed by the API). Any version
 * can be opened or erased from the history.
 */
import FormDialog from '@/components/FormDialog.vue'
import { useDateFormat } from '@/composables/useDateFormat'
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useNumberFormat } from '@/composables/useNumberFormat'
import { formatMoney } from '@/utils/money'
import {
  getAveragePrice,
  getAveragePriceHistory,
  type AveragePrice,
  type AveragePriceDetail,
  type VersionsAverage,
} from './api'
import PriceDocuments from './PriceDocuments.vue'
import { specText } from './specText'
import PricePhoto from './PricePhoto.vue'
import PriceVersionsList from './PriceVersionsList.vue'
import VersionsAverageCard from './VersionsAverageCard.vue'

const props = defineProps<{ rowId: number | null }>()
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ newVersion: [row: AveragePrice]; changed: [] }>()

const { t, locale } = useI18n()
const { n } = useNumberFormat()
// Dates in the formats the user chose (Settings)
const { d } = useDateFormat()

const shownId = ref<number | null>(null)
const row = ref<AveragePriceDetail | null>(null)
const history = ref<AveragePrice[]>([])
const average = ref<VersionsAverage | null>(null)
const loading = ref(false)
const loadError = ref(false)
const tab = ref<'terms' | 'curve' | 'history' | 'documents'>('terms')

async function load(id: number) {
  shownId.value = id
  loading.value = true
  loadError.value = false
  try {
    const [detail, versions] = await Promise.all([getAveragePrice(id), getAveragePriceHistory(id)])
    row.value = detail
    history.value = versions.versions
    average.value = versions.average
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
  average.value = null
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

// Documents belong to the row (every version); the grid shows how many
const documentsCount = computed(() => row.value?.documents_count ?? 0)

function onPhotoChanged(photoId: number | null) {
  // Reload the row: the photo's source may have changed too
  if (row.value) row.value.photo_id = photoId
  if (shownId.value !== null) load(shownId.value)
  emit('changed')
}

function onDocumentsChanged(count: number) {
  if (row.value) row.value.documents_count = count
  emit('changed')
}

// Erasing a version may change which one is current: refresh this view and the grid. If the
// version shown was erased, show the newest one left (or close when none is left).
async function onVersionDeleted(erased: AveragePrice) {
  emit('changed')
  const left = history.value.filter((version) => version.id !== erased.id)
  const next = erased.id === shownId.value ? left[0]?.id : shownId.value
  if (next === undefined || next === null) {
    open.value = false
    return
  }
  await load(next)
}
</script>

<template>
  <FormDialog
    v-model="open"
    :title="row ? `${row.manufacturer.name} ${row.model}` : $t('averagePrices.title')"
    max-width="980"
  >
    <!-- What the price is: its photo, name, class and status -->
    <template #heading>
      <v-card-item class="pa-0">
        <template v-if="row" #prepend>
          <PricePhoto
            :key="row.id"
            :row-id="row.id"
            :photo-id="row.photo_id"
            :icon="row.asset_class.icon"
            :title="`${row.manufacturer.name} ${row.model}`"
            :can-edit="!row.deleted_at"
            :source-url="row.photo_source_url"
            class="mr-2"
            @changed="onPhotoChanged"
          />
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
    </template>

    <v-progress-linear v-if="loading" indeterminate class="mb-4" />
    <v-alert v-if="loadError" type="error" variant="tonal">{{ $t('common.loadError') }}</v-alert>

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
      <template v-if="row.description">
        <div class="text-caption text-medium-emphasis">
          {{ $t('averagePrices.fields.description') }}
        </div>
        <p class="mb-3" style="white-space: pre-line">{{ row.description }}</p>
      </template>
      <div v-if="row.specs.length" class="d-flex flex-wrap ga-2 mb-4" data-testid="detail-specs">
        <v-chip v-for="spec in row.specs" :key="spec.key" size="small" variant="outlined">
          <span class="text-medium-emphasis mr-1">{{ spec.label }}:</span>
          <span class="font-weight-medium">{{ specText(spec, t, n) }}</span>
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
        <v-tab value="curve" data-testid="tab-curve">{{ $t('averagePrices.tabs.curve') }}</v-tab>
        <v-tab value="history" data-testid="tab-history">
          {{ $t('averagePrices.tabs.history', history.length) }}
        </v-tab>
        <v-tab value="documents" data-testid="tab-documents">
          {{ $t('averagePrices.documents.title', documentsCount) }}
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
          <VersionsAverageCard
            v-if="average && average.count > 1"
            :average="average"
            :currency="row.currency"
            class="mb-3"
          />
          <PriceVersionsList
            :versions="history"
            :active-id="shownId"
            data-testid="detail-history"
            @open="load($event.id)"
            @deleted="onVersionDeleted"
          />
        </v-window-item>
        <v-window-item value="documents">
          <PriceDocuments
            :key="row.id"
            :row-id="row.id"
            :can-edit="!row.deleted_at"
            @changed="onDocumentsChanged"
          />
        </v-window-item>
      </v-window>
    </template>

    <template #actions>
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
    </template>
  </FormDialog>
</template>
