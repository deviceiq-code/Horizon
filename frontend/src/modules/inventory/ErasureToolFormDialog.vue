<script setup lang="ts">
/** An erasure tool: name, version, methods (at least one), the asset classes it serves. */
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import FormDialog from '@/components/FormDialog.vue'
import { useValidationRules } from '@/composables/useValidationRules'
import { listAssetClasses, type AssetClass } from '@/modules/catalogs/asset-classes/api'
import {
  ERASURE_METHODS,
  createErasureTool,
  updateErasureTool,
  type ErasureMethod,
  type ErasureTool,
} from './api'

const props = defineProps<{ tool: ErasureTool | null }>()
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ saved: [tool: ErasureTool, created: boolean] }>()

const { t } = useI18n()
const rules = useValidationRules()

const name = ref('')
const version = ref('')
const methods = ref<ErasureMethod[]>([])
const classes = ref<number[]>([])
const notes = ref('')
const isActive = ref(true)
const allClasses = ref<AssetClass[]>([])
const fieldErrors = ref<Record<string, string[]>>({})
const generalError = ref('')
const saving = ref(false)
const formRef = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(null)

const methodOptions = computed(() =>
  ERASURE_METHODS.map((v) => ({ value: v, title: t(`inventory.erasure.methodNames.${v}`) })),
)
const classOptions = computed(() => allClasses.value.map((c) => ({ value: c.id, title: c.name })))

onMounted(async () => {
  try {
    allClasses.value = (
      await listAssetClasses({ page: 1, pageSize: 200, ordering: 'name' })
    ).results
  } catch {
    allClasses.value = []
  }
})

watch(open, (isOpen) => {
  if (!isOpen) return
  const tool = props.tool
  name.value = tool?.name ?? ''
  version.value = tool?.version ?? ''
  methods.value = [...(tool?.methods ?? [])]
  classes.value = [...(tool?.asset_classes ?? [])]
  notes.value = tool?.notes ?? ''
  isActive.value = tool?.is_active ?? true
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
    const data = {
      name: name.value,
      version: version.value,
      methods: methods.value,
      asset_classes: classes.value,
      notes: notes.value,
      is_active: isActive.value,
    }
    const saved = props.tool
      ? await updateErasureTool(props.tool.id, data)
      : await createErasureTool(data)
    emit('saved', saved, !props.tool)
    open.value = false
  } catch (error) {
    const errors = error instanceof ApiError ? error.fieldErrors() : {}
    if (Object.keys(errors).length) fieldErrors.value = errors
    else generalError.value = t('common.saveError')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <FormDialog
    :audit="tool"
    ref="formRef"
    v-model="open"
    :title="tool ? $t('inventory.erasure.edit') : $t('inventory.erasure.new')"
    :subtitle="tool ? `${tool.name} ${tool.version}` : null"
    icon="mdi-harddisk-remove"
    max-width="680"
    :persistent="saving"
    @submit="submit"
  >
    <v-row dense>
      <v-col cols="12" md="8">
        <v-text-field
          v-model="name"
          :label="$t('inventory.erasure.tool')"
          :rules="[rules.required, rules.maxLength(100)]"
          :error-messages="fieldErrors.name"
          maxlength="100"
          data-testid="tool-name"
        />
      </v-col>
      <v-col cols="12" md="4">
        <v-text-field
          v-model="version"
          :label="$t('inventory.erasure.version')"
          maxlength="40"
          :error-messages="fieldErrors.version"
        />
      </v-col>
      <v-col cols="12">
        <v-select
          v-model="methods"
          :items="methodOptions"
          :label="$t('inventory.erasure.methods')"
          multiple
          chips
          closable-chips
          :rules="[(v: unknown[]) => v.length > 0 || $t('validation.required')]"
          :error-messages="fieldErrors.methods"
          data-testid="tool-methods"
        />
      </v-col>
      <v-col cols="12">
        <v-autocomplete
          v-model="classes"
          :items="classOptions"
          :label="$t('inventory.erasure.classes')"
          multiple
          chips
          closable-chips
          :error-messages="fieldErrors.asset_classes"
        />
      </v-col>
      <v-col cols="12">
        <v-textarea v-model="notes" :label="$t('customers.fields.notes')" rows="2" auto-grow />
      </v-col>
      <v-col cols="12">
        <v-switch v-model="isActive" :label="$t('customers.status.active')" color="primary" inset />
      </v-col>
    </v-row>
    <v-alert v-if="generalError" type="error" variant="tonal" density="compact">
      {{ generalError }}
    </v-alert>
    <template #actions>
      <v-btn variant="text" :disabled="saving" @click="open = false">{{
        $t('common.cancel')
      }}</v-btn>
      <v-btn type="submit" color="primary" variant="flat" :loading="saving" data-testid="save">
        {{ $t('common.save') }}
      </v-btn>
    </template>
  </FormDialog>
</template>
