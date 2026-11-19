<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import { useValidationRules } from '@/composables/useValidationRules'
import VerticalPicker from '@/modules/catalogs/verticals/VerticalPicker.vue'
import { useNotificationsStore } from '@/stores/notifications'
import { squareImage } from '@/utils/image'
import AccountManagerAvatar from './AccountManagerAvatar.vue'
import {
  createAccountManager,
  deleteAccountManagerPhoto,
  updateAccountManager,
  uploadAccountManagerPhoto,
  type AccountManager,
  type AccountManagerInput,
} from './api'

/**
 * Create (manager = null) or edit an account manager, the verticals they work in and their
 * photo (cropped square in the browser, shown in a circle; sent after the record is saved).
 */
const props = defineProps<{ manager: AccountManager | null }>()
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ saved: [manager: AccountManager, created: boolean] }>()

const { t } = useI18n()
const notifications = useNotificationsStore()

const FIELDS = ['full_name', 'email', 'verticals']

const form = ref<AccountManagerInput>({ full_name: '', email: '', verticals: [] })
const fieldErrors = ref<Record<string, string[]>>({})
const generalError = ref('')
const saving = ref(false)
const formRef = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(null)
const openCount = ref(0) // remounts the vertical picker on every open

// --- Photo (applied when saving) -------------------------------------------------------------

const photoInput = ref<HTMLInputElement | null>(null)
const pendingPhoto = ref<File | null>(null)
const previewUrl = ref<string | null>(null)
const removePhoto = ref(false)
const preparingPhoto = ref(false)

function setPreview(file: File | null) {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = file ? URL.createObjectURL(file) : null
}

async function choosePhoto(files: FileList | null) {
  const file = files?.[0]
  if (photoInput.value) photoInput.value.value = ''
  if (!file) return
  if (!file.type.startsWith('image/')) {
    notifications.notify(t('accountManagers.photo.notImage'), 'error')
    return
  }
  preparingPhoto.value = true
  try {
    pendingPhoto.value = await squareImage(file)
    removePhoto.value = false
    setPreview(pendingPhoto.value)
  } catch {
    notifications.notify(t('accountManagers.photo.notImage'), 'error')
  } finally {
    preparingPhoto.value = false
  }
}

function clearPhoto() {
  pendingPhoto.value = null
  setPreview(null)
  removePhoto.value = !!props.manager?.photo_version
}

const hasPhoto = computed(
  () => !!pendingPhoto.value || (!!props.manager?.photo_version && !removePhoto.value),
)

onBeforeUnmount(() => setPreview(null))

const isEdit = computed(() => props.manager !== null)
const initialVerticals = computed(() => props.manager?.verticals_detail ?? [])

const rules = useValidationRules()

// Reset the form every time the dialog opens
watch(open, (isOpen) => {
  if (!isOpen) return
  form.value = {
    full_name: props.manager?.full_name ?? '',
    email: props.manager?.email ?? '',
    verticals: [...(props.manager?.verticals ?? [])],
  }
  fieldErrors.value = {}
  generalError.value = ''
  openCount.value += 1
  pendingPhoto.value = null
  removePhoto.value = false
  setPreview(null)
})

/** Send the photo change after the record is saved (a failure keeps the record saved). */
async function applyPhoto(saved: AccountManager): Promise<AccountManager> {
  try {
    if (pendingPhoto.value) return await uploadAccountManagerPhoto(saved.id, pendingPhoto.value)
    if (removePhoto.value && saved.photo_version) {
      await deleteAccountManagerPhoto(saved.id)
      return { ...saved, photo_version: null }
    }
  } catch (error) {
    const messages = error instanceof ApiError ? error.fieldErrors().file : undefined
    notifications.notify(messages?.join(' ') || t('accountManagers.photo.saveError'), 'error')
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
      full_name: form.value.full_name.trim(),
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
  <v-dialog v-model="open" max-width="600" :persistent="saving">
    <v-card :title="isEdit ? $t('accountManagers.edit') : $t('accountManagers.new')">
      <v-form ref="formRef" @submit.prevent="submit">
        <v-card-text>
          <div class="d-flex align-center ga-4 mb-4" data-testid="photo">
            <AccountManagerAvatar
              :name="form.full_name || '?'"
              :id="manager?.id ?? null"
              :photo-version="removePhoto ? null : (manager?.photo_version ?? null)"
              :preview-url="previewUrl"
              :size="96"
            />
            <div class="d-flex flex-column ga-1">
              <v-btn
                variant="tonal"
                size="small"
                prepend-icon="mdi-camera-outline"
                :loading="preparingPhoto"
                data-testid="photo-choose"
                @click="photoInput?.click()"
              >
                {{ $t(hasPhoto ? 'accountManagers.photo.change' : 'accountManagers.photo.add') }}
              </v-btn>
              <v-btn
                v-if="hasPhoto"
                variant="text"
                size="small"
                color="error"
                prepend-icon="mdi-trash-can-outline"
                data-testid="photo-remove"
                @click="clearPhoto"
              >
                {{ $t('accountManagers.photo.remove') }}
              </v-btn>
              <input
                ref="photoInput"
                type="file"
                accept="image/jpeg,image/png,image/webp,image/gif"
                hidden
                data-testid="photo-input"
                @change="choosePhoto(($event.target as HTMLInputElement).files)"
              />
            </div>
          </div>
          <v-text-field
            v-model="form.full_name"
            :label="$t('accountManagers.fields.fullName')"
            :rules="[rules.required, rules.maxLength(150)]"
            :error-messages="fieldErrors.full_name"
            maxlength="150"
            autofocus
            data-testid="full-name"
            @update:model-value="fieldErrors.full_name = []"
          />
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
