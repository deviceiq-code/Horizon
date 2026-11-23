<script setup lang="ts">
/**
 * Average prices: market value estimates of assets at each term. Rows are never edited:
 * "New version" creates a new row and keeps the previous one in the history. Rows with previous
 * versions expand to list them; a version can be deleted there or in the detail (the newest
 * one left becomes current). Deleting from the grid hides every version (all kept).
 */
import { useDateFormat } from '@/composables/useDateFormat'
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useNumberFormat } from '@/composables/useNumberFormat'
import MoneyField from '@/components/MoneyField.vue'
import ServerCrudTable from '@/components/ServerCrudTable.vue'
import { useNotificationsStore } from '@/stores/notifications'
import { formatMoney } from '@/utils/money'
import AveragePriceDetailDialog from './AveragePriceDetailDialog.vue'
import AssetClassPicker from '@/modules/catalogs/asset-classes/AssetClassPicker.vue'
import AveragePriceFormDialog from './AveragePriceFormDialog.vue'
import type { SaveOutcome } from './media'
import { usePriceFilters } from './AveragePriceFilters'
import PriceVersionsPanel from './PriceVersionsPanel.vue'
import {
  deleteAveragePrice,
  listAveragePrices,
  type AveragePrice,
  type AveragePriceDetail,
} from './api'

const { t, locale } = useI18n()
const { n } = useNumberFormat()
// Dates in the formats the user chose (Settings)
const { d } = useDateFormat()
const notifications = useNotificationsStore()

const table = ref<{ reload: () => Promise<void> } | null>(null)

const headers = computed(() => [
  // Minimum widths leave room for the column filters
  { title: t('averagePrices.fields.assetClass'), key: 'asset_class', minWidth: '240px' },
  { title: t('averagePrices.fields.model'), key: 'model', minWidth: '200px' },
  {
    title: t('averagePrices.fields.originalValue'),
    key: 'original_value',
    align: 'end' as const,
    minWidth: '220px',
  },
  { title: t('averagePrices.fields.terms'), key: 'points', sortable: false },
  { title: t('averagePrices.fields.createdAt'), key: 'created_at', minWidth: '190px' },
])

// --- Create / new version / detail -----------------------------------------------------------

const formOpen = ref(false)
const source = ref<AveragePrice | null>(null)
const detailOpen = ref(false)
const detailId = ref<number | null>(null)

function openNew() {
  source.value = null
  formOpen.value = true
}

function openNewVersion(row: AveragePrice) {
  detailOpen.value = false
  source.value = row
  formOpen.value = true
}

function openDetail(row: AveragePrice) {
  detailId.value = row.id
  detailOpen.value = true
}

function onSaved(row: AveragePriceDetail | null, outcome: SaveOutcome) {
  notifications.notify(
    t(
      {
        created: 'averagePrices.created',
        version: 'averagePrices.versionCreated',
        media: 'averagePrices.media.saved',
      }[outcome],
    ),
  )
  if (row?.increasing_terms.length) {
    notifications.notify(
      t('averagePrices.increasingWarning', { terms: row.increasing_terms.join(', ') }),
      'warning',
    )
  }
  table.value?.reload()
}

// --- Column filters --------------------------------------------------------------------------

const {
  filters,
  typed,
  invalid,
  pickerKey,
  clear: clearFilters,
} = usePriceFilters(() => locale.value)

const money = (row: AveragePrice) => formatMoney(row.original_value, row.currency, locale.value)
</script>

