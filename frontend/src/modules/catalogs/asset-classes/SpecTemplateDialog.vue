<script setup lang="ts">
/**
 * Edit the specification template of an asset class: the fields every average price of that
 * class describes (e.g. "Operating hours", number, "h", required). Saving replaces the
 * template; records already saved keep the template they were created with. "Import Template"
 * brings the fields of another asset class of the same vertical (`templateImport.ts`): added to
 * these or replacing them, applied only when saved.
 */
import FormDialog from '@/components/FormDialog.vue'
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import { useValidationRules } from '@/composables/useValidationRules'
import { useNotificationsStore } from '@/stores/notifications'
import ListItemsField from '@/components/ListItemsField.vue'
import {
  getSpecTemplate,
  listAssetClasses,
  SPEC_KINDS,
  saveSpecTemplate,
  type AssetClass,
  type SpecField,
} from './api'
import { importFields, type ImportMode } from './templateImport'

const props = withDefaults(
  defineProps<{ assetClassId: number | null; label: string; verticalId?: number | null }>(),
  { verticalId: null },
)
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ saved: [fields: SpecField[]] }>()

const { t } = useI18n()
const rules = useValidationRules()
const notifications = useNotificationsStore()

const fields = ref<SpecField[]>([])
const rowErrors = ref<Record<number, string[]>>({})
const listErrors = ref<string[]>([])
const loading = ref(false)
const saving = ref(false)
const formRef = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(null)

const kinds = SPEC_KINDS.map((kind) => ({ value: kind, titleKey: `specTemplate.kinds.${kind}` }))

watch(open, async (isOpen) => {
  if (!isOpen || props.assetClassId === null) return
  rowErrors.value = {}
  listErrors.value = []
  loading.value = true
  try {
    fields.value = (await getSpecTemplate(props.assetClassId)).fields
  } catch {
    listErrors.value = [t('common.loadError')]
  } finally {
    loading.value = false
  }
})

function add() {
  fields.value = [
    ...fields.value,
    { key: '', label: '', kind: 'text', unit: '', required: false, options: [] },
  ]
}

function remove(index: number) {
  fields.value = fields.value.filter((_, i) => i !== index)
  rowErrors.value = {}
}

function move(index: number, delta: number) {
  const target = index + delta
  if (target < 0 || target >= fields.value.length) return
  const copy = [...fields.value]
  ;[copy[index], copy[target]] = [copy[target]!, copy[index]!]
  fields.value = copy
  rowErrors.value = {}
}

// --- Import from another asset class of the same vertical -------------------------------------

const importOpen = ref(false)
const sources = ref<AssetClass[]>([])
const sourceId = ref<number | null>(null)
const importMode = ref<ImportMode>('add')
const loadingSources = ref(false)
const source = computed(() => sources.value.find((c) => c.id === sourceId.value) ?? null)
const sourceOptions = computed(() =>
  sources.value.map((c) => ({
    value: c.id,
    title: c.name,
    subtitle: `${c.sub_vertical_detail.label} · ${t('specTemplate.fieldCount', c.spec_template.length)}`,
  })),
)

/** Where to look: the same vertical (default) or any vertical */
const sourceScope = ref<'vertical' | 'any'>('vertical')

function openImport() {
  importOpen.value = true
  importMode.value = fields.value.length ? 'add' : 'replace'
  sourceScope.value = props.verticalId ? 'vertical' : 'any'
  loadSources()
}

watch(sourceScope, () => {
  if (importOpen.value) loadSources()
})

async function loadSources() {
  sourceId.value = null
  loadingSources.value = true
  try {
    const data = await listAssetClasses({
      page: 1,
      pageSize: 200,
      ordering: 'name',
      filters:
        sourceScope.value === 'vertical' && props.verticalId ? { vertical: props.verticalId } : {},
    })
    sources.value = data.results.filter(
      (c) => c.id !== props.assetClassId && c.spec_template.length > 0,
    )
  } catch {
    sources.value = []
  } finally {
    loadingSources.value = false
  }
}

