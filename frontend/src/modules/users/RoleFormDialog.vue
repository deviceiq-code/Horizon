<script setup lang="ts">
/** Create (role = null) or edit a role created in the app (system roles are read-only). */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import { useValidationRules } from '@/composables/useValidationRules'
import { createRole, updateRole, type Role } from './api'

const props = defineProps<{ role: Role | null }>()
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ saved: [role: Role, created: boolean] }>()

const { t } = useI18n()
const rules = useValidationRules()

const form = ref({ name: '', description: '' })
const fieldErrors = ref<Record<string, string[]>>({})
const generalError = ref('')
const saving = ref(false)
const formRef = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(null)

const isEdit = computed(() => props.role !== null)

watch(open, (isOpen) => {
  if (!isOpen) return
  form.value = { name: props.role?.name ?? '', description: props.role?.description ?? '' }
  fieldErrors.value = {}
  generalError.value = ''
})

async function submit() {
  const result = await formRef.value?.validate()
  if (!result?.valid) return
  saving.value = true
  fieldErrors.value = {}
  generalError.value = ''
  const data = { name: form.value.name.trim(), description: form.value.description.trim() }
  try {
    const saved = props.role ? await updateRole(props.role.id, data) : await createRole(data)
    emit('saved', saved, !props.role)
    open.value = false
  } catch (error) {
    const errors = error instanceof ApiError ? error.fieldErrors() : {}
    if (errors.name || errors.description) {
      fieldErrors.value = errors
    } else {
      generalError.value =
        errors.non_field_errors?.join(' ') ||
        (error instanceof ApiError && error.status === 409 && error.message) ||
        t('common.saveError')
    }
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <v-dialog v-model="open" max-width="560" :persistent="saving">
    <v-card :title="isEdit ? $t('users.roles.edit') : $t('users.roles.new')">
      <v-form ref="formRef" @submit.prevent="submit">
        <v-card-text>
          <v-text-field
            v-model="form.name"
            :label="$t('users.roles.fields.name')"
            :rules="[rules.required, rules.maxLength(80)]"
            :error-messages="fieldErrors.name"
            maxlength="80"
            autofocus
            data-testid="role-name"
            @update:model-value="fieldErrors.name = []"
          />
          <v-textarea
            v-model="form.description"
            :label="$t('users.roles.fields.description')"
            :error-messages="fieldErrors.description"
            rows="3"
            auto-grow
            data-testid="role-description"
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
