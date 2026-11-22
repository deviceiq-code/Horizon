<script setup lang="ts">
import FormDialog from '@/components/FormDialog.vue'
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import { useValidationRules } from '@/composables/useValidationRules'
import SubVerticalsEditor from './SubVerticalsEditor.vue'
import {
  createVertical,
  getVerticalDefaults,
  updateVertical,
  type SubVertical,
  type SubVerticalDefaults,
  type SubVerticalErrors,
  type Vertical,
  type VerticalInput,
} from './api'

/** Create (vertical = null) or edit a business vertical and its sub-verticals. */
const props = defineProps<{ vertical: Vertical | null }>()
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ saved: [vertical: Vertical, created: boolean] }>()

const { t } = useI18n()
const rules = useValidationRules()

const FIELDS = ['name', 'is_enabled', 'notes']

const form = ref<VerticalInput>({
  name: '',
  is_enabled: true,
  notes: '',
  sub_verticals: [],
})
const fieldErrors = ref<Record<string, string[]>>({})
const subRowErrors = ref<Record<number, Record<string, string[]>>>({})
const subListErrors = ref<string[]>([])
const generalError = ref('')
const saving = ref(false)
const loadingDefaults = ref(false)
const defaults = ref<SubVerticalDefaults | null>(null)
const formRef = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(null)

const isEdit = computed(() => props.vertical !== null)
const busy = computed(() => saving.value || loadingDefaults.value)

function copySubVertical(s: SubVertical): SubVertical {
  return { ...s, allowed_terms: [...s.allowed_terms] }
}

/** Defaults come from the backend (single source); loaded once per page. */
async function loadDefaults(): Promise<SubVerticalDefaults> {
  if (!defaults.value) defaults.value = await getVerticalDefaults()
  return defaults.value
}

watch(open, async (isOpen) => {
  if (!isOpen) return
  fieldErrors.value = {}
  subRowErrors.value = {}
  subListErrors.value = []
  generalError.value = ''

  const v = props.vertical
  form.value = {
    name: v?.name ?? '',
    is_enabled: v?.is_enabled ?? true,
    notes: v?.notes ?? '',
    sub_verticals: v ? v.sub_verticals.map(copySubVertical) : [],
  }

  // Needed for the general sub-vertical of a new vertical and for the terms field
  loadingDefaults.value = true
  try {
    const d = await loadDefaults()
    if (!v) {
      form.value.sub_verticals = [
        {
          name: '',
          is_general: true,
          risk: d.risk,
          allowed_terms: [...d.allowed_terms],
          recommended_term: d.recommended_term,
        },
      ]
    }
  } catch {
    generalError.value = t('common.loadError')
  } finally {
    loadingDefaults.value = false
  }
})

function onSubEdited(index: number, field: string) {
  if (field === '*') {
    subRowErrors.value = {} // rows moved: positions no longer match
  } else if (subRowErrors.value[index]?.[field]) {
    subRowErrors.value[index]![field] = []
  }
  subListErrors.value = []
}

function applySubErrors(errors: SubVerticalErrors | undefined) {
  if (!errors) return
  if (Array.isArray(errors)) {
    subListErrors.value = errors
  } else {
    subRowErrors.value = Object.fromEntries(
      Object.entries(errors).map(([index, fields]) => [Number(index), fields]),
    )
  }
}

async function submit() {
  const result = await formRef.value?.validate()
  if (!result?.valid) return

  saving.value = true
  fieldErrors.value = {}
  subRowErrors.value = {}
  subListErrors.value = []
  generalError.value = ''
  try {
    const data: VerticalInput = {
      ...form.value,
      name: form.value.name.trim(),
      sub_verticals: form.value.sub_verticals.map((s) => ({ ...s, name: s.name.trim() })),
    }
    const saved = props.vertical
      ? await updateVertical(props.vertical.id, data)
      : await createVertical(data)
    emit('saved', saved, !props.vertical)
    open.value = false
  } catch (error) {
    const body = error instanceof ApiError && error.status === 400 ? error.data : null
    if (body && typeof body === 'object') {
      const { sub_verticals, ...rest } = body as Record<string, unknown>
      fieldErrors.value = (error as ApiError).fieldErrors()
      applySubErrors(sub_verticals as SubVerticalErrors | undefined)
      if (!sub_verticals && !Object.keys(rest).some((k) => FIELDS.includes(k))) {
        generalError.value = t('common.saveError')
      }
    } else {
      generalError.value = t('common.saveError')
    }
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
    :title="isEdit ? $t('verticals.edit') : $t('verticals.new')"
    :subtitle="vertical?.name ?? null"
    icon="mdi-shape-outline"
    max-width="1000"
    :persistent="saving"
    @submit="submit"
  >
    <v-row dense>
      <v-col cols="12" md="6">
        <v-text-field
          v-model="form.name"
          :label="$t('verticals.fields.name')"
          :rules="[rules.required, rules.maxLength(100)]"
          :error-messages="fieldErrors.name"
          maxlength="100"
          autofocus
          data-testid="name"
          @update:model-value="clearError('name')"
        />
      </v-col>
      <v-col cols="12" md="6" class="d-flex align-center">
        <v-switch
          v-model="form.is_enabled"
          :label="$t('verticals.fields.enabled')"
          color="primary"
          inset
          hide-details
          data-testid="enabled"
        />
      </v-col>
      <v-col cols="12">
        <v-textarea
          v-model="form.notes"
          :label="$t('verticals.fields.notes')"
          :error-messages="fieldErrors.notes"
          rows="2"
          auto-grow
          data-testid="notes"
          @update:model-value="clearError('notes')"
        />
      </v-col>
    </v-row>

    <div class="text-subtitle-1 mb-1">{{ $t('verticals.subVerticals') }}</div>
    <p class="text-body-2 text-medium-emphasis mb-3">
      {{ $t('verticals.subVerticalsHint') }}
    </p>
    <v-progress-linear v-if="loadingDefaults" indeterminate class="mb-3" />
    <SubVerticalsEditor
      v-else-if="defaults"
      v-model="form.sub_verticals"
      :max-term="defaults.max_term_months"
      :row-errors="subRowErrors"
      :list-errors="subListErrors"
      :disabled="saving"
      @edited="onSubEdited"
    />

    <v-alert v-if="generalError" type="error" variant="tonal" density="compact" class="mt-3">
      {{ generalError }}
    </v-alert>

    <template #actions>
      <v-btn variant="text" :disabled="saving" @click="open = false">
        {{ $t('common.cancel') }}
      </v-btn>
      <v-btn
        type="submit"
        color="primary"
        variant="flat"
        :loading="saving"
        :disabled="busy || !defaults"
        data-testid="save"
      >
        {{ $t('common.save') }}
      </v-btn>
    </template>
  </FormDialog>
</template>
