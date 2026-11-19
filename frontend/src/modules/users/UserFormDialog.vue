<script setup lang="ts">
/**
 * Create (user = null) or edit a user: photo (cropped square in the browser, shown in a circle;
 * sent after saving), login, name, email, roles, active, password (required when creating;
 * when editing, empty keeps the current one). The server checks the password
 * rules and refuses locking yourself out (409, shown here).
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import PhotoField, { type PhotoChange } from '@/components/PhotoField.vue'
import { useValidationRules } from '@/composables/useValidationRules'
import { useAuthStore } from '@/stores/auth'
import { useNotificationsStore } from '@/stores/notifications'
import {
  allRoles,
  createUser,
  deleteUserPhoto,
  updateUser,
  uploadUserPhoto,
  userPhotoUrl,
  type Role,
  type User,
  type UserInput,
} from './api'
import { roleName } from './roleText'

const props = defineProps<{ user: User | null }>()
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ saved: [user: User, created: boolean] }>()

const { t } = useI18n()
const rules = useValidationRules()
const auth = useAuthStore()
const notifications = useNotificationsStore()

const FIELDS = ['username', 'first_name', 'last_name', 'email', 'roles', 'password', 'is_active']

const form = ref({
  username: '',
  first_name: '',
  last_name: '',
  email: '',
  is_active: true,
  roles: [] as number[],
  password: '',
  confirm: '',
})
const photo = ref<PhotoChange>(null)
const roles = ref<Role[]>([])
const fieldErrors = ref<Record<string, string[]>>({})
const generalError = ref('')
const saving = ref(false)
const showPassword = ref(false)
const formRef = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(null)

const isEdit = computed(() => props.user !== null)
const isMe = computed(() => props.user !== null && props.user.id === auth.user?.id)
const currentPhoto = computed(() =>
  props.user?.photo_version ? userPhotoUrl(props.user.id, props.user.photo_version) : null,
)
const nameForInitials = computed(
  () => `${form.value.first_name} ${form.value.last_name}`.trim() || form.value.username,
)
const roleItems = computed(() => roles.value.map((r) => ({ value: r.id, title: roleName(r, t) })))

watch(open, async (isOpen) => {
  if (!isOpen) return
  const user = props.user
  form.value = {
    username: user?.username ?? '',
    first_name: user?.first_name ?? '',
    last_name: user?.last_name ?? '',
    email: user?.email ?? '',
    is_active: user?.is_active ?? true,
    roles: [...(user?.roles ?? [])],
    password: '',
    confirm: '',
  }
  photo.value = null
  fieldErrors.value = {}
  generalError.value = ''
  showPassword.value = false
  try {
    roles.value = await allRoles()
  } catch {
    generalError.value = t('common.loadError')
  }
})

const passwordRules = computed(() => [
  (v: string) => isEdit.value || !!v || t('validation.required'),
])
const confirmRules = computed(() => [
  (v: string) => v === form.value.password || t('users.passwordMismatch'),
])

/** Send the photo change after the user is saved (a failure keeps the user saved). */
async function applyPhoto(saved: User): Promise<User> {
  try {
    if (photo.value instanceof File) return await uploadUserPhoto(saved.id, photo.value)
    if (photo.value === 'remove' && saved.photo_version) {
      await deleteUserPhoto(saved.id)
      return { ...saved, photo_version: null }
    }
  } catch (error) {
    const messages = error instanceof ApiError ? error.fieldErrors().file : undefined
    notifications.notify(messages?.join(' ') || t('photo.saveError'), 'error')
  }
  return saved
}

