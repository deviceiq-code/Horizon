import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api'
import { usePreferencesStore, type Preferences } from '@/stores/preferences'

export interface User {
  id: number
  username: string
  name: string
  is_staff: boolean
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

  async function logout() {
    await api('/auth/logout/', { method: 'POST' })
    user.value = null
  }

  return { user, loaded, isAuthenticated, load, login, logout }
})
