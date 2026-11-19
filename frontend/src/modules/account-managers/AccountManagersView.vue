<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { deleteErrorMessage } from '@/api'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import { useServerTable } from '@/composables/useServerTable'
import { useNotificationsStore } from '@/stores/notifications'
import AccountManagerAvatar from './AccountManagerAvatar.vue'
import AccountManagerFormDialog from './AccountManagerFormDialog.vue'
import { deleteAccountManager, listAccountManagers, type AccountManager } from './api'

/** How many vertical chips to show per row before "+N". */
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
} = useServerTable(listAccountManagers, { sortBy: [{ key: 'full_name', order: 'asc' }] })

const headers = computed(() => [
  { title: t('accountManagers.fields.id'), key: 'id', width: 100 },
  { title: t('accountManagers.fields.fullName'), key: 'full_name' },
  { title: t('accountManagers.fields.email'), key: 'email' },
  { title: t('accountManagers.fields.verticals'), key: 'verticals_detail', sortable: false },
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
const editing = ref<AccountManager | null>(null)

function openCreate() {
  editing.value = null
  formOpen.value = true
}

function openEdit(manager: AccountManager) {
  editing.value = manager
  formOpen.value = true
}

function onSaved(_manager: AccountManager, created: boolean) {
  notifications.notify(t(created ? 'accountManagers.created' : 'accountManagers.updated'))
  load()
}

// --- Delete ----------------------------------------------------------------------------------

const deleting = ref<AccountManager | null>(null)
const confirmOpen = ref(false)
const deleteInProgress = ref(false)

function askDelete(manager: AccountManager) {
  deleting.value = manager
  confirmOpen.value = true
}

async function confirmDelete() {
  if (!deleting.value) return
  deleteInProgress.value = true
  try {
    await deleteAccountManager(deleting.value.id)
    notifications.notify(t('accountManagers.deleted'))
    confirmOpen.value = false
    await reloadAfterDelete()
  } catch (error) {
    // e.g. 409: the account manager still has customers
    notifications.notify(deleteErrorMessage(error, t('common.deleteError')), 'error')
    confirmOpen.value = false
  } finally {
    deleteInProgress.value = false
  }
}
</script>

<template>
  <v-container fluid class="module-page">
    <div class="d-flex flex-wrap align-center ga-3 mb-4">
      <h1 class="text-h5 mr-auto">{{ $t('accountManagers.title') }}</h1>
      <v-text-field
        v-model="searchInput"
        :placeholder="$t('accountManagers.searchPlaceholder')"
        :aria-label="$t('common.search')"
        prepend-inner-icon="mdi-magnify"
        density="compact"
        clearable
        hide-details
        style="min-width: 260px; max-width: 360px"
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
        :no-data-text="search ? $t('accountManagers.noResults') : $t('accountManagers.empty')"
        must-sort
        hover
        @update:options="load"
      >
        <template #[`item.full_name`]="{ item }">
          <div class="d-flex align-center ga-3 py-1">
            <AccountManagerAvatar
              :name="item.full_name"
              :id="item.id"
              :photo-version="item.photo_version"
              :size="36"
            />
            <span>{{ item.full_name }}</span>
          </div>
        </template>
        <template #[`item.verticals_detail`]="{ item }">
          <div class="d-flex flex-wrap ga-1 py-1">
            <v-chip
              v-for="vertical in item.verticals_detail.slice(0, MAX_CHIPS)"
              :key="vertical.id"
              size="small"
              :variant="vertical.is_enabled ? 'tonal' : 'outlined'"
              :title="vertical.is_enabled ? undefined : $t('verticals.status.disabled')"
              :class="{ 'text-disabled': !vertical.is_enabled }"
            >
              {{ vertical.name }}
            </v-chip>
            <v-chip
              v-if="item.verticals_detail.length > MAX_CHIPS"
              size="small"
              variant="text"
              :title="
                item.verticals_detail
                  .slice(MAX_CHIPS)
                  .map((v) => v.name)
                  .join(', ')
              "
            >
              +{{ item.verticals_detail.length - MAX_CHIPS }}
            </v-chip>
            <span v-if="!item.verticals_detail.length" class="text-medium-emphasis">—</span>
          </div>
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

    <AccountManagerFormDialog v-model="formOpen" :manager="editing" @saved="onSaved" />

    <ConfirmDialog
      v-model="confirmOpen"
      :title="$t('accountManagers.deleteTitle')"
      :message="$t('accountManagers.deleteConfirm', { name: deleting?.full_name ?? '' })"
      :confirm-text="$t('common.delete')"
      :loading="deleteInProgress"
      @confirm="confirmDelete"
    />
  </v-container>
</template>