async function submit() {
  const result = await formRef.value?.validate()
  if (!result?.valid) return

  saving.value = true
  fieldErrors.value = {}
  generalError.value = ''
  const data: UserInput = {
    username: form.value.username.trim(),
    first_name: form.value.first_name.trim(),
    last_name: form.value.last_name.trim(),
    email: form.value.email.trim(),
    is_active: form.value.is_active,
    roles: form.value.roles,
  }
  if (form.value.password) data.password = form.value.password
  try {
    let saved = props.user ? await updateUser(props.user.id, data) : await createUser(data)
    saved = await applyPhoto(saved)
    // Your own photo or name changed: the top bar follows
    if (saved.id === auth.user?.id) await auth.refresh()
    emit('saved', saved, !props.user)
    open.value = false
  } catch (error) {
    const errors = error instanceof ApiError ? error.fieldErrors() : {}
    if (Object.keys(errors).some((k) => FIELDS.includes(k))) {
      fieldErrors.value = errors
    } else if (error instanceof ApiError && error.status === 409 && error.message) {
      generalError.value = error.message
    } else {
      generalError.value = t('common.saveError')
    }
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <v-dialog v-model="open" max-width="640" :persistent="saving">
    <v-card :title="isEdit ? $t('users.edit') : $t('users.new')">
      <v-form ref="formRef" @submit.prevent="submit">
        <v-card-text>
          <PhotoField
            v-model="photo"
            :name="nameForInitials"
            :current-url="currentPhoto"
            class="mb-4"
          />
          <v-text-field
            v-model="form.username"
            :label="$t('users.fields.username')"
            :rules="[rules.required, rules.maxLength(150)]"
            :error-messages="fieldErrors.username"
            maxlength="150"
            autocomplete="off"
            data-testid="username"
            @update:model-value="fieldErrors.username = []"
          />
          <v-row dense>
            <v-col cols="12" sm="6">
              <v-text-field
                v-model="form.first_name"
                :label="$t('users.fields.firstName')"
                :rules="[rules.maxLength(150)]"
                :error-messages="fieldErrors.first_name"
                maxlength="150"
                data-testid="first-name"
              />
            </v-col>
            <v-col cols="12" sm="6">
              <v-text-field
                v-model="form.last_name"
                :label="$t('users.fields.lastName')"
                :rules="[rules.maxLength(150)]"
                :error-messages="fieldErrors.last_name"
                maxlength="150"
                data-testid="last-name"
              />
            </v-col>
          </v-row>
          <v-text-field
            v-model="form.email"
            :label="$t('users.fields.email')"
            type="email"
            :rules="[rules.email]"
            :error-messages="fieldErrors.email"
            data-testid="email"
            @update:model-value="fieldErrors.email = []"
          />
          <v-select
            v-model="form.roles"
            :items="roleItems"
            :label="$t('users.fields.roles')"
            :error-messages="fieldErrors.roles"
            multiple
            chips
            closable-chips
            data-testid="roles"
          />
          <v-switch
            v-model="form.is_active"
            :label="$t(form.is_active ? 'users.status.active' : 'users.status.inactive')"
            :hint="$t('users.activeHint')"
            :disabled="isMe"
            persistent-hint
            color="primary"
            inset
            class="mb-2"
            data-testid="is-active"
          />

          <div class="text-subtitle-2 mt-2">{{ $t('users.fields.password') }}</div>
          <p v-if="isEdit" class="text-caption text-medium-emphasis mb-2">
            {{ $t('users.passwordKeep') }}
          </p>
          <v-row dense>
            <v-col cols="12" sm="6">
              <v-text-field
                v-model="form.password"
                :label="$t(isEdit ? 'users.fields.newPassword' : 'users.fields.password')"
                :type="showPassword ? 'text' : 'password'"
                :append-inner-icon="showPassword ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
                :rules="passwordRules"
                :error-messages="fieldErrors.password"
                autocomplete="new-password"
                data-testid="password"
                @click:append-inner="showPassword = !showPassword"
                @update:model-value="fieldErrors.password = []"
              />
            </v-col>
            <v-col cols="12" sm="6">
              <v-text-field
                v-model="form.confirm"
                :label="$t('users.fields.passwordConfirm')"
                :type="showPassword ? 'text' : 'password'"
                :rules="confirmRules"
                autocomplete="new-password"
                data-testid="password-confirm"
              />
            </v-col>
          </v-row>

          <v-alert
            v-if="generalError"
            type="error"
            variant="tonal"
            density="compact"
            data-testid="general-error"
          >
            {{ generalError }}
          </v-alert>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" :disabled="saving" @click="open = false">
            {{ $t('common.cancel') }}
          </v-btn>
          <v-btn type="submit" color="primary" variant="flat" :loading="saving" data-testid="save">
            {{ $t('common.save') }}
          </v-btn>
        </v-card-actions>
      </v-form>
    </v-card>
  </v-dialog>
</template>
