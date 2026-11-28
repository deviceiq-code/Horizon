<script setup lang="ts">
import FormDialog from '@/components/FormDialog.vue'
import WebSearchButton from '@/components/WebSearchButton.vue'
import KeywordsField from '@/components/KeywordsField.vue'
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import { useValidationRules } from '@/composables/useValidationRules'
import EntityPicker from '@/modules/business-entities/EntityPicker.vue'
import RemarketingEditor from '../remarketing/RemarketingEditor.vue'
import {
  createManufacturer,
  MANUFACTURER_RATINGS,
  updateManufacturer,
  type Manufacturer,
  type ManufacturerInput,
} from './api'

/** Create (manufacturer = null) or edit a manufacturer (a brand), the business entity behind
 * it (optional) and its remarketing rating. */
const props = defineProps<{ manufacturer: Manufacturer | null }>()
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ saved: [manufacturer: Manufacturer, created: boolean] }>()

const { t } = useI18n()
const rules = useValidationRules()

const FIELDS = ['name', 'business_entity', ...MANUFACTURER_RATINGS, 'is_enabled', 'keywords']

function emptyForm(): ManufacturerInput {
  return {
    name: '',
    business_entity: null,
    reputation: '0.0',
    product_quality: '0.0',
    after_sales: '0.0',
    is_enabled: true,
    keywords: [],
  }
}

const form = ref<ManufacturerInput>(emptyForm())
const fieldErrors = ref<Record<string, string[]>>({})
const generalError = ref('')
const saving = ref(false)
const formRef = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(null)

const isEdit = computed(() => props.manufacturer !== null)
const openCount = ref(0) // remounts the entity picker on every open

watch(open, (isOpen) => {
  if (!isOpen) return
  const m = props.manufacturer
  form.value = m
    ? {
        name: m.name,
        business_entity: m.business_entity,
        reputation: m.reputation,
        product_quality: m.product_quality,
        after_sales: m.after_sales,
        is_enabled: m.is_enabled,
        keywords: [...m.keywords],
      }
    : emptyForm()
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
  <FormDialog
    :audit="manufacturer"
    ref="formRef"
    v-model="open"
    :title="isEdit ? $t('manufacturers.edit') : $t('manufacturers.new')"
    :subtitle="manufacturer?.name ?? null"
    icon="mdi-factory"
    max-width="680"
    :persistent="saving"
    @submit="submit"
  >
    <v-text-field
      v-model="form.name"
      :label="$t('manufacturers.fields.name')"
      :rules="[rules.required, rules.maxLength(100)]"
      :error-messages="fieldErrors.name"
      maxlength="100"
      autofocus
      data-testid="name"
      @update:model-value="clearError('name')"
    >
      <template #append-inner><WebSearchButton :term="form.name" /></template>
    </v-text-field>
    <!-- The business entity behind the brand (e.g. Dell → Dell Computadores do Brasil Ltda) -->
    <EntityPicker
      :key="`entity-${openCount}`"
      v-model="form.business_entity"
      :label="$t('manufacturers.fields.businessEntity')"
      :initial-option="manufacturer?.business_entity_detail ?? null"
      :error-messages="fieldErrors.business_entity"
      class="mb-1"
      data-testid="business-entity"
      @update:model-value="clearError('business_entity')"
    />
    <div class="text-caption text-medium-emphasis mb-4">
      {{ $t('manufacturers.businessEntityHint') }}
    </div>

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

    <KeywordsField
      v-model="form.keywords"
      :error-messages="fieldErrors.keywords"
      data-testid="keywords"
      @update:model-value="clearError('keywords')"
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
