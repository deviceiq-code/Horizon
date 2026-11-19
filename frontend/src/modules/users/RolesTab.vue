<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import ServerCrudTable from '@/components/ServerCrudTable.vue'
import { useNotificationsStore } from '@/stores/notifications'
import RoleFormDialog from './RoleFormDialog.vue'
import { deleteRole, listRoles, type Role } from './api'
import { roleDescription, roleName } from './roleText'

const { t } = useI18n()
const notifications = useNotificationsStore()

const table = ref<{ reload: () => Promise<void> } | null>(null)

const headers = computed(() => [
  { title: t('users.roles.fields.name'), key: 'name' },
  { title: t('users.roles.fields.description'), key: 'description', sortable: false },
  { title: t('users.roles.fields.users'), key: 'users_count', align: 'end' as const, width: 130 },
])

const formOpen = ref(false)
const editing = ref<Role | null>(null)

function openForm(role: Role | null) {
  editing.value = role
  formOpen.value = true
}

function onSaved(_role: Role, created: boolean) {
  notifications.notify(t(created ? 'users.roles.created' : 'users.roles.updated'))
  table.value?.reload()
}
</script>

<template>
  <ServerCrudTable
    ref="table"
    :fetch-page="listRoles"
    :delete-item="deleteRole"
    :headers="headers"
    :sort-by="[{ key: 'name', order: 'asc' }]"
    :search-placeholder="$t('users.roles.searchPlaceholder')"
    :empty-text="$t('users.roles.empty')"
    :no-results-text="$t('users.roles.noResults')"
    :delete-title="$t('users.roles.deleteTitle')"
    :delete-message="(r: Role) => $t('users.roles.deleteConfirm', { name: roleName(r, t) })"
    :deleted-text="$t('users.roles.deleted')"
    :can-edit="(r: Role) => !r.is_system"
    :can-delete="(r: Role) => !r.is_system"
    @create="openForm(null)"
    @edit="openForm"
  >
    <template #[`item.name`]="{ item }">
      <span class="font-weight-medium">{{ roleName(item, t) }}</span>
      <v-chip
        v-if="item.is_system"
        size="x-small"
        color="primary"
        variant="tonal"
        prepend-icon="mdi-shield-crown-outline"
        class="ml-2"
        :title="$t('users.roles.systemHint')"
        label
        data-testid="system-role"
      >
        {{ $t('users.roles.system') }}
      </v-chip>
    </template>
    <template #[`item.description`]="{ item }">
      <span class="text-medium-emphasis">{{ roleDescription(item, t) }}</span>
    </template>
  </ServerCrudTable>

  <RoleFormDialog v-model="formOpen" :role="editing" @saved="onSaved" />
</template>
