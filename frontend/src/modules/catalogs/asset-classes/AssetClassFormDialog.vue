<script setup lang="ts">
import FormDialog from '@/components/FormDialog.vue'
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import { useValidationRules } from '@/composables/useValidationRules'
import SubVerticalPicker from '../verticals/SubVerticalPicker.vue'
import IconPicker from './IconPicker.vue'
import KeywordsField from '@/components/KeywordsField.vue'
import { PHOTO_KINDS } from '@/modules/inventory/api'
import RemarketingEditor from '../remarketing/RemarketingEditor.vue'
import {
  createAssetClass,
  REMARKETING_RATINGS,
  updateAssetClass,
  type AssetClass,
  type AssetClassInput,
} from './api'
import { DEFAULT_ASSET_ICON } from './icons'
import { LANGUAGES } from '@/i18n'
import { englishPlural } from './names'

/** Create (assetClass = null) or edit an asset class. */
const props = defineProps<{ assetClass: AssetClass | null }>()
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ saved: [assetClass: AssetClass, created: boolean] }>()

const { t } = useI18n()
const rules = useValidationRules()

const FIELDS = [
  'name',
  'plural_name',
  'translations',
  'icon',
  'sub_vertical',
  ...REMARKETING_RATINGS,
  'keywords',
  'notes',
  'required_photo_kinds',
]

/** The other languages: an optional name and plural each (empty: English) */
const OTHER_LANGUAGES = LANGUAGES.filter((language) => language.code !== 'en')
const emptyTranslations = () =>
  Object.fromEntries(OTHER_LANGUAGES.map((l) => [l.code, { name: '', plural: '' }]))

// The plural follows the name (English rule) until it is typed
const pluralTouched = ref(false)
function onNameChange(name: string) {
  clearError('name')
  if (!pluralTouched.value) form.value.plural_name = englishPlural(name)
}

function emptyForm(): AssetClassInput {
  return {
    name: '',
    plural_name: '',
    translations: emptyTranslations(),
    icon: DEFAULT_ASSET_ICON,
    sub_vertical: null,
    liquidity: '0.0',
    value_retention: '0.0',
    technology_renewal: '0.0',
    usage_breadth: '0.0',
    keywords: [],
    notes: '',
    is_enabled: true,
    required_photo_kinds: [],
  }
}

const form = ref<AssetClassInput>(emptyForm())
const fieldErrors = ref<Record<string, string[]>>({})
const generalError = ref('')
const saving = ref(false)
const formRef = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(null)
const openCount = ref(0) // remounts the sub-vertical picker on every open

const isEdit = computed(() => props.assetClass !== null)
const photoKindOptions = computed(() =>
  PHOTO_KINDS.map((value) => ({ value, title: t(`inventory.photoKinds.${value}`) })),
)
const subVerticalRules = [
  (v: unknown) => (v !== null && v !== undefined) || t('validation.required'),
]

watch(open, (isOpen) => {
  if (!isOpen) return
  const a = props.assetClass
  form.value = a
    ? {
        name: a.name,
        plural_name: a.plural_name ?? englishPlural(a.name),
        translations: {
          ...emptyTranslations(),
          ...Object.fromEntries(
            Object.entries(a.translations ?? {}).map(([code, entry]) => [
              code,
              { name: entry.name ?? '', plural: entry.plural ?? '' },
            ]),
          ),
        },
        icon: a.icon,
        sub_vertical: a.sub_vertical,
        liquidity: a.liquidity,
        value_retention: a.value_retention,
        technology_renewal: a.technology_renewal,
        usage_breadth: a.usage_breadth,
        keywords: [...a.keywords],
        notes: a.notes,
        is_enabled: a.is_enabled,
        required_photo_kinds: [...(a.required_photo_kinds ?? [])],
      }
    : emptyForm()
  fieldErrors.value = {}
  generalError.value = ''
  // Editing: the plural is the one saved (it only follows the name while it is the suggested)
  pluralTouched.value = !!a && a.plural_name !== englishPlural(a.name)
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
      ...form.value,
      name: form.value.name.trim(),
      plural_name: form.value.plural_name.trim(),
    }
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
  <FormDialog
    ref="formRef"
    v-model="open"
    :title="isEdit ? $t('assetClasses.edit') : $t('assetClasses.new')"
    :subtitle="assetClass ? `${assetClass.name} · ${assetClass.sub_vertical_detail.label}` : null"
    icon="mdi-tag-multiple-outline"
    max-width="760"
    :persistent="saving"
    @submit="submit"
  >
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
          @update:model-value="onNameChange"
        />
        <v-text-field
          v-model="form.plural_name"
          :label="$t('assetClasses.fields.pluralName')"
          :hint="$t('assetClasses.fields.pluralNameHint')"
          :rules="[rules.required, rules.maxLength(100)]"
          :error-messages="fieldErrors.plural_name"
          maxlength="100"
          data-testid="plural-name"
          @update:model-value="((pluralTouched = true), clearError('plural_name'))"
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

    <!-- The name in other languages (optional: empty = English); folded until opened -->
    <v-expansion-panels variant="accordion" class="mb-4 translations" data-testid="translations">
      <v-expansion-panel elevation="0">
        <v-expansion-panel-title class="px-3" data-testid="translations-toggle">
          <div>
            <div class="text-subtitle-1">{{ $t('assetClasses.translations.title') }}</div>
            <div class="text-body-2 text-medium-emphasis">
              {{ $t('assetClasses.translations.subtitle') }}
            </div>
          </div>
        </v-expansion-panel-title>
        <v-expansion-panel-text eager>
          <div
            v-for="language in OTHER_LANGUAGES"
            :key="language.code"
            class="d-flex flex-wrap ga-3 align-start"
            :data-testid="`translation-${language.code}`"
          >
            <div class="translation-language text-body-2 pt-3">{{ language.name }}</div>
            <v-text-field
              v-model="form.translations[language.code]!.name"
              :label="$t('assetClasses.fields.name')"
              :placeholder="form.name"
              persistent-placeholder
              maxlength="100"
              class="flex-grow-1"
              density="compact"
              :data-testid="`translation-${language.code}-name`"
            />
            <v-text-field
              v-model="form.translations[language.code]!.plural"
              :label="$t('assetClasses.fields.pluralName')"
              :placeholder="form.plural_name"
              persistent-placeholder
              maxlength="100"
              class="flex-grow-1"
              density="compact"
              :data-testid="`translation-${language.code}-plural`"
            />
          </div>
          <div v-if="fieldErrors.translations" class="text-caption text-error mb-2">
            {{ fieldErrors.translations.join(' ') }}
          </div>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>

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

    <!-- Photos every inspection report of its assets must have -->
    <v-select
      v-model="form.required_photo_kinds"
      :items="photoKindOptions"
      :label="$t('assetClasses.fields.requiredPhotos')"
      :hint="$t('assetClasses.requiredPhotosHint')"
      persistent-hint
      multiple
      chips
      closable-chips
      class="mb-4"
      data-testid="required-photos"
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

<style scoped>
.translations {
  border: thin solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 10px;
}
.translation-language {
  flex: 0 0 160px;
}
</style>
