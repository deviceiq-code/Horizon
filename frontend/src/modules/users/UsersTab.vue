<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import PersonAvatar from '@/components/PersonAvatar.vue'
import ServerCrudTable from '@/components/ServerCrudTable.vue'
import { useAuthStore } from '@/stores/auth'
import { useNotificationsStore } from '@/stores/notifications'
import UserFormDialog from './UserFormDialog.vue'
import { deleteUser, listUsers, userPhotoUrl, type User } from './api'
import { roleName } from './roleText'

const { t, d } = useI18n()
const auth = useAuthStore()
const notifications = useNotificationsStore()

const table = ref<{ reload: () => Promise<void> } | null>(null)

const headers = computed(() => [
  { title: t('users.fields.username'), key: 'username' },
  { title: t('users.fields.fullName'), key: 'first_name' },
  { title: t('users.fields.email'), key: 'email' },
  { title: t('users.fields.roles'), key: 'roles_detail', sortable: false },
  { title: t('users.fields.status'), key: 'is_active', sortable: false, width: 120 },
  { title: t('users.fields.lastLogin'), key: 'last_login', width: 170 },
])

const formOpen = ref(false)
const editing = ref<User | null>(null)

function openForm(user: User | null) {
  editing.value = user
  formOpen.value = true
}

function onSaved(_user: User, created: boolean) {
  notifications.notify(t(created ? 'users.created' : 'users.updated'))
  table.value?.reload()
}

// Nobody deletes their own user (the server refuses it too)
const isMe = (user: User) => user.id === auth.user?.id
</script>

<template>
  <ServerCrudTable
    ref="table"
    :fetch-page="listUsers"
    :delete-item="deleteUser"
    :headers="headers"
    :sort-by="[{ key: 'username', order: 'asc' }]"
    :search-placeholder="$t('users.searchPlaceholder')"
    :empty-text="$t('users.empty')"
    :no-results-text="$t('users.noResults')"
    :delete-title="$t('users.deleteTitle')"
    :delete-message="(u: User) => $t('users.deleteConfirm', { name: u.username })"
    :deleted-text="$t('users.deleted')"
    :can-delete="(u: User) => !isMe(u)"
    @create="openForm(null)"
    @edit="openForm"
  >
    <template #[`item.username`]="{ item }">
      <span class="font-weight-medium">{{ item.username }}</span>
      <v-chip v-if="isMe(item)" size="x-small" class="ml-2" label>{{ $t('users.you') }}</v-chip>
    </template>
    <template #[`item.first_name`]="{ item }">
      <div class="d-flex align-center ga-3 py-1">
        <PersonAvatar
          :name="item.full_name || item.username"
          :src="item.photo_version ? userPhotoUrl(item.id, item.photo_version) : null"
          :size="36"
        />
        <span>{{ item.full_name }}</span>
      </div>
    </template>
    <template #[`item.roles_detail`]="{ item }">
      <div class="d-flex flex-wrap ga-1 py-1">
        <v-chip
          v-for="role in item.roles_detail"
          :key="role.id"
          size="small"
          :color="role.is_system ? 'primary' : undefined"
          variant="tonal"
          :prepend-icon="role.is_system ? 'mdi-shield-crown-outline' : undefined"
        >
          {{ roleName(role, t) }}
        </v-chip>
      </div>
    </template>
    <template #[`item.is_active`]="{ item }">
      <v-chip
        size="small"
        :color="item.is_active ? 'success' : undefined"
        variant="tonal"
        label
        data-testid="user-status"
      >
        {{ $t(item.is_active ? 'users.status.active' : 'users.status.inactive') }}
      </v-chip>
    </template>
    <template #[`item.last_login`]="{ item }">
      <span v-if="item.last_login">{{ d(new Date(item.last_login), 'dateTime') }}</span>
      <span v-else class="text-medium-emphasis">{{ $t('users.never') }}</span>
    </template>
  </ServerCrudTable>

  <UserFormDialog v-model="formOpen" :user="editing" @saved="onSaved" />
</template>
