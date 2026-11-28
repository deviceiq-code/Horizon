<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import ServerCrudTable from '@/components/ServerCrudTable.vue'
import { useNotificationsStore } from '@/stores/notifications'
import EnabledChip from '../EnabledChip.vue'
import AssetClassFormDialog from './AssetClassFormDialog.vue'
import { useAssetClassFilters } from './useAssetClassFilters'
import SpecTemplateDialog from './SpecTemplateDialog.vue'
import CompareAssetClassesDialog from './CompareAssetClassesDialog.vue'
import { MAX_COMPARED } from '@/utils/battle'
import RemarketingAverage from '../remarketing/RemarketingAverage.vue'
import { deleteAssetClass, listAssetClasses, REMARKETING_RATINGS, type AssetClass } from './api'

const { t } = useI18n()
const notifications = useNotificationsStore()

const table = ref<{ reload: () => Promise<void> } | null>(null)

// --- Column filters --------------------------------------------------------------------------

const {
  filters,
  typedName,
  scope,
  scopeItems,
  loadVerticals,
  clear: clearFilters,
} = useAssetClassFilters()
onMounted(() => loadVerticals().catch(() => undefined))
const starOptions = [1, 2, 3, 4, 5].map((stars) => ({
  value: stars,
  title: `★ ${stars}+`,
}))
const statusOptions = computed(() => [
  { value: 'true', title: t('catalogs.status.enabled') },
  { value: 'false', title: t('catalogs.status.disabled') },
])

const headers = computed(() => [
  { title: t('catalogs.fields.id'), key: 'id', width: 80 },
  { title: t('assetClasses.fields.name'), key: 'name', minWidth: '220px' },
  { title: t('assetClasses.fields.subVertical'), key: 'sub_vertical_detail', minWidth: '240px' },
  // Average of the four ratings; hover for each one
  { title: t('assetClasses.remarketing.title'), key: 'remarketing_average', width: 230 },
  { title: t('catalogs.fields.status'), key: 'is_enabled', width: 150 },
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

// --- Specification template ------------------------------------------------------------------

// --- Compare (up to three, as Battle Cards) -------------------------------------------------

const comparing = ref(false)
const selected = ref<number[]>([])
const compareOpen = ref(false)

function startComparing() {
  selected.value = []
  comparing.value = true
}

function stopComparing() {
  comparing.value = false
  selected.value = []
}

watch(selected, (ids) => {
  if (ids.length > MAX_COMPARED) {
    selected.value = ids.slice(0, MAX_COMPARED)
    notifications.notify(t('assetClasses.compare.max', { n: MAX_COMPARED }), 'warning')
  }
})

const templateOpen = ref(false)
const templateOf = ref<AssetClass | null>(null)

function openTemplate(assetClass: AssetClass) {
  templateOf.value = assetClass
  templateOpen.value = true
}
</script>

<template>
  <ServerCrudTable
    ref="table"
    class="asset-classes-grid"
    :fetch-page="listAssetClasses"
    :delete-item="deleteAssetClass"
    :headers="headers"
    :sort-by="[{ key: 'name', order: 'asc' }]"
    :ordering-fields="{
      sub_vertical_detail: 'sub_vertical__vertical__name',
      remarketing_average: 'remarketing_score',
    }"
    :search-placeholder="$t('assetClasses.searchPlaceholder')"
    :filters="filters"
    filters-storage-key="asset-classes"
    :selectable="comparing"
    v-model:selected="selected"
    @clear-filters="clearFilters"
    :empty-text="$t('assetClasses.empty')"
    :no-results-text="$t('assetClasses.noResults')"
    :delete-title="$t('assetClasses.deleteTitle')"
    :delete-message="(a: AssetClass) => $t('assetClasses.deleteConfirm', { name: a.name })"
    :deleted-text="$t('assetClasses.deleted')"
    @create="openForm(null)"
    @edit="openForm"
  >
    <template #toolbar>
      <v-btn
        v-if="!comparing"
        variant="text"
        prepend-icon="mdi-cards-outline"
        data-testid="compare-start"
        @click="startComparing"
      >
        {{ $t('assetClasses.compare.button') }}
      </v-btn>
      <template v-else>
        <span class="text-body-2 text-medium-emphasis" data-testid="compare-count">{{
          $t('assetClasses.compare.selected', { n: selected.length, max: MAX_COMPARED })
        }}</span>
        <v-btn
          color="primary"
          variant="tonal"
          prepend-icon="mdi-cards-outline"
          :disabled="selected.length < 2"
          data-testid="compare-open"
          @click="compareOpen = true"
        >
          {{ $t('assetClasses.compare.button') }}
        </v-btn>
        <v-btn variant="text" data-testid="compare-cancel" @click="stopComparing">{{
          $t('common.cancel')
        }}</v-btn>
      </template>
    </template>
    <template #row-actions="{ item }">
      <v-btn
        icon
        variant="text"
        size="small"
        :aria-label="$t('specTemplate.title')"
        :title="$t('specTemplate.fieldCount', item.spec_template.length)"
        data-testid="edit-spec-template"
        @click="openTemplate(item)"
      >
        <v-badge
          :content="item.spec_template.length"
          :model-value="item.spec_template.length > 0"
          color="primary"
          floating
        >
          <v-icon icon="mdi-format-list-checks" />
        </v-badge>
      </v-btn>
    </template>
    <template #[`filter.name`]>
      <v-text-field
        v-model="typedName"
        :placeholder="$t('assetClasses.filters.name')"
        prepend-inner-icon="mdi-filter-outline"
        density="compact"
        hide-details
        clearable
        data-testid="filter-name"
      />
    </template>
    <template #[`filter.sub_vertical_detail`]>
      <v-autocomplete
        v-model="scope"
        :items="scopeItems"
        :placeholder="$t('assetClasses.filters.scope')"
        density="compact"
        hide-details
        clearable
        data-testid="filter-scope"
      />
    </template>
    <template #[`filter.remarketing_average`]>
      <v-select
        v-model="filters.remarketing_min"
        :items="starOptions"
        :placeholder="$t('assetClasses.filters.minStars')"
        density="compact"
        hide-details
        clearable
        data-testid="filter-stars"
      />
    </template>
    <template #[`filter.is_enabled`]>
      <v-select
        v-model="filters.is_enabled"
        :items="statusOptions"
        :placeholder="$t('assetClasses.filters.all')"
        density="compact"
        hide-details
        clearable
        data-testid="filter-status"
      />
    </template>
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

  <CompareAssetClassesDialog v-model="compareOpen" :ids="selected" />
  <AssetClassFormDialog v-model="formOpen" :asset-class="editing" @saved="onSaved" />
  <SpecTemplateDialog
    v-model="templateOpen"
    :asset-class-id="templateOf?.id ?? null"
    :vertical-id="templateOf?.sub_vertical_detail.vertical.id ?? null"
    :label="templateOf ? `${templateOf.name} — ${templateOf.sub_vertical_detail.label}` : ''"
    @saved="table?.reload()"
  />
</template>

<style scoped>
/* Every row the same height — with keywords under the name or not — with room above the
   specification count, which sits on the button's corner (a short row cut it) */
.asset-classes-grid :deep(tbody tr:not(.v-data-table-rows-no-data) > td) {
  height: 72px;
}
.asset-classes-grid :deep(.v-badge__badge) {
  z-index: 1;
}
</style>
