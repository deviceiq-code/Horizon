<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { deleteErrorMessage } from '@/api'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import { useServerTable } from '@/composables/useServerTable'
import { useNotificationsStore } from '@/stores/notifications'
import RiskChip from './RiskChip.vue'
import VerticalFormDialog from './VerticalFormDialog.vue'
import { deleteVertical, listVerticals, type Vertical } from './api'

/** How many account manager chips to show per row before "+N". */
const MAX_CHIPS = 3

const { t } = useI18n()
const notifications = useNotificationsStore()

// --- Grid (server-side pagination, sorting and search) ---------------------------------------

const {
  items,
  total,
  loading,
  loadError,
  page,
  itemsPerPage,
  sortBy,
  searchInput,
  search,
  load,
  reloadAfterDelete,
} = useServerTable(listVerticals, { sortBy: [{ key: 'name', order: 'asc' }] })

const headers = computed(() => [
  { title: '', key: 'data-table-expand', width: 48 },
  { title: t('verticals.fields.id'), key: 'id', width: 90 },
  { title: t('verticals.fields.name'), key: 'name' },
  {
    title: t('verticals.subVerticals'),
    key: 'sub_verticals',
    sortable: false,
    width: 140,
  },
  {
    title: t('verticals.fields.accountManagers'),
    key: 'account_managers_detail',
    sortable: false,
  },
  { title: t('verticals.fields.status'), key: 'is_enabled', width: 140 },
  {
    title: t('common.actions'),
    key: 'actions',
    sortable: false,
    align: 'end' as const,
    width: 120,
  },
])

// --- Create / edit ---------------------------------------------------------------------------

const formOpen = ref(false)
const editing = ref<Vertical | null>(null)

function openCreate() {
  editing.value = null
  formOpen.value = true
}

function openEdit(vertical: Vertical) {
  editing.value = vertical
  formOpen.value = true
}

function onSaved(_vertical: Vertical, created: boolean) {
  notifications.notify(t(created ? 'verticals.created' : 'verticals.updated'))
  load()
}

// --- Delete ----------------------------------------------------------------------------------

const deleting = ref<Vertical | null>(null)
const confirmOpen = ref(false)
const deleteInProgress = ref(false)

function askDelete(vertical: Vertical) {
  deleting.value = vertical
  confirmOpen.value = true
}

async function confirmDelete() {
  if (!deleting.value) return
  deleteInProgress.value = true
  try {
    await deleteVertical(deleting.value.id)
    notifications.notify(t('verticals.deleted'))
    confirmOpen.value = false
    await reloadAfterDelete()
  } catch (error) {
    notifications.notify(deleteErrorMessage(error, t('common.deleteError')), 'error')
    confirmOpen.value = false
  } finally {
    deleteInProgress.value = false
  }
}
</script>

