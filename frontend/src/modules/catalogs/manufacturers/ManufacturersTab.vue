<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import ServerCrudTable from '@/components/ServerCrudTable.vue'
import { useNotificationsStore } from '@/stores/notifications'
import EnabledChip from '../EnabledChip.vue'
import RemarketingAverage from '../remarketing/RemarketingAverage.vue'
import ManufacturerFormDialog from './ManufacturerFormDialog.vue'
import {
  deleteManufacturer,
  listManufacturers,
  MANUFACTURER_RATINGS,
  type Manufacturer,
} from './api'

const { t } = useI18n()
const notifications = useNotificationsStore()

const table = ref<{ reload: () => Promise<void> } | null>(null)

const headers = computed(() => [
  { title: t('catalogs.fields.id'), key: 'id', width: 90 },
  { title: t('manufacturers.fields.name'), key: 'name' },
  // Average of the three ratings; hover for each one
  { title: t('manufacturers.remarketing.title'), key: 'remarketing_average', width: 230 },
  { title: t('catalogs.fields.status'), key: 'is_enabled', width: 140 },
])

const formOpen = ref(false)
const editing = ref<Manufacturer | null>(null)

function openForm(manufacturer: Manufacturer | null) {
  editing.value = manufacturer
  formOpen.value = true
}

function onSaved(_manufacturer: Manufacturer, created: boolean) {
  notifications.notify(t(created ? 'manufacturers.created' : 'manufacturers.updated'))
  table.value?.reload()
}
</script>

<template>
  <ServerCrudTable
    ref="table"
    :fetch-page="listManufacturers"
    :delete-item="deleteManufacturer"
    :headers="headers"
    :sort-by="[{ key: 'name', order: 'asc' }]"
    :ordering-fields="{ remarketing_average: 'remarketing_score' }"
    :search-placeholder="$t('manufacturers.searchPlaceholder')"
    :empty-text="$t('manufacturers.empty')"
    :no-results-text="$t('manufacturers.noResults')"
    :delete-title="$t('manufacturers.deleteTitle')"
    :delete-message="(m: Manufacturer) => $t('manufacturers.deleteConfirm', { name: m.name })"
    :deleted-text="$t('manufacturers.deleted')"
    @create="openForm(null)"
    @edit="openForm"
  >
    <template #[`item.remarketing_average`]="{ item }">
      <RemarketingAverage
        :average="item.remarketing_average"
        :breakdown="
          MANUFACTURER_RATINGS.map((field) => ({
            label: $t(`manufacturers.remarketing.${field}.label`),
            value: item[field],
          }))
        "
      />
    </template>
    <template #[`item.is_enabled`]="{ item }">
      <EnabledChip :enabled="item.is_enabled" />
    </template>
  </ServerCrudTable>

  <ManufacturerFormDialog v-model="formOpen" :manufacturer="editing" @saved="onSaved" />
</template>
