<script setup lang="ts">
/**
 * Create (assetModel = null) or edit an asset model: manufacturer, model, asset class and the
 * class's specification values (defaults for its units — none required here), how the
 * inventory controls it, the serial number pattern, the kit checklist and the test script.
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import FormDialog from '@/components/FormDialog.vue'
import KeywordsField from '@/components/KeywordsField.vue'
import ListItemsField from '@/components/ListItemsField.vue'
import KitChecklistField from './KitChecklistField.vue'
import { useValidationRules } from '@/composables/useValidationRules'
import SpecValuesInput from '@/modules/average-prices/SpecValuesInput.vue'
import AssetClassPicker from '@/modules/catalogs/asset-classes/AssetClassPicker.vue'
import { getAssetClass, type AssetClass } from '@/modules/catalogs/asset-classes/api'
import ManufacturerPicker from '@/modules/catalogs/manufacturers/ManufacturerPicker.vue'
import { parseMoney, toInputNumber } from '@/utils/money'
import {
  createAssetModel,
  updateAssetModel,
  type AssetModel,
  type AssetModelInput,
  type Tracking,
} from './api'

const props = defineProps<{ assetModel: AssetModel | null }>()
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ saved: [assetModel: AssetModel, created: boolean] }>()

const { t, locale } = useI18n()
const rules = useValidationRules()

const FIELDS = [
  'manufacturer',
  'name',
  'asset_class',
  'specs',
  'tracking',
  'serial_regex',
  'kit_checklist',
  'test_script',
  'has_storage',
  'keywords',
  'notes',
  'is_enabled',
]

interface Form extends Omit<AssetModelInput, 'specs'> {
  manufacturer: number | null
  asset_class: number | null
}

function emptyForm(): Form {
  return {
    manufacturer: null,
    name: '',
    asset_class: null,
    tracking: 'unit',
    serial_regex: '',
    kit_checklist: [],
    test_script: [],
    has_storage: false,
    keywords: [],
    notes: '',
    is_enabled: true,
  }
}

const form = ref<Form>(emptyForm())
const specs = ref<Record<string, string>>({})
const assetClass = ref<AssetClass | null>(null)
const fieldErrors = ref<Record<string, string[]>>({})
const specErrors = ref<Record<string, string[]>>({})
const generalError = ref('')
const saving = ref(false)
const formRef = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(null)
const openCount = ref(0)
// The class picker remounts once the edited model's class is loaded (to show it)
const classLoaded = ref(false)

const isEdit = computed(() => props.assetModel !== null)
/** The model's values are defaults: no field is required here */
const template = computed(() =>
  (assetClass.value?.spec_template ?? []).map((field) => ({ ...field, required: false })),
)
const initialManufacturer = computed(() =>
  props.assetModel
    ? { id: props.assetModel.manufacturer, name: props.assetModel.manufacturer_name }
    : null,
)
const trackingOptions = computed(() => [
  { value: 'unit' as Tracking, title: t('assetModels.tracking.unit') },
  { value: 'quantity' as Tracking, title: t('assetModels.tracking.quantity') },
])
const requiredRule = [(v: unknown) => (v !== null && v !== undefined) || t('validation.required')]

watch(open, async (isOpen) => {
  if (!isOpen) return
  const m = props.assetModel
  form.value = m
    ? {
        manufacturer: m.manufacturer,
        name: m.name,
        asset_class: m.asset_class,
        tracking: m.tracking,
        serial_regex: m.serial_regex,
        kit_checklist: m.kit_checklist.map((entry) => ({ ...entry })),
        test_script: [...m.test_script],
        has_storage: m.has_storage,
        keywords: [...m.keywords],
        notes: m.notes,
        is_enabled: m.is_enabled,
      }
    : emptyForm()
  specs.value = Object.fromEntries(
    (m?.spec_values ?? []).map((spec) => [
      spec.key,
      spec.kind === 'number' && spec.value
        ? toInputNumber(spec.value, locale.value, 0, 6)
        : spec.value,
    ]),
  )
  fieldErrors.value = {}
  specErrors.value = {}
  generalError.value = ''
  assetClass.value = null
  classLoaded.value = false
  openCount.value += 1
  if (m) {
    try {
      assetClass.value = await getAssetClass(m.asset_class)
      classLoaded.value = true
    } catch {
      generalError.value = t('common.loadError')
    }
  }
})

/** Another class: keep only the values of fields it also has. */
function onAssetClass(chosen: AssetClass | null) {
  clearError('asset_class')
  assetClass.value = chosen
  const keys = new Set((chosen?.spec_template ?? []).map((field) => field.key))
  specs.value = Object.fromEntries(Object.entries(specs.value).filter(([key]) => keys.has(key)))
}

function canonicalSpecs(): Record<string, string> {
  return Object.fromEntries(
    template.value.map((field) => {
      const text = specs.value[field.key] ?? ''
      const value =
        field.kind === 'number' && text.trim() ? (parseMoney(text, locale.value, 6) ?? text) : text
      return [field.key, value]
    }),
  )
}

