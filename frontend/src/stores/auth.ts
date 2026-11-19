import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api'

export interface Usuario {
  id: number
  username: string
  nome: string
  is_staff: boolean
}

export const useAuthStore = defineStore('auth', () => {
  const usuario = ref<Usuario | null>(null)
  const carregado = ref(false)
  const autenticado = computed(() => usuario.value !== null)

  /** Busca o cookie CSRF e o usuário da sessão atual (uma vez por carregamento). */
  async function carregar() {
    if (carregado.value) return
    await api('/auth/csrf/')
    try {
      usuario.value = await api<Usuario>('/auth/me/')
    } catch {
      usuario.value = null
    }
    carregado.value = true
  }

  async function entrar(username: string, password: string) {
    usuario.value = await api<Usuario>('/auth/login/', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    })
  }

  async function sair() {
    await api('/auth/logout/', { method: 'POST' })
    usuario.value = null
  }

  return { usuario, carregado, autenticado, carregar, entrar, sair }
})
