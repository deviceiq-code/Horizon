<script setup lang="ts">
/**
 * Edit the specification template of an asset class: the fields every average price of that
 * class describes (e.g. "Operating hours", number, "h", required). Saving replaces the
 * template; records already saved keep the template they were created with.
 */
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import { useValidationRules } from '@/composables/useValidationRules'
import { useNotificationsStore } from '@/stores/notifications'
import ListItemsField from '@/components/ListItemsField.vue'
import { getSpecTemplate, SPEC_KINDS, saveSpecTemplate, type SpecField } from './api'

const props = defineProps<{ assetClassId: number | null; label: string }>()
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
  <v-dialog v-model="open" max-width="1200" scrollable :persistent="saving">
    <v-card :title="$t('specTemplate.title')" :subtitle="label">
      <v-form
        ref="formRef"
        class="d-flex flex-column"
        style="min-height: 0"
        @submit.prevent="submit"
      >
        <v-card-text>
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

          <v-btn
            variant="tonal"
            prepend-icon="mdi-plus"
            :disabled="loading"
            data-testid="spec-add"
            @click="add"
          >
            {{ $t('specTemplate.add') }}
          </v-btn>
        </v-card-text>

        <v-card-actions>
          <v-spacer />
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
        </v-card-actions>
      </v-form>
    </v-card>
  </v-dialog>
</template>
