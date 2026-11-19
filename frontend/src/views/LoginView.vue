<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const username = ref('')
const password = ref('')
const mostrarSenha = ref(false)
const erro = ref('')
const carregando = ref(false)

async function entrar() {
  erro.value = ''
  carregando.value = true
  try {
    await auth.entrar(username.value, password.value)
    const destino = typeof route.query.next === 'string' ? route.query.next : '/'
    await router.push(destino)
  } catch {
    erro.value = 'Usuário ou senha inválidos.'
  } finally {
    carregando.value = false
  }
}
</script>

<template>
  <v-main class="d-flex align-center justify-center pa-4">
    <v-card width="400" max-width="100%" elevation="4" class="pa-2">
      <v-card-item>
        <v-card-title class="text-h5">Sistema Horizon</v-card-title>
        <v-card-subtitle>Precificação de residuais de leasing operacional</v-card-subtitle>
      </v-card-item>

      <v-card-text>
        <v-form @submit.prevent="entrar">
          <v-text-field
            v-model="username"
            label="Usuário"
            prepend-inner-icon="mdi-account"
            autocomplete="username"
            autofocus
          />
          <v-text-field
            v-model="password"
            label="Senha"
            prepend-inner-icon="mdi-lock"
            :type="mostrarSenha ? 'text' : 'password'"
            :append-inner-icon="mostrarSenha ? 'mdi-eye-off' : 'mdi-eye'"
            autocomplete="current-password"
            @click:append-inner="mostrarSenha = !mostrarSenha"
          />

          <v-alert v-if="erro" type="error" variant="tonal" density="compact" class="mb-4">
            {{ erro }}
          </v-alert>

          <v-btn
            type="submit"
            color="primary"
            size="large"
            block
            prepend-icon="mdi-login"
            :loading="carregando"
          >
            Entrar
          </v-btn>
        </v-form>
      </v-card-text>
    </v-card>
  </v-main>
</template>
