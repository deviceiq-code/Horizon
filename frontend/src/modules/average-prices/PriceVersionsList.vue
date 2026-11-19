<script setup lang="ts">
/**
 * Versions of an average price (newest first, identified by date and time) with their values per
 * term. Any version can be erased here for good (after confirmation); the API then makes the
 * newest version left the current one. Used in the detail's history and the grid's expanded rows.
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { deleteErrorMessage } from '@/api'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import { useNotificationsStore } from '@/stores/notifications'
import { formatMoney } from '@/utils/money'
import { deleteAveragePriceVersion, type AveragePrice } from './api'

defineProps<{
  /** Every version of the row, newest first (as GET /history/ returns them) */
  versions: AveragePrice[]
  /** Version being shown elsewhere (highlighted) */
  activeId?: number | null
}>()
const emit = defineEmits<{ open: [version: AveragePrice]; deleted: [version: AveragePrice] }>()

const { t, locale, n, d } = useI18n()
const notifications = useNotificationsStore()

const money = (version: AveragePrice, value: string) =>
  formatMoney(value, version.currency, locale.value)
const dateTime = (value: string) => d(new Date(value), 'dateTime')

// --- Delete one version ----------------------------------------------------------------------

const deleting = ref<AveragePrice | null>(null)
const confirmOpen = ref(false)
const inProgress = ref(false)

function askDelete(version: AveragePrice) {
  deleting.value = version
  confirmOpen.value = true
}

async function confirmDelete() {
  if (!deleting.value) return
  const version = deleting.value
  inProgress.value = true
  try {
    await deleteAveragePriceVersion(version.id)
    notifications.notify(t('averagePrices.versionDeleted'))
    emit('deleted', version)
  } catch (error) {
    notifications.notify(deleteErrorMessage(error, t('common.deleteError')), 'error')
  } finally {
    confirmOpen.value = false
    inProgress.value = false
  }
}
</script>

<template>
  <div>
    <p v-if="!versions.length" class="text-medium-emphasis pa-4">
      {{ $t('averagePrices.noPreviousVersions') }}
    </p>
    <v-list v-else density="compact" bg-color="transparent" data-testid="versions">
      <v-list-item
        v-for="version in versions"
        :key="version.id"
        :active="version.id === activeId"
        color="primary"
        data-testid="history-item"
        @click="version.id !== activeId && emit('open', version)"
      >
        <v-list-item-title>
          {{ dateTime(version.created_at) }}
          <span v-if="version.created_by_name" class="text-medium-emphasis">
            · {{ version.created_by_name }}
          </span>
        </v-list-item-title>
        <v-list-item-subtitle>
          {{ version.manufacturer.name }} {{ version.model }} ·
          {{ money(version, version.original_value) }}
        </v-list-item-subtitle>
        <div class="d-flex flex-wrap ga-1 mt-1">
          <v-chip
            v-for="point in version.points"
            :key="point.term_months"
            size="x-small"
            variant="tonal"
            :color="version.increasing_terms.includes(point.term_months) ? 'warning' : undefined"
            :title="money(version, point.value)"
          >
            {{ point.term_months }}m · {{ n(Number(point.percent), 'percentValue') }}%
          </v-chip>
        </div>
        <template #append>
          <v-chip
            v-if="version.is_current"
            color="success"
            size="x-small"
            variant="tonal"
            label
            class="mr-1"
          >
            {{ $t('averagePrices.status.current') }}
          </v-chip>
          <v-btn
            icon="mdi-delete-outline"
            variant="text"
            size="small"
            color="error"
            :aria-label="$t('averagePrices.deleteVersion')"
            :title="$t('averagePrices.deleteVersion')"
            data-testid="delete-version"
            @click.stop="askDelete(version)"
          />
        </template>
      </v-list-item>
    </v-list>

    <ConfirmDialog
      v-model="confirmOpen"
      :title="$t('averagePrices.deleteVersion')"
      :message="
        deleting
          ? $t('averagePrices.deleteVersionConfirm', { date: dateTime(deleting.created_at) })
          : ''
      "
      :confirm-text="$t('common.delete')"
      :loading="inProgress"
      @confirm="confirmDelete"
    />
  </div>
</template>
