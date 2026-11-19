<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import { useValidationRules } from '@/composables/useValidationRules'
import SubVerticalPicker from '../verticals/SubVerticalPicker.vue'
import IconPicker from './IconPicker.vue'
import KeywordsField from './KeywordsField.vue'
import RemarketingEditor from '../remarketing/RemarketingEditor.vue'
import {
  createAssetClass,
  REMARKETING_RATINGS,
  updateAssetClass,
  type AssetClass,
  type AssetClassInput,
} from './api'
import { DEFAULT_ASSET_ICON } from './icons'

/** Create (assetClass = null) or edit an asset class. */
const props = defineProps<{ assetClass: AssetClass | null }>()
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ saved: [assetClass: AssetClass, created: boolean] }>()

const { t } = useI18n()
const rules = useValidationRules()

const FIELDS = ['name', 'icon', 'sub_vertical', ...REMARKETING_RATINGS, 'keywords', 'notes']

function emptyForm(): AssetClassInput {
  return {
    name: '',
    icon: DEFAULT_ASSET_ICON,
    sub_vertical: null,
    liquidity: '0.0',
    value_retention: '0.0',
    technology_renewal: '0.0',
    usage_breadth: '0.0',
    keywords: [],
    notes: '',
    is_enabled: true,
  }
}

const form = ref<AssetClassInput>(emptyForm())
const fieldErrors = ref<Record<string, string[]>>({})
const generalError = ref('')
const saving = ref(false)
const formRef = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(null)
const openCount = ref(0) // remounts the sub-vertical picker on every open

const isEdit = computed(() => props.assetClass !== null)
const subVerticalRules = [
  (v: unknown) => (v !== null && v !== undefined) || t('validation.required'),
]

watch(open, (isOpen) => {
  if (!isOpen) return
  const a = props.assetClass
  form.value = a
    ? {
        name: a.name,
        icon: a.icon,
        sub_vertical: a.sub_vertical,
        liquidity: a.liquidity,
        value_retention: a.value_retention,
        technology_renewal: a.technology_renewal,
        usage_breadth: a.usage_breadth,
        keywords: [...a.keywords],
        notes: a.notes,
        is_enabled: a.is_enabled,
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
    const saved = props.assetClass
      ? await updateAssetClass(props.assetClass.id, data)
      : await createAssetClass(data)
    emit('saved', saved, !props.assetClass)
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
  <v-dialog v-model="open" max-width="760" scrollable :persistent="saving">
    <v-card :title="isEdit ? $t('assetClasses.edit') : $t('assetClasses.new')">
      <v-form
        ref="formRef"
        class="d-flex flex-column"
        style="min-height: 0"
        @submit.prevent="submit"
      >
        <v-card-text>
          <!-- Identification -->
          <div class="d-flex flex-wrap ga-4 align-start">
            <IconPicker
              v-model="form.icon"
              :label="$t('assetClasses.fields.icon')"
              :error-messages="fieldErrors.icon"
              data-testid="icon"
              @update:model-value="clearError('icon')"
            />
            <div class="flex-grow-1" style="min-width: 280px">
              <v-text-field
                v-model="form.name"
                :label="$t('assetClasses.fields.name')"
                :rules="[rules.required, rules.maxLength(100)]"
                :error-messages="fieldErrors.name"
                maxlength="100"
                autofocus
                data-testid="name"
                @update:model-value="clearError('name')"
              />
              <SubVerticalPicker
                :key="openCount"
                v-model="form.sub_vertical"
                :initial-option="assetClass?.sub_vertical_detail ?? null"
                :label="$t('assetClasses.fields.subVertical')"
                :rules="subVerticalRules"
                :error-messages="fieldErrors.sub_vertical"
                data-testid="sub-vertical"
                @update:model-value="clearError('sub_vertical')"
              />
            </div>
          </div>

          <!-- Remarketing rating -->
          <div class="text-subtitle-1 mt-2">{{ $t('assetClasses.remarketing.title') }}</div>
          <p class="text-body-2 text-medium-emphasis mb-3">
            {{ $t('assetClasses.remarketing.subtitle') }}
          </p>
          <RemarketingEditor
            :ratings="form"
            :fields="REMARKETING_RATINGS"
            i18n-prefix="assetClasses.remarketing"
            :errors="fieldErrors"
            class="mb-4"
            @edited="clearError"
          />

          <!-- Keywords, notes, status -->
          <KeywordsField
            v-model="form.keywords"
            :label="$t('assetClasses.fields.keywords')"
            :error-messages="fieldErrors.keywords"
            class="mb-2"
            data-testid="keywords"
            @update:model-value="clearError('keywords')"
          />
          <v-textarea
            v-model="form.notes"
            :label="$t('assetClasses.fields.notes')"
            :error-messages="fieldErrors.notes"
            rows="2"
            auto-grow
            data-testid="notes"
            @update:model-value="clearError('notes')"
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