async function submit() {
  const result = await formRef.value?.validate()
  if (!result?.valid) return
  saving.value = true
  fieldErrors.value = {}
  specErrors.value = {}
  generalError.value = ''
  try {
    const data: AssetModelInput = { ...form.value, specs: canonicalSpecs() }
    const saved = props.assetModel
      ? await updateAssetModel(props.assetModel.id, data)
      : await createAssetModel(data)
    emit('saved', saved, !props.assetModel)
    open.value = false
  } catch (error) {
    const body = error instanceof ApiError ? error.fieldErrors() : {}
    const { specs: specErr, ...rest } = body as Record<string, unknown>
    specErrors.value = (specErr as Record<string, string[]>) ?? {}
    const known = Object.keys(rest).filter((key) => FIELDS.includes(key))
    if (known.length) fieldErrors.value = rest as Record<string, string[]>
    if (!known.length && !specErr) generalError.value = t('common.saveError')
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
    ref="formRef"
    v-model="open"
    :title="isEdit ? $t('assetModels.edit') : $t('assetModels.new')"
    :subtitle="assetModel ? `${assetModel.manufacturer_name} ${assetModel.name}` : null"
    icon="mdi-shape-plus-outline"
    max-width="880"
    :persistent="saving"
    @submit="submit"
  >
    <div class="text-subtitle-2 text-medium-emphasis mb-2">
      {{ $t('assetModels.sections.identification') }}
    </div>
    <v-row dense>
      <v-col cols="12" md="5">
        <ManufacturerPicker
          :key="`manufacturer-${openCount}`"
          v-model="form.manufacturer"
          :label="$t('assetModels.fields.manufacturer')"
          :initial-option="initialManufacturer"
          :rules="requiredRule"
          :error-messages="fieldErrors.manufacturer"
          data-testid="manufacturer"
          @update:model-value="clearError('manufacturer')"
        />
      </v-col>
      <v-col cols="12" md="7">
        <v-text-field
          v-model="form.name"
          :label="$t('assetModels.fields.name')"
          :rules="[rules.required, rules.maxLength(150)]"
          :error-messages="fieldErrors.name"
          maxlength="150"
          data-testid="name"
          @update:model-value="clearError('name')"
        />
      </v-col>
      <v-col cols="12">
        <AssetClassPicker
          :key="`class-${openCount}-${classLoaded}`"
          v-model="form.asset_class"
          :label="$t('assetModels.fields.assetClass')"
          :initial-option="assetClass"
          :rules="requiredRule"
          :error-messages="fieldErrors.asset_class"
          data-testid="asset-class"
          @selected="onAssetClass"
        />
      </v-col>
    </v-row>

    <div class="text-subtitle-2 text-medium-emphasis mb-1 mt-2">
      {{ $t('assetModels.sections.specs') }}
    </div>
    <p class="text-caption text-medium-emphasis mb-2">{{ $t('assetModels.specsHint') }}</p>
    <SpecValuesInput
      v-if="template.length"
      v-model="specs"
      :template="template"
      :asset-class-id="form.asset_class"
      :errors="specErrors"
    />
    <p v-else class="text-body-2 text-medium-emphasis mb-2" data-testid="no-template">
      {{ form.asset_class ? $t('assetModels.noTemplate') : $t('assetModels.chooseClass') }}
    </p>

    <div class="text-subtitle-2 text-medium-emphasis mb-2 mt-4">
      {{ $t('assetModels.sections.inventory') }}
    </div>
    <v-row dense>
      <v-col cols="12" md="4">
        <v-select
          v-model="form.tracking"
          :items="trackingOptions"
          :label="$t('assetModels.fields.tracking')"
          :hint="$t('assetModels.trackingHint')"
          persistent-hint
          :error-messages="fieldErrors.tracking"
          data-testid="tracking"
        />
      </v-col>
      <v-col cols="12" md="5">
        <v-text-field
          v-model="form.serial_regex"
          :label="$t('assetModels.fields.serialRegex')"
          :hint="$t('assetModels.serialRegexHint')"
          persistent-hint
          :error-messages="fieldErrors.serial_regex"
          maxlength="200"
          class="font-monospace"
          data-testid="serial-regex"
          @update:model-value="clearError('serial_regex')"
        />
      </v-col>
      <v-col cols="12" md="3" class="d-flex align-center">
        <v-switch
          v-model="form.has_storage"
          :label="$t('assetModels.fields.hasStorage')"
          color="primary"
          hide-details
          inset
          data-testid="has-storage"
        />
      </v-col>
      <v-col cols="12" md="6">
        <KitChecklistField
          v-model="form.kit_checklist"
          :label="$t('assetModels.fields.kitChecklist')"
          :hint="$t('assetModels.kitChecklistHint')"
          :error-messages="fieldErrors.kit_checklist"
        />
      </v-col>
      <v-col cols="12" md="6">
        <ListItemsField
          v-model="form.test_script"
          :label="$t('assetModels.fields.testScript')"
          :hint="$t('assetModels.testScriptHint')"
          :error-messages="fieldErrors.test_script"
          :max-length="200"
        />
      </v-col>
    </v-row>

    <v-row dense class="mt-2">
      <v-col cols="12">
        <v-switch
          v-model="form.is_enabled"
          :label="$t('catalogs.fields.enabled')"
          color="primary"
          hide-details
          inset
        />
      </v-col>
      <v-col cols="12">
        <KeywordsField
          v-model="form.keywords"
          :error-messages="fieldErrors.keywords"
          data-testid="keywords"
        />
      </v-col>
      <v-col cols="12">
        <v-textarea
          v-model="form.notes"
          :label="$t('customers.fields.notes')"
          :error-messages="fieldErrors.notes"
          rows="2"
          auto-grow
        />
      </v-col>
    </v-row>

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
