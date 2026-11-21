<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import LanguageSelector from '@/components/LanguageSelector.vue'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const username = ref('')
const password = ref('')
const showPassword = ref(false)
const error = ref('')
const loading = ref(false)

async function login() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(username.value, password.value)
    const target = typeof route.query.next === 'string' ? route.query.next : '/'
    await router.push(target)
  } catch {
    error.value = t('login.invalidCredentials')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <v-main class="d-flex align-center justify-center pa-4">
    <div class="position-absolute top-0 right-0 pa-2">
      <LanguageSelector />
    </div>

    <v-card width="400" max-width="100%" elevation="4" class="pa-2">
      <v-card-item>
        <template #prepend>
          <!-- The brand's mark, as in the side menu -->
          <v-avatar color="primary" rounded="lg" size="40" class="font-weight-bold">H</v-avatar>
        </template>
        <v-card-title class="text-h5 font-weight-bold">{{ $t('app.name') }}</v-card-title>
        <v-card-subtitle>{{ $t('app.description') }}</v-card-subtitle>
      </v-card-item>

      <v-card-text>
        <v-form @submit.prevent="login">
          <v-text-field
            v-model="username"
            :label="$t('login.username')"
            prepend-inner-icon="mdi-account"
            autocomplete="username"
            autofocus
          />
          <v-text-field
            v-model="password"
            :label="$t('login.password')"
            prepend-inner-icon="mdi-lock"
            :type="showPassword ? 'text' : 'password'"
            :append-inner-icon="showPassword ? 'mdi-eye-off' : 'mdi-eye'"
            autocomplete="current-password"
            @click:append-inner="showPassword = !showPassword"
          />

          <v-alert v-if="error" type="error" variant="tonal" density="compact" class="mb-4">
            {{ error }}
          </v-alert>

          <v-btn
            type="submit"
            color="primary"
            size="large"
            block
            prepend-icon="mdi-login"
            :loading="loading"
          >
            {{ $t('login.submit') }}
          </v-btn>
        </v-form>
      </v-card-text>
    </v-card>
  </v-main>
</template>