<template>
  <v-container fluid class="module-page">
    <h1 class="text-h5 mb-1">{{ $t('averagePrices.title') }}</h1>
    <p class="text-medium-emphasis mb-4">{{ $t('averagePrices.subtitle') }}</p>

    <ServerCrudTable
      ref="table"
      :fetch-page="listAveragePrices"
      :delete-item="deleteAveragePrice"
      :headers="headers"
      :sort-by="[{ key: 'created_at', order: 'desc' }]"
      :ordering-fields="{ asset_class: 'asset_class__name' }"
      :search-placeholder="$t('averagePrices.searchPlaceholder')"
      :empty-text="$t('averagePrices.empty')"
      :no-results-text="$t('averagePrices.noResults')"
      :delete-title="$t('averagePrices.deleteTitle')"
      :delete-message="
        (row: AveragePrice) =>
          $t('averagePrices.deleteConfirm', { name: `${row.manufacturer.name} ${row.model}` })
      "
      :deleted-text="$t('averagePrices.deleted')"
      edit-icon="mdi-file-replace-outline"
      :edit-title="$t('averagePrices.newVersion')"
      :expandable="(row: AveragePrice) => row.supersedes !== null"
      :filters="filters"
      filters-storage-key="average-prices"
      @clear-filters="clearFilters"
      @create="openNew"
      @edit="openNewVersion"
    >
      <template #[`item.asset_class`]="{ item }">
        <div class="d-flex align-center ga-3 py-2">
          <v-avatar color="primary" variant="tonal" size="36" rounded>
            <v-icon :icon="item.asset_class.icon" size="20" />
          </v-avatar>
          <div>
            <div>{{ item.asset_class.name }}</div>
            <div class="text-caption text-medium-emphasis">{{ item.sub_vertical.label }}</div>
          </div>
        </div>
      </template>
      <template #[`item.model`]="{ item }">
        <div class="font-weight-medium">{{ item.model }}</div>
        <div class="text-caption text-medium-emphasis">
          {{ item.manufacturer.name }}
          <span
            v-if="item.documents_count"
            class="ml-1 text-no-wrap"
            :title="$t('averagePrices.documents.title', item.documents_count)"
            data-testid="documents-count"
          >
            <v-icon icon="mdi-paperclip" size="x-small" />{{ item.documents_count }}
          </span>
        </div>
      </template>
      <template #[`item.original_value`]="{ item }">
        <span class="text-no-wrap">{{ money(item) }}</span>
      </template>
      <template #[`item.points`]="{ item }">
        <div class="d-flex flex-wrap ga-1 py-1" data-testid="points">
          <v-chip
            v-for="point in item.points"
            :key="point.term_months"
            size="small"
            variant="tonal"
            :color="item.increasing_terms.includes(point.term_months) ? 'warning' : undefined"
            :title="formatMoney(point.value, item.currency, locale)"
          >
            {{ point.term_months }}m · {{ n(Number(point.percent), 'percentValue') }}%
          </v-chip>
        </div>
      </template>
      <template #[`item.created_at`]="{ item }">
        <div class="text-no-wrap">{{ d(new Date(item.created_at), 'short') }}</div>
        <div class="text-caption text-medium-emphasis">
          <v-icon v-if="item.supersedes" icon="mdi-history" size="x-small" />
          {{ item.created_by_name }}
        </div>
      </template>
      <template #[`filter.asset_class`]>
        <AssetClassPicker
          :key="pickerKey"
          v-model="filters.asset_class"
          :label="$t('averagePrices.filters.assetClass')"
          density="compact"
          hide-details
          data-testid="filter-asset-class"
        />
      </template>
      <template #[`filter.model`]>
        <v-text-field
          v-model="typed.model"
          :placeholder="$t('averagePrices.filters.model')"
          prepend-inner-icon="mdi-filter-outline"
          density="compact"
          hide-details
          clearable
          data-testid="filter-model"
        />
      </template>
      <template #[`filter.original_value`]>
        <div class="d-flex ga-1">
          <MoneyField
            v-model="typed.min"
            :placeholder="$t('averagePrices.filters.from')"
            density="compact"
            hide-details
            :error="invalid.min"
            data-testid="filter-value-min"
          />
          <MoneyField
            v-model="typed.max"
            :placeholder="$t('averagePrices.filters.to')"
            density="compact"
            hide-details
            :error="invalid.max"
            data-testid="filter-value-max"
          />
        </div>
      </template>
      <template #[`filter.created_at`]>
        <div class="d-flex flex-column ga-1">
          <v-text-field
            v-model="filters.created_from"
            type="date"
            :label="$t('averagePrices.filters.from')"
            density="compact"
            hide-details
            data-testid="filter-created-from"
          />
          <v-text-field
            v-model="filters.created_to"
            type="date"
            :label="$t('averagePrices.filters.to')"
            density="compact"
            hide-details
            data-testid="filter-created-to"
          />
        </div>
      </template>
      <template #expanded-row="{ item }">
        <PriceVersionsPanel :row="item" @open="openDetail" @deleted="table?.reload()" />
      </template>
      <template #row-actions="{ item }">
        <v-btn
          icon="mdi-eye-outline"
          variant="text"
          size="small"
          :aria-label="$t('averagePrices.view')"
          :title="$t('averagePrices.view')"
          data-testid="view"
          @click="openDetail(item)"
        />
      </template>
    </ServerCrudTable>

    <AveragePriceFormDialog v-model="formOpen" :source="source" @saved="onSaved" />
    <AveragePriceDetailDialog
      v-model="detailOpen"
      :row-id="detailId"
      @new-version="openNewVersion"
      @changed="table?.reload()"
    />
  </v-container>
</template>