/** Typing finds a class by its name or by its vertical / sub-vertical */
function matchSource(
  _value: string,
  query: string,
  item?: { raw?: { title: string; subtitle: string } },
) {
  const text = `${item?.raw?.title ?? ''} ${item?.raw?.subtitle ?? ''}`.toLowerCase()
  return query
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .every((word) => text.includes(word))
}

function applyImport() {
  if (!source.value) return
  const result = importFields(fields.value, source.value.spec_template, importMode.value)
  fields.value = result.fields
  rowErrors.value = {}
  importOpen.value = false
  notifications.notify(
    t('specTemplate.import.done', { added: result.added, skipped: result.skipped }),
  )
}

async function submit() {
  const result = await formRef.value?.validate()
  if (!result?.valid || props.assetClassId === null) return
  saving.value = true
  rowErrors.value = {}
  listErrors.value = []
  try {
    const saved = await saveSpecTemplate(props.assetClassId, fields.value)
    notifications.notify(t('specTemplate.saved'))
    emit('saved', saved.fields)
    open.value = false
  } catch (error) {
    const body = error instanceof ApiError && error.status === 400 ? error.data : null
    const errors = (body as { fields?: Record<string, string[]> } | null)?.fields
    if (errors) {
      listErrors.value = errors.__all__ ?? []
      rowErrors.value = Object.fromEntries(
        Object.entries(errors)
          .filter(([key]) => key !== '__all__')
          .map(([index, messages]) => [Number(index), messages]),
      )
    } else {
      listErrors.value = [t('common.saveError')]
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
    :title="$t('specTemplate.title')"
    :subtitle="label"
    icon="mdi-format-list-checks"
    max-width="1200"
    :persistent="saving"
    @submit="submit"
  >
    <p class="text-body-2 text-medium-emphasis mb-4">{{ $t('specTemplate.hint') }}</p>
    <v-progress-linear v-if="loading" indeterminate class="mb-4" />
    <v-alert
      v-for="message in listErrors"
      :key="message"
      type="error"
      variant="tonal"
      density="compact"
      class="mb-3"
    >
      {{ message }}
    </v-alert>

    <p v-if="!loading && !fields.length" class="text-medium-emphasis mb-4">
      {{ $t('specTemplate.empty') }}
    </p>

    <v-sheet
      v-for="(field, index) in fields"
      :key="index"
      border
      rounded
      class="pa-3 pb-0 mb-3"
      :data-testid="`spec-field-${index}`"
    >
      <v-row dense>
        <v-col cols="12" md="4">
          <v-text-field
            v-model="field.label"
            :label="$t('specTemplate.fields.label')"
            :rules="[rules.required, rules.maxLength(60)]"
            :error-messages="rowErrors[index]"
            maxlength="60"
            data-testid="spec-label"
          />
        </v-col>
        <v-col cols="6" md="3">
          <v-select
            v-model="field.kind"
            :items="kinds.map((k) => ({ value: k.value, title: $t(k.titleKey) }))"
            :label="$t('specTemplate.fields.kind')"
            data-testid="spec-kind"
          />
        </v-col>
        <v-col cols="6" md="2">
          <!-- Only numbers have a unit -->
          <v-text-field
            v-if="field.kind === 'number'"
            v-model="field.unit"
            :label="$t('specTemplate.fields.unit')"
            :placeholder="$t('specTemplate.unitPlaceholder')"
            :rules="[rules.maxLength(20)]"
            maxlength="20"
            data-testid="spec-unit"
          />
        </v-col>
        <v-col cols="8" md="2" class="d-flex align-center">
          <v-switch
            v-model="field.required"
            :label="$t('specTemplate.fields.required')"
            color="primary"
            density="compact"
            hide-details
            inset
            data-testid="spec-required"
          />
        </v-col>
        <v-col cols="4" md="1" class="d-flex flex-column align-end">
          <div class="d-flex">
            <v-btn
              icon="mdi-arrow-up"
              variant="text"
              size="x-small"
              :disabled="index === 0"
              :aria-label="$t('specTemplate.moveUp')"
              @click="move(index, -1)"
            />
            <v-btn
              icon="mdi-arrow-down"
              variant="text"
              size="x-small"
              :disabled="index === fields.length - 1"
              :aria-label="$t('specTemplate.moveDown')"
              @click="move(index, 1)"
            />
          </div>
          <v-btn
            icon="mdi-delete-outline"
            variant="text"
            size="small"
            color="error"
            :aria-label="$t('specTemplate.remove')"
            :title="$t('specTemplate.remove')"
            data-testid="spec-remove"
            @click="remove(index)"
          />
        </v-col>
        <!-- The items a "choice" field offers -->
        <v-col v-if="field.kind === 'choice'" cols="12" class="pb-2">
          <ListItemsField
            v-model="field.options"
            :label="$t('specTemplate.fields.options')"
            :hint="$t('specTemplate.optionsHint')"
            data-testid="spec-options"
          />
        </v-col>
      </v-row>
    </v-sheet>

    <div class="d-flex flex-wrap ga-2">
      <v-btn
        variant="tonal"
        prepend-icon="mdi-plus"
        :disabled="loading"
        data-testid="spec-add"
        @click="add"
      >
        {{ $t('specTemplate.add') }}
      </v-btn>
      <v-btn
        variant="text"
        prepend-icon="mdi-import"
        :disabled="loading"
        data-testid="spec-import"
        @click="openImport"
      >
        {{ $t('specTemplate.import.button') }}
      </v-btn>
    </div>

    <v-dialog v-model="importOpen" max-width="560">
      <v-card :title="$t('specTemplate.import.title')" data-testid="import-dialog">
        <v-card-text>
          <p class="text-body-2 text-medium-emphasis mb-3">
            {{ $t('specTemplate.import.hint') }}
          </p>
          <v-btn-toggle
            v-model="sourceScope"
            mandatory
            density="comfortable"
            variant="outlined"
            divided
            color="primary"
            class="mb-4"
            data-testid="import-scope"
          >
            <v-btn value="vertical" :disabled="!verticalId" data-testid="import-scope-vertical">{{
              $t('specTemplate.import.sameVertical')
            }}</v-btn>
            <v-btn value="any" data-testid="import-scope-any">{{
              $t('specTemplate.import.anyVertical')
            }}</v-btn>
          </v-btn-toggle>
          <v-progress-linear v-if="loadingSources" indeterminate class="mb-3" />
          <v-autocomplete
            v-model="sourceId"
            :items="sourceOptions"
            :label="$t('specTemplate.import.source')"
            :no-data-text="$t('specTemplate.import.none')"
            :item-props="
              (item: { title: string; subtitle: string }) => ({ subtitle: item.subtitle })
            "
            :custom-filter="matchSource"
            auto-select-first
            data-testid="import-source"
          />
          <div v-if="source" class="d-flex flex-wrap ga-1 mb-3" data-testid="import-preview">
            <v-chip v-for="field in source.spec_template" :key="field.key" size="small" label>
              {{ field.label }}
              <span class="text-medium-emphasis ml-1"
                >· {{ $t(`specTemplate.kinds.${field.kind}`) }}</span
              >
            </v-chip>
          </div>
          <v-radio-group v-model="importMode" hide-details>
            <v-radio value="add" :label="$t('specTemplate.import.add')" data-testid="import-add" />
            <v-radio
              value="replace"
              :label="$t('specTemplate.import.replace')"
              data-testid="import-replace"
            />
          </v-radio-group>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="importOpen = false">{{ $t('common.cancel') }}</v-btn>
          <v-btn
            color="primary"
            variant="flat"
            :disabled="!source"
            data-testid="import-apply"
            @click="applyImport"
            >{{ $t('specTemplate.import.apply') }}</v-btn
          >
        </v-card-actions>
      </v-card>
    </v-dialog>

    <template #actions>
      <v-btn variant="text" :disabled="saving" @click="open = false">
        {{ $t('common.cancel') }}
      </v-btn>
      <v-btn
        type="submit"
        color="primary"
        variant="flat"
        :loading="saving"
        :disabled="loading"
        data-testid="save"
      >
        {{ $t('common.save') }}
      </v-btn>
    </template>
  </FormDialog>
</template>
