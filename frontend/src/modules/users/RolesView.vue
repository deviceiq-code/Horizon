<script setup lang="ts">
/**
 * Roles of the users (administrators only), as cards (the Haze "Roles" page): name, how many
 * users and who they are (chips, "+N more"), description and keywords. System roles show
 * translated and cannot be changed or deleted; a role with users cannot be deleted (409).
 */
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { deleteErrorMessage } from '@/api'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import PersonAvatar from '@/components/PersonAvatar.vue'
import { useNotificationsStore } from '@/stores/notifications'
import RoleFormDialog from './RoleFormDialog.vue'
import { deleteRole, allRoles, userPhotoUrl, type Role } from './api'
import { roleDescription, roleName } from './roleText'

/** Members shown on a card before "+N more" */
const MEMBERS_SHOWN = 6

const { t } = useI18n()
const notifications = useNotificationsStore()

const roles = ref<Role[]>([])
const loading = ref(true)
const loadError = ref(false)

async function load() {
  loading.value = true
  loadError.value = false
  try {
    roles.value = await allRoles()
  } catch {
    loadError.value = true
  } finally {
    loading.value = false
  }
}
onMounted(load)

// System roles first, then by name
const sorted = computed(() =>
  [...roles.value].sort(
    (a, b) =>
      Number(b.is_system) - Number(a.is_system) || roleName(a, t).localeCompare(roleName(b, t)),
  ),
)

// --- Create / edit -----------------------------------------------------------------------------

const formOpen = ref(false)
const editing = ref<Role | null>(null)

function openForm(role: Role | null) {
  editing.value = role
  formOpen.value = true
}

function onSaved(_role: Role, created: boolean) {
  notifications.notify(t(created ? 'users.roles.created' : 'users.roles.updated'))
  load()
}

// --- Delete -----------------------------------------------------------------------------------

const deleting = ref<Role | null>(null)
const confirmOpen = ref(false)
const deleteBusy = ref(false)

function askDelete(role: Role) {
  deleting.value = role
  confirmOpen.value = true
}

async function confirmDelete() {
  if (!deleting.value) return
  deleteBusy.value = true
  try {
    await deleteRole(deleting.value.id)
    notifications.notify(t('users.roles.deleted'))
    await load()
  } catch (error) {
    // E.g. a role with users (409): the server says why
    notifications.notify(deleteErrorMessage(error, t('common.deleteError')), 'error')
  } finally {
    deleteBusy.value = false
    confirmOpen.value = false
  }
}
</script>

<template>
  <v-container fluid class="module-page">
    <div class="d-flex flex-wrap align-start ga-3 mb-5">
      <div class="flex-grow-1">
        <h1 class="mb-1">{{ $t('users.tabs.roles') }}</h1>
        <p class="text-medium-emphasis mb-0">{{ $t('users.rolesSubtitle') }}</p>
      </div>
      <v-btn color="primary" prepend-icon="mdi-plus" data-testid="new" @click="openForm(null)">
        {{ $t('users.roles.new') }}
      </v-btn>
    </div>

    <v-progress-linear v-if="loading && !roles.length" indeterminate />
    <v-alert v-else-if="loadError" type="error" variant="tonal">
      {{ $t('common.loadError') }}
      <template #append>
        <v-btn variant="text" size="small" @click="load">{{ $t('common.retry') }}</v-btn>
      </template>
    </v-alert>
    <p v-else-if="!roles.length" class="text-medium-emphasis">{{ $t('users.roles.empty') }}</p>

    <v-row v-else>
      <v-col v-for="role in sorted" :key="role.id" cols="12" md="6" xl="4">
        <v-card class="role-card h-100 pa-5" data-testid="role-card">
          <div class="d-flex align-start ga-2">
            <div class="flex-grow-1 min-w-0">
              <div class="d-flex align-center flex-wrap ga-2">
                <span class="role-name" data-testid="role-name">{{ roleName(role, t) }}</span>
                <v-chip
                  v-if="role.is_system"
                  size="x-small"
                  color="primary"
                  variant="tonal"
                  prepend-icon="mdi-shield-crown-outline"
                  :title="$t('users.roles.systemHint')"
                  label
                  data-testid="system-role"
                >
                  {{ $t('users.roles.system') }}
                </v-chip>
              </div>
              <div class="text-medium-emphasis" data-testid="role-users-count">
                {{ $t('users.roles.users_count', role.users_count) }}
              </div>
            </div>
            <template v-if="!role.is_system">
              <v-btn
                icon="mdi-pencil-outline"
                variant="text"
                size="small"
                :title="$t('users.roles.edit')"
                :aria-label="$t('users.roles.edit')"
                data-testid="edit"
                @click="openForm(role)"
              />
              <v-btn
                icon="mdi-delete-outline"
                variant="text"
                size="small"
                color="error"
                :title="$t('users.roles.deleteTitle')"
                :aria-label="$t('users.roles.deleteTitle')"
                data-testid="delete"
                @click="askDelete(role)"
              />
            </template>
            <v-icon
              v-else
              icon="mdi-lock-outline"
              size="small"
              class="text-medium-emphasis mt-1"
              :title="$t('users.roles.systemHint')"
            />
          </div>

          <p
            v-if="roleDescription(role, t)"
            class="text-body-2 text-medium-emphasis mt-3 mb-0"
            data-testid="role-description"
          >
            {{ roleDescription(role, t) }}
          </p>

          <!-- Who has it (the Haze card's "permissions" place) -->
          <div class="section-title mt-5 mb-2">
            {{ $t('users.roles.membersTitle') }}
          </div>
          <div class="d-flex flex-wrap ga-2" data-testid="role-members">
            <v-chip
              v-for="member in role.members.slice(0, MEMBERS_SHOWN)"
              :key="member.id"
              size="small"
              :class="{ 'text-disabled': !member.is_active }"
              data-testid="role-member"
            >
              <template #prepend>
                <PersonAvatar
                  :name="member.full_name"
                  :src="member.photo_version ? userPhotoUrl(member.id, member.photo_version) : null"
                  :size="18"
                  color="primary"
                  class="mr-1"
                />
              </template>
              {{ member.full_name }}
            </v-chip>
            <v-chip
              v-if="role.members.length > MEMBERS_SHOWN"
              size="small"
              variant="text"
              data-testid="role-more-members"
            >
              {{ $t('users.roles.moreMembers', { n: role.members.length - MEMBERS_SHOWN }) }}
            </v-chip>
            <span v-if="!role.members.length" class="text-body-2 text-medium-emphasis">
              {{ $t('users.roles.noMembers') }}
            </span>
          </div>

          <div v-if="role.keywords.length" class="d-flex flex-wrap ga-1 mt-4">
            <v-chip
              v-for="keyword in role.keywords"
              :key="keyword"
              size="x-small"
              variant="outlined"
              prepend-icon="mdi-tag-outline"
              label
            >
              {{ keyword }}
            </v-chip>
          </div>
        </v-card>
      </v-col>
    </v-row>

    <RoleFormDialog v-model="formOpen" :role="editing" @saved="onSaved" />
    <ConfirmDialog
      v-model="confirmOpen"
      :title="$t('users.roles.deleteTitle')"
      :message="deleting ? $t('users.roles.deleteConfirm', { name: roleName(deleting, t) }) : ''"
      :confirm-text="$t('common.delete')"
      :loading="deleteBusy"
      @confirm="confirmDelete"
    />
  </v-container>
</template>

<style scoped>
.role-name {
  font-size: 1.125rem;
  font-weight: 600;
}
.section-title {
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.min-w-0 {
  min-width: 0;
}
</style>
