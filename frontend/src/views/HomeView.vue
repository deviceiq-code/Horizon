<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

async function sair() {
  await auth.sair()
  await router.push({ name: 'login' })
}
</script>

<template>
  <v-app-bar color="primary" density="comfortable">
    <template #prepend>
      <v-icon icon="mdi-chart-line" class="ml-2" />
    </template>
    <v-app-bar-title>Sistema Horizon</v-app-bar-title>
    <template #append>
      <span class="mr-3 d-none d-sm-inline">
        <v-icon icon="mdi-account" size="small" /> {{ auth.usuario?.nome }}
      </span>
      <v-btn variant="text" prepend-icon="mdi-logout" @click="sair">Sair</v-btn>
    </template>
  </v-app-bar>

  <v-main>
    <v-container style="max-width: 1100px">
      <v-card>
        <v-card-title>Bem-vindo, {{ auth.usuario?.nome }}</v-card-title>
        <v-card-text>
          O ambiente está funcionando. Aqui entrarão as telas de ativos, curvas de residual e
          simulações de precificação.
        </v-card-text>
      </v-card>
    </v-container>
  </v-main>
</template>
