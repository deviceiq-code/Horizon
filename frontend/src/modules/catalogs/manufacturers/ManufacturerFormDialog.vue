<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import { useValidationRules } from '@/composables/useValidationRules'
import RemarketingEditor from '../remarketing/RemarketingEditor.vue'
import {
  createManufacturer,
  MANUFACTURER_RATINGS,
  updateManufacturer,
  type Manufacturer,
  type ManufacturerInput,
} from './api'

/** Create (manufacturer = null) or edit a manufacturer and its remarketing rating. */
const props = defineProps<{ manufacturer: Manufacturer | null }>()
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ saved: [manufacturer: Manufacturer, created: boolean] }>()

const { t } = useI18n()
const rules = useValidationRules()

const FIELDS = ['name', ...MANUFACTURER_RATINGS, 'is_enabled']

function emptyForm(): ManufacturerInput {
  return {
    name: '',
    reputation: '0.0',
    product_quality: '0.0',
    after_sales: '0.0',
    is_enabled: true,
  }
}

const form = ref<ManufacturerInput>(emptyForm())
const fieldErrors = ref<Record<string, string[]>>({})
const generalError = ref('')
const saving = ref(false)
const formRef = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(null)

const isEdit = computed(() => props.manufacturer !== null)

watch(open, (isOpen) => {
  if (!isOpen) return
  const m = props.manufacturer
  form.value = m
    ? {
        name: m.name,
        reputation: m.reputation,
        product_quality: m.product_quality,
        after_sales: m.after_sales,
        is_enabled: m.is_enabled,
      }
    : emptyForm()
  fieldErrors.value = {}
  generalError.value = ''
})

async function submit() {
  const result = await formRef.value?.validate()
  if (!result?.valid) return

  saving.value = true
  fieldErrors.value = {}
  generalError.value = ''
  try {
    const data = { ...form.value, name: form.value.name.trim() }
    const saved = props.manufacturer
      ? await updateManufacturer(props.manufacturer.id, data)
      : await createManufacturer(data)
    emit('saved', saved, !props.manufacturer)
    open.value = false
  } catch (error) {
    const errors = error instanceof ApiError ? error.fieldErrors() : {}
    if (Object.keys(errors).some((k) => FIELDS.includes(k))) fieldErrors.value = errors
    else generalError.value = t('common.saveError')
  } finally {
    saving.value = false
  }
}

function clearError(field: string) {
  if (fieldErrors.value[field]) fieldErrors.value[field] = []
}
</script>

<template>
  <v-dialog v-model="open" max-width="680" scrollable :persistent="saving">
    <v-card :title="isEdit ? $t('manufacturers.edit') : $t('manufacturers.new')">
      <v-form
        ref="formRef"
        class="d-flex flex-column"
        style="min-height: 0"
        @submit.prevent="submit"
      >
        <v-card-text>
          <v-text-field
            v-model="form.name"
            :label="$t('manufacturers.fields.name')"
            :rules="[rules.required, rules.maxLength(100)]"
            :error-messages="fieldErrors.name"
            maxlength="100"
            autofocus
            data-testid="name"
            @update:model-value="clearError('name')"
          />

          <div class="text-subtitle-1">{{ $t('manufacturers.remarketing.title') }}</div>
          <p class="text-body-2 text-medium-emphasis mb-3">
            {{ $t('manufacturers.remarketing.subtitle') }}
          </p>
          <RemarketingEditor
            :ratings="form"
            :fields="MANUFACTURER_RATINGS"
            i18n-prefix="manufacturers.remarketing"
            :errors="fieldErrors"
            class="mb-4"
            @edited="clearError"
          />

          <v-switch
            v-model="form.is_enabled"
            :label="$t('catalogs.fields.enabled')"
            color="primary"
            inset
            hide-details
            data-testid="enabled"
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
