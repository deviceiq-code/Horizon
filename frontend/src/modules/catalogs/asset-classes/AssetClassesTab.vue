<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import ServerCrudTable from '@/components/ServerCrudTable.vue'
import { useNotificationsStore } from '@/stores/notifications'
import EnabledChip from '../EnabledChip.vue'
import AssetClassFormDialog from './AssetClassFormDialog.vue'
import RemarketingAverage from '../remarketing/RemarketingAverage.vue'
import { deleteAssetClass, listAssetClasses, REMARKETING_RATINGS, type AssetClass } from './api'

const { t } = useI18n()
const notifications = useNotificationsStore()

const table = ref<{ reload: () => Promise<void> } | null>(null)

const headers = computed(() => [
  { title: t('catalogs.fields.id'), key: 'id', width: 80 },
  { title: t('assetClasses.fields.name'), key: 'name' },
  { title: t('assetClasses.fields.subVertical'), key: 'sub_vertical_detail' },
  // Average of the four ratings; hover for each one
  { title: t('assetClasses.remarketing.title'), key: 'remarketing_average', width: 230 },
  { title: t('catalogs.fields.status'), key: 'is_enabled', width: 130 },
])

const formOpen = ref(false)
const editing = ref<AssetClass | null>(null)

function openForm(assetClass: AssetClass | null) {
  editing.value = assetClass
  formOpen.value = true
}

function onSaved(_assetClass: AssetClass, created: boolean) {
  notifications.notify(t(created ? 'assetClasses.created' : 'assetClasses.updated'))
  table.value?.reload()
}
</script>

<template>
  <ServerCrudTable
    ref="table"
    :fetch-page="listAssetClasses"
    :delete-item="deleteAssetClass"
    :headers="headers"
    :sort-by="[{ key: 'name', order: 'asc' }]"
    :ordering-fields="{
      sub_vertical_detail: 'sub_vertical__vertical__name',
      remarketing_average: 'remarketing_score',
    }"
    :search-placeholder="$t('assetClasses.searchPlaceholder')"
    :empty-text="$t('assetClasses.empty')"
    :no-results-text="$t('assetClasses.noResults')"
    :delete-title="$t('assetClasses.deleteTitle')"
    :delete-message="(a: AssetClass) => $t('assetClasses.deleteConfirm', { name: a.name })"
    :deleted-text="$t('assetClasses.deleted')"
    @create="openForm(null)"
    @edit="openForm"
  >
    <template #[`item.name`]="{ item }">
      <div class="d-flex align-center ga-3 py-2">
        <v-avatar color="primary" variant="tonal" size="36" rounded>
          <v-icon :icon="item.icon" size="20" />
        </v-avatar>
        <div>
          <div>{{ item.name }}</div>
          <div
            v-if="item.keywords.length"
            class="text-caption text-medium-emphasis text-truncate"
            style="max-width: 260px"
            :title="item.keywords.join(', ')"
            data-testid="keywords-preview"
          >
            {{ item.keywords.join(', ') }}
          </div>
        </div>
      </div>
    </template>
    <template #[`item.sub_vertical_detail`]="{ item }">
      <span :class="{ 'text-medium-emphasis': !item.sub_vertical_detail.vertical.is_enabled }">
        {{ item.sub_vertical_detail.label }}
      </span>
      <span
        v-if="!item.sub_vertical_detail.vertical.is_enabled"
        class="text-caption text-medium-emphasis"
      >
        ({{ $t('catalogs.status.disabled') }})
      </span>
    </template>
    <template #[`item.remarketing_average`]="{ item }">
      <RemarketingAverage
        :average="item.remarketing_average"
        :breakdown="
          REMARKETING_RATINGS.map((field) => ({
            label: $t(`assetClasses.remarketing.${field}.label`),
            value: item[field],
          }))
        "
      />
    </template>
    <template #[`item.is_enabled`]="{ item }">
      <EnabledChip :enabled="item.is_enabled" />
    </template>
  </ServerCrudTable>

  <AssetClassFormDialog v-model="formOpen" :asset-class="editing" @saved="onSaved" />
</template>
