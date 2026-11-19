<script setup lang="ts">
/**
 * Average prices: market value estimates of assets at each term. Rows are never edited:
 * "New version" creates a new row and keeps the previous one in the history. Rows with previous
 * versions expand to list them; a version can be deleted there or in the detail (the newest
 * one left becomes current). Deleting from the grid hides every version (all kept).
 */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import ServerCrudTable from '@/components/ServerCrudTable.vue'
import { useNotificationsStore } from '@/stores/notifications'
import { formatMoney } from '@/utils/money'
import AveragePriceDetailDialog from './AveragePriceDetailDialog.vue'
import AveragePriceFormDialog from './AveragePriceFormDialog.vue'
import PriceVersionsPanel from './PriceVersionsPanel.vue'
import {
  deleteAveragePrice,
  listAveragePrices,
  type AveragePrice,
  type AveragePriceDetail,
} from './api'

const { t, locale, n, d } = useI18n()
const notifications = useNotificationsStore()

const table = ref<{ reload: () => Promise<void> } | null>(null)

const headers = computed(() => [
  { title: t('averagePrices.fields.assetClass'), key: 'asset_class' },
  { title: t('averagePrices.fields.model'), key: 'model' },
  { title: t('averagePrices.fields.originalValue'), key: 'original_value', align: 'end' as const },
  { title: t('averagePrices.fields.terms'), key: 'points', sortable: false },
  { title: t('averagePrices.fields.createdAt'), key: 'created_at', width: 150 },
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

function onSaved(row: AveragePriceDetail, newVersion: boolean) {
  notifications.notify(t(newVersion ? 'averagePrices.versionCreated' : 'averagePrices.created'))
  if (row.increasing_terms.length) {
    notifications.notify(
      t('averagePrices.increasingWarning', { terms: row.increasing_terms.join(', ') }),
      'warning',
    )
  }
  table.value?.reload()
}

const money = (row: AveragePrice) => formatMoney(row.original_value, row.currency, locale.value)
</script>

<template>
  <v-container fluid style="max-width: 1400px">
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
