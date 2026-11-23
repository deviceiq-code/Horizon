<script setup lang="ts">
/** Create (role = null) or edit a role created in the app (system roles are read-only). */
import FormDialog from '@/components/FormDialog.vue'
import KeywordsField from '@/components/KeywordsField.vue'
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

const form = ref({ name: '', description: '', keywords: [] as string[] })
const fieldErrors = ref<Record<string, string[]>>({})
const generalError = ref('')
const saving = ref(false)
const formRef = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(null)

const isEdit = computed(() => props.role !== null)

watch(open, (isOpen) => {
  if (!isOpen) return
  form.value = {
    name: props.role?.name ?? '',
    description: props.role?.description ?? '',
    keywords: [...(props.role?.keywords ?? [])],
  }
  fieldErrors.value = {}
  generalError.value = ''
})

async function submit() {
  const result = await formRef.value?.validate()
  if (!result?.valid) return
  saving.value = true
  fieldErrors.value = {}
  generalError.value = ''
  const data = {
    name: form.value.name.trim(),
    description: form.value.description.trim(),
    keywords: form.value.keywords,
  }
  try {
    const saved = props.role ? await updateRole(props.role.id, data) : await createRole(data)
    emit('saved', saved, !props.role)
    open.value = false
  } catch (error) {
    const errors = error instanceof ApiError ? error.fieldErrors() : {}
    if (errors.name || errors.description || errors.keywords) {
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
  <FormDialog
    ref="formRef"
    v-model="open"
    :title="isEdit ? $t('users.roles.edit') : $t('users.roles.new')"
    :subtitle="role?.name ?? null"
    icon="mdi-shield-account-outline"
    max-width="560"
    :persistent="saving"
    @submit="submit"
  >
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
    <KeywordsField
      v-model="form.keywords"
      :error-messages="fieldErrors.keywords"
      data-testid="keywords"
      @update:model-value="fieldErrors.keywords = []"
    />
    <v-alert v-if="generalError" type="error" variant="tonal" density="compact">
      {{ generalError }}
    </v-alert>

    <template #actions>
      <v-btn variant="text" :disabled="saving" @click="open = false">
        {{ $t('common.cancel') }}
      </v-btn>
      <v-btn type="submit" color="primary" variant="flat" :loading="saving" data-testid="save">
        {{ $t('common.save') }}
      </v-btn>
    </template>
  </FormDialog>
</template>