<template>
  <div>
    <div class="d-flex flex-wrap align-center ga-3 mb-4">
      <v-text-field
        v-model="searchInput"
        :placeholder="$t('verticals.searchPlaceholder')"
        :aria-label="$t('common.search')"
        prepend-inner-icon="mdi-magnify"
        density="compact"
        clearable
        hide-details
        class="mr-auto"
        style="min-width: 260px; max-width: 400px"
        data-testid="search"
      />
      <v-btn color="primary" prepend-icon="mdi-plus" data-testid="new" @click="openCreate">
        {{ $t('common.new') }}
      </v-btn>
    </div>

    <v-alert v-if="loadError" type="error" variant="tonal" class="mb-4">
      {{ $t('common.loadError') }}
      <template #append>
        <v-btn variant="text" size="small" @click="load">{{ $t('common.retry') }}</v-btn>
      </template>
    </v-alert>

    <v-card>
      <v-data-table-server
        v-model:page="page"
        v-model:items-per-page="itemsPerPage"
        v-model:sort-by="sortBy"
        :headers="headers"
        :items="items"
        :items-length="total"
        :loading="loading"
        :search="search"
        :items-per-page-options="[10, 25, 50, 100]"
        :no-data-text="search ? $t('verticals.noResults') : $t('verticals.empty')"
        item-value="id"
        show-expand
        must-sort
        hover
        @update:options="load"
      >
        <template #[`item.sub_verticals`]="{ item }">
          {{ $t('verticals.subVerticalCount', item.sub_verticals.length) }}
        </template>
        <template #expanded-row="{ columns, item }">
          <tr>
            <td :colspan="columns.length" class="bg-surface-light pa-0">
              <v-table density="compact" class="bg-transparent" data-testid="sub-verticals-table">
                <thead>
                  <tr>
                    <th class="pl-16">{{ $t('verticals.fields.subVertical') }}</th>
                    <th>{{ $t('verticals.fields.risk') }}</th>
                    <th>{{ $t('verticals.fields.allowedTerms') }}</th>
                    <th>{{ $t('verticals.fields.recommendedTerm') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="sub in item.sub_verticals"
                    :key="sub.id"
                    data-testid="sub-vertical-row"
                  >
                    <td class="pl-16">
                      <span v-if="sub.is_general" class="font-weight-medium">
                        {{ $t('verticals.general') }}
                      </span>
                      <span v-else>{{ sub.name }}</span>
                    </td>
                    <td><RiskChip :risk="sub.risk" /></td>
                    <td>{{ sub.allowed_terms.join(' · ') }}</td>
                    <td class="font-weight-medium">
                      {{ $t('verticals.months', sub.recommended_term ?? 0) }}
                    </td>
                  </tr>
                </tbody>
              </v-table>
            </td>
          </tr>
        </template>
        <template #[`item.name`]="{ item }">
          <div>{{ item.name }}</div>
          <div
            v-if="item.notes"
            class="text-caption text-medium-emphasis text-truncate"
            style="max-width: 360px"
            :title="item.notes"
          >
            {{ item.notes }}
          </div>
        </template>
        <template #[`item.account_managers_detail`]="{ item }">
          <div class="d-flex flex-wrap ga-1 py-1">
            <v-chip
              v-for="manager in item.account_managers_detail.slice(0, MAX_CHIPS)"
              :key="manager.id"
              size="small"
            >
              {{ manager.full_name }}
            </v-chip>
            <v-chip
              v-if="item.account_managers_detail.length > MAX_CHIPS"
              size="small"
              variant="text"
              :title="
                item.account_managers_detail
                  .slice(MAX_CHIPS)
                  .map((m) => m.full_name)
                  .join(', ')
              "
            >
              +{{ item.account_managers_detail.length - MAX_CHIPS }}
            </v-chip>
            <span v-if="!item.account_managers_detail.length" class="text-medium-emphasis">
              —
            </span>
          </div>
        </template>
        <template #[`item.is_enabled`]="{ item }">
          <v-chip
            :color="item.is_enabled ? 'success' : undefined"
            size="small"
            variant="tonal"
            label
          >
            {{ item.is_enabled ? $t('verticals.status.enabled') : $t('verticals.status.disabled') }}
          </v-chip>
        </template>
        <template #[`item.actions`]="{ item }">
          <v-btn
            icon="mdi-pencil-outline"
            variant="text"
            size="small"
            :aria-label="$t('common.edit')"
            :title="$t('common.edit')"
            data-testid="edit"
            @click="openEdit(item)"
          />
          <v-btn
            icon="mdi-delete-outline"
            variant="text"
            size="small"
            color="error"
            :aria-label="$t('common.delete')"
            :title="$t('common.delete')"
            data-testid="delete"
            @click="askDelete(item)"
          />
        </template>
      </v-data-table-server>
    </v-card>

    <VerticalFormDialog v-model="formOpen" :vertical="editing" @saved="onSaved" />

    <ConfirmDialog
      v-model="confirmOpen"
      :title="$t('verticals.deleteTitle')"
      :message="$t('verticals.deleteConfirm', { name: deleting?.name ?? '' })"
      :confirm-text="$t('common.delete')"
      :loading="deleteInProgress"
      @confirm="confirmDelete"
    />
  </div>
</template>
