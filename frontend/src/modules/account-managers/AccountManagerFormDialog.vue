<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import { useValidationRules } from '@/composables/useValidationRules'
import VerticalPicker from '@/modules/catalogs/verticals/VerticalPicker.vue'
import {
  createAccountManager,
  updateAccountManager,
  type AccountManager,
  type AccountManagerInput,
} from './api'

/** Create (manager = null) or edit an account manager and the verticals they work in. */
const props = defineProps<{ manager: AccountManager | null }>()
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ saved: [manager: AccountManager, created: boolean] }>()

const { t } = useI18n()

const FIELDS = ['full_name', 'email', 'verticals']

const form = ref<AccountManagerInput>({ full_name: '', email: '', verticals: [] })
const fieldErrors = ref<Record<string, string[]>>({})
const generalError = ref('')
const saving = ref(false)
const formRef = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(null)
const openCount = ref(0) // remounts the vertical picker on every open

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
})

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
    const saved = props.manager
      ? await updateAccountManager(props.manager.id, data)
      : await createAccountManager(data)
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
