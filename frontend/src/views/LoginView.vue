<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ApiError } from '@/api'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import HorizonLogo from '@/components/HorizonLogo.vue'
import LanguageSelector from '@/components/LanguageSelector.vue'
import { chooseEnvironment, ENVIRONMENT_ICONS, fetchEnvironments } from '@/environment'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const username = ref('')
const password = ref('')
const showPassword = ref(false)
const error = ref('')
/** error: wrong user or password; warning: an environment not given to the user */
const errorKind = ref<'error' | 'warning'>('error')
const loading = ref(false)

// Live or Development (Test): offered only when the server has more than one
const environments = ref<string[]>([])
const environment = ref('')

onMounted(async () => {
  try {
    const data = await fetchEnvironments()
    environments.value = data.environments
    environment.value = data.current
  } catch {
    environments.value = []
  }
})

function selectEnvironment(name: string | null) {
  if (!name) return
  environment.value = name
  chooseEnvironment(name)
}

async function login() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(username.value, password.value)
    const target = typeof route.query.next === 'string' ? route.query.next : '/'
    await router.push(target)
  } catch (failure) {
    // An environment not given to this user (the administrators were warned): the server says
    const denied =
      failure instanceof ApiError &&
      failure.status === 403 &&
      (failure.data as { code?: string } | null)?.code === 'environment_denied'
    errorKind.value = denied ? 'warning' : 'error'
    error.value = denied ? failure.message : t('login.invalidCredentials')
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
      <!-- The logo: the sun over the horizon, the name and the slogan -->
      <div class="d-flex justify-center pt-6 pb-2">
        <HorizonLogo :mark-height="80" />
      </div>

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

          <div v-if="environments.length > 1" class="mb-4" data-testid="environment">
            <div class="text-caption text-medium-emphasis mb-1">
              {{ $t('environments.label') }}
            </div>
            <v-btn-toggle
              :model-value="environment"
              mandatory
              divided
              variant="outlined"
              density="comfortable"
              class="w-100"
              :color="environment === 'live' ? 'primary' : 'warning'"
              @update:model-value="selectEnvironment"
            >
              <v-btn
                v-for="name in environments"
                :key="name"
                :value="name"
                :prepend-icon="ENVIRONMENT_ICONS[name]"
                class="flex-grow-1"
                :data-testid="`environment-${name}`"
              >
                {{ $t(`environments.${name}`) }}
              </v-btn>
            </v-btn-toggle>
          </div>

          <v-alert
            v-if="error"
            :type="errorKind"
            variant="tonal"
            density="compact"
            class="mb-4"
            data-testid="login-error"
          >
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
