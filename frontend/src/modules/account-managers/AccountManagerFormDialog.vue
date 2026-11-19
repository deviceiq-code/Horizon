<script setup lang="ts">
/**
 * Create (manager = null) or edit an account manager: photo (cropped square in the browser,
 * shown in a circle; sent after the record is saved), first and last name, email and the
 * business verticals they work in.
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import PhotoField, { type PhotoChange } from '@/components/PhotoField.vue'
import { useValidationRules } from '@/composables/useValidationRules'
import VerticalPicker from '@/modules/catalogs/verticals/VerticalPicker.vue'
import { useNotificationsStore } from '@/stores/notifications'
import {
  accountManagerPhotoUrl,
  createAccountManager,
  deleteAccountManagerPhoto,
  updateAccountManager,
  uploadAccountManagerPhoto,
  type AccountManager,
  type AccountManagerInput,
} from './api'

const props = defineProps<{ manager: AccountManager | null }>()
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ saved: [manager: AccountManager, created: boolean] }>()

const { t } = useI18n()
const notifications = useNotificationsStore()
const rules = useValidationRules()

const FIELDS = ['first_name', 'last_name', 'email', 'verticals']

const form = ref<AccountManagerInput>({ first_name: '', last_name: '', email: '', verticals: [] })
const photo = ref<PhotoChange>(null)
const fieldErrors = ref<Record<string, string[]>>({})
const generalError = ref('')
const saving = ref(false)
const formRef = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(null)
const openCount = ref(0) // remounts the vertical picker on every open

const isEdit = computed(() => props.manager !== null)
const initialVerticals = computed(() => props.manager?.verticals_detail ?? [])
const currentPhoto = computed(() =>
  props.manager?.photo_version
    ? accountManagerPhotoUrl(props.manager.id, props.manager.photo_version)
    : null,
)
const nameForInitials = computed(() => `${form.value.first_name} ${form.value.last_name}`)

// Reset the form every time the dialog opens
watch(open, (isOpen) => {
  if (!isOpen) return
  form.value = {
    first_name: props.manager?.first_name ?? '',
    last_name: props.manager?.last_name ?? '',
    email: props.manager?.email ?? '',
    verticals: [...(props.manager?.verticals ?? [])],
  }
  photo.value = null
  fieldErrors.value = {}
  generalError.value = ''
  openCount.value += 1
})

/** Send the photo change after the record is saved (a failure keeps the record saved). */
async function applyPhoto(saved: AccountManager): Promise<AccountManager> {
  try {
    if (photo.value instanceof File) return await uploadAccountManagerPhoto(saved.id, photo.value)
    if (photo.value === 'remove' && saved.photo_version) {
      await deleteAccountManagerPhoto(saved.id)
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
  try {
    const data = {
      first_name: form.value.first_name.trim(),
      last_name: form.value.last_name.trim(),
      email: form.value.email.trim(),
      verticals: form.value.verticals,
    }
    let saved = props.manager
      ? await updateAccountManager(props.manager.id, data)
      : await createAccountManager(data)
    saved = await applyPhoto(saved)
    emit('saved', saved, !props.manager)
    open.value = false
  } catch (error) {
    const errors = error instanceof ApiError ? error.fieldErrors() : {}
    if (Object.keys(errors).some((k) => FIELDS.includes(k))) {
      fieldErrors.value = errors
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
    <v-card :title="isEdit ? $t('accountManagers.edit') : $t('accountManagers.new')">
      <v-form ref="formRef" @submit.prevent="submit">
        <v-card-text>
          <PhotoField
            v-model="photo"
            :name="nameForInitials"
            :current-url="currentPhoto"
            class="mb-4"
          />
          <v-row dense>
            <v-col cols="12" sm="6">
              <v-text-field
                v-model="form.first_name"
                :label="$t('accountManagers.fields.firstName')"
                :rules="[rules.required, rules.maxLength(100)]"
                :error-messages="fieldErrors.first_name"
                maxlength="100"
                autofocus
                data-testid="first-name"
                @update:model-value="fieldErrors.first_name = []"
              />
            </v-col>
            <v-col cols="12" sm="6">
              <v-text-field
                v-model="form.last_name"
                :label="$t('accountManagers.fields.lastName')"
                :rules="[rules.maxLength(100)]"
                :error-messages="fieldErrors.last_name"
                maxlength="100"
                data-testid="last-name"
                @update:model-value="fieldErrors.last_name = []"
              />
            </v-col>
          </v-row>
          <v-text-field
            v-model="form.email"
            :label="$t('accountManagers.fields.email')"
            type="email"
            :rules="[rules.required, rules.email, rules.maxLength(254)]"
            :error-messages="fieldErrors.email"
            maxlength="254"
            data-testid="email"
            @update:model-value="fieldErrors.email = []"
          />
          <VerticalPicker
            :key="openCount"
            v-model="form.verticals"
            multiple
            :initial-options="initialVerticals"
            :label="$t('accountManagers.fields.verticals')"
            :error-messages="fieldErrors.verticals"
            data-testid="verticals"
            @update:model-value="fieldErrors.verticals = []"
          />
          <v-alert v-if="generalError" type="error" variant="tonal" density="compact">
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
