<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Button from 'primevue/button'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import Password from 'primevue/password'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const username = ref('')
const password = ref('')
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
  <main class="login">
    <Card class="cartao">
      <template #title>Sistema Horizon</template>
      <template #subtitle>Precificação de residuais de leasing operacional</template>
      <template #content>
        <form class="formulario" @submit.prevent="entrar">
          <label for="usuario">Usuário</label>
          <InputText id="usuario" v-model="username" autocomplete="username" autofocus fluid />

          <label for="senha">Senha</label>
          <Password
            v-model="password"
            input-id="senha"
            :feedback="false"
            :input-props="{ autocomplete: 'current-password' }"
            toggle-mask
            fluid
          />

          <Message v-if="erro" severity="error" size="small" variant="simple">{{ erro }}</Message>

          <Button type="submit" label="Entrar" icon="pi pi-sign-in" :loading="carregando" fluid />
        </form>
      </template>
    </Card>
  </main>
</template>

<style scoped>
.login {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 1rem;
}
.cartao {
  width: 100%;
  max-width: 400px;
}
.formulario {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}
.formulario button {
  margin-top: 0.8rem;
}
</style>
