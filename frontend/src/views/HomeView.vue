<script setup lang="ts">
import { useRouter } from 'vue-router'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Toolbar from 'primevue/toolbar'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

async function sair() {
  await auth.sair()
  await router.push({ name: 'login' })
}
</script>

<template>
  <Toolbar class="barra">
    <template #start>
      <i class="pi pi-chart-line" />
      <strong>Sistema Horizon</strong>
    </template>
    <template #end>
      <span class="usuario"><i class="pi pi-user" /> {{ auth.usuario?.nome }}</span>
      <Button label="Sair" icon="pi pi-sign-out" severity="secondary" text @click="sair" />
    </template>
  </Toolbar>

  <main class="conteudo">
    <Card>
      <template #title>Bem-vindo, {{ auth.usuario?.nome }}</template>
      <template #content>
        <p>
          O ambiente está funcionando. Aqui entrarão as telas de ativos, curvas de residual e
          simulações de precificação.
        </p>
      </template>
    </Card>
  </main>
</template>

<style scoped>
.barra {
  border-radius: 0;
  border-width: 0 0 1px 0;
}
.barra :deep(.p-toolbar-start) {
  gap: 0.5rem;
  font-size: 1.1rem;
}
.usuario {
  margin-right: 0.75rem;
  color: var(--p-text-muted-color);
}
.conteudo {
  max-width: 1100px;
  margin: 1.5rem auto;
  padding: 0 1rem;
}
</style>
