<script setup lang="ts">
import { useDateFormat } from '@/composables/useDateFormat'
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import PersonAvatar from '@/components/PersonAvatar.vue'
import ServerCrudTable from '@/components/ServerCrudTable.vue'
import { useAuthStore } from '@/stores/auth'
import { useNotificationsStore } from '@/stores/notifications'
import UserFormDialog from './UserFormDialog.vue'
import { allRoles, deleteUser, listUsers, userPhotoUrl, type Role, type User } from './api'
import { roleName } from './roleText'

const { t } = useI18n()
// Dates in the formats the user chose (Settings)
const { d } = useDateFormat()
const auth = useAuthStore()
const notifications = useNotificationsStore()

const table = ref<{ reload: () => Promise<void> } | null>(null)
const route = useRoute()

// --- Column filters (?role= in the address opens them, e.g. from the former Account Managers)

const initialRole = typeof route.query.role === 'string' ? route.query.role : null
const filters = reactive<Record<string, string | null>>({ role: initialRole, is_active: null })
const roles = ref<Role[]>([])
onMounted(async () => {
  try {
    roles.value = await allRoles()
  } catch {
    roles.value = []
  }
})
// System roles by their key (stable), the others by id
const roleOptions = computed(() =>
  roles.value.map((role) => ({
    value: role.is_system && role.key ? role.key : String(role.id),
    title: roleName(role, t),
  })),
)
const statusOptions = computed(() => [
  { value: 'true', title: t('users.status.active') },
  { value: 'false', title: t('users.status.inactive') },
])
function clearFilters() {
  filters.role = null
  filters.is_active = null
}

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
    :filters="filters"
    filters-storage-key="users"
    :show-filters-at-start="!!initialRole"
    @clear-filters="clearFilters"
    @create="openForm(null)"
    @edit="openForm"
  >
    <template #[`filter.roles_detail`]>
      <v-select
        v-model="filters.role"
        :items="roleOptions"
        :placeholder="$t('users.filters.role')"
        density="compact"
        hide-details
        clearable
        data-testid="filter-role"
      />
    </template>
    <template #[`filter.is_active`]>
      <v-select
        v-model="filters.is_active"
        :items="statusOptions"
        :placeholder="$t('users.filters.all')"
        density="compact"
        hide-details
        clearable
        data-testid="filter-status"
      />
    </template>
    <template #[`item.username`]="{ item }">
      <span class="font-weight-medium">{{ item.username }}</span>
      <v-chip v-if="isMe(item)" size="x-small" class="ml-2" label>{{ $t('users.you') }}</v-chip>
      <v-chip
        v-if="!item.has_password"
        size="x-small"
        color="warning"
        variant="tonal"
        class="ml-2"
        :title="$t('users.noPasswordHint')"
        label
        data-testid="no-password"
      >
        {{ $t('users.noPassword') }}
      </v-chip>
    </template>
    <template #[`item.first_name`]="{ item }">
      <div class="d-flex align-center ga-3 py-1">
        <PersonAvatar
          :name="item.full_name || item.username"
          :src="item.photo_version ? userPhotoUrl(item.id, item.photo_version) : null"
          :size="36"
        />
        <div>
          <div>{{ item.full_name }}</div>
          <div v-if="item.job_title" class="text-caption text-medium-emphasis">
            {{ item.job_title }}
          </div>
        </div>
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
