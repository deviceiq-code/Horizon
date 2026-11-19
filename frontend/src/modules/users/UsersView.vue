<script setup lang="ts">
/** Users of the system and roles (administrators only), in two tabs (?tab=roles). */
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import RolesTab from './RolesTab.vue'
import UsersTab from './UsersTab.vue'

type Tab = 'users' | 'roles'
const route = useRoute()
const router = useRouter()
const tab = computed<Tab>({
  get: () => (route.query.tab === 'roles' ? 'roles' : 'users'),
  set: (value) => {
    router.replace({ query: { ...route.query, tab: value === 'users' ? undefined : value } })
  },
})
</script>

<template>
  <v-container fluid class="module-page">
    <h1 class="text-h5 mb-1">{{ $t('users.title') }}</h1>
    <p class="text-medium-emphasis mb-3">{{ $t('users.subtitle') }}</p>

    <v-tabs v-model="tab" color="primary" class="mb-4">
      <v-tab value="users" prepend-icon="mdi-account-outline" data-testid="tab-users">
        {{ $t('users.tabs.users') }}
      </v-tab>
      <v-tab value="roles" prepend-icon="mdi-shield-account-outline" data-testid="tab-roles">
        {{ $t('users.tabs.roles') }}
      </v-tab>
    </v-tabs>

    <UsersTab v-if="tab === 'users'" />
    <RolesTab v-else />
  </v-container>
</template>
