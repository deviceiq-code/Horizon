import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api'
import { usePreferencesStore, type Preferences } from '@/stores/preferences'

export interface User {
  id: number
  username: string
  name: string
  /** Has the Administrator role (or is a Django superuser): can do everything */
  is_admin: boolean
  /** Names of the user's roles */
  roles: string[]
  /** Photo version (GET /api/users/<id>/photo/?v=…), null without a photo */
  photo_version: string | null
  email?: string
  /** The roles for display (system ones show translated, users/roleText.ts) */
  role_refs?: { name: string; key: string; is_system: boolean }[]
  preferences: Preferences
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const loaded = ref(false)
  const isAuthenticated = computed(() => user.value !== null)
  const preferences = usePreferencesStore()

  /** Fetch the CSRF cookie and the current session's user (once per page load). */
  async function load() {
    if (loaded.value) return
    await api('/auth/csrf/')
    try {
      user.value = await api<User>('/auth/me/')
      preferences.apply(user.value.preferences)
    } catch {
      user.value = null
    }
    loaded.value = true
  }

  async function login(username: string, password: string) {
    user.value = await api<User>('/auth/login/', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    })
    preferences.apply(user.value.preferences)
  }

  /** Read the signed-in user again (e.g. after the way names are shown changed). */
  async function refresh() {
    user.value = await api<User>('/auth/me/')
  }

  async function logout() {
    await api('/auth/logout/', { method: 'POST' })
    user.value = null
  }

  return { user, loaded, isAuthenticated, load, login, logout, refresh }
})
