<script setup lang="ts">
/**
 * Create a location (an area of the warehouse, or under `parent`) or edit one. The segment
 * makes its code (parent's code + "-" + segment) and never changes; the kind of area (children
 * start with their parent's), the description and the active flag can.
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import FormDialog from '@/components/FormDialog.vue'
import { useValidationRules } from '@/composables/useValidationRules'
import type { Warehouse } from '@/modules/warehouses/api'
import { AREA_TYPES, createLocation, updateLocation, type AreaType, type Location } from './api'

const props = defineProps<{
  location: Location | null
  parent: Location | null
  warehouse: Warehouse | null
}>()
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ saved: [location: Location, created: boolean] }>()

const { t } = useI18n()
const rules = useValidationRules()

const segment = ref('')
const areaType = ref<AreaType | null>(null)
const description = ref('')
const isActive = ref(true)
const fieldErrors = ref<Record<string, string[]>>({})
const generalError = ref('')
const saving = ref(false)
const formRef = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(null)

const isEdit = computed(() => props.location !== null)
const base = computed(() => props.parent?.code ?? props.warehouse?.code ?? '')
const preview = computed(() => {
  const typed = segment.value.replace(/\s+/g, '').toUpperCase()
  return typed ? `${base.value}-${typed}` : `${base.value}-…`
})
const areaOptions = computed(() =>
  AREA_TYPES.map((value) => ({ value, title: t(`inventory.areas.${value}`) })),
)
const segmentRule = (v: string) =>
  /^[A-Za-z0-9]{1,20}$/.test(v.replace(/\s+/g, '')) || t('inventory.locations.segmentRule')

watch(open, (isOpen) => {
  if (!isOpen) return
  const l = props.location
  segment.value = l?.segment ?? ''
  areaType.value = l?.area_type ?? (props.parent?.area_type as AreaType | undefined) ?? null
  description.value = l?.description ?? ''
  isActive.value = l?.is_active ?? true
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
    const saved = props.location
      ? await updateLocation(props.location.id, {
          area_type: areaType.value!,
          description: description.value,
          is_active: isActive.value,
        })
      : await createLocation({
          ...(props.parent ? { parent: props.parent.id } : { warehouse: props.warehouse?.id }),
          segment: segment.value,
          area_type: areaType.value!,
          description: description.value,
        })
    emit('saved', saved, !props.location)
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
    ref="formRef"
    v-model="open"
    :title="isEdit ? $t('inventory.locations.edit') : $t('inventory.locations.new')"
    :subtitle="location?.code ?? (parent ? parent.code : (warehouse?.name ?? null))"
    icon="mdi-file-tree-outline"
    max-width="620"
    :persistent="saving"
    @submit="submit"
  >
    <v-row dense>
      <v-col cols="12" md="5">
        <v-text-field
          v-model="segment"
          :label="$t('inventory.locations.segment')"
          :rules="isEdit ? [] : [rules.required, segmentRule]"
          :error-messages="fieldErrors.segment"
          :disabled="isEdit"
          maxlength="20"
          autofocus
          data-testid="segment"
        />
      </v-col>
      <v-col cols="12" md="7">
        <v-text-field
          :model-value="isEdit ? location!.code : preview"
          :label="$t('inventory.locations.code')"
          :hint="$t('inventory.locations.codeHint')"
          persistent-hint
          readonly
          data-testid="code-preview"
        />
      </v-col>
      <v-col cols="12">
        <v-select
          v-model="areaType"
          :items="areaOptions"
          :label="$t('inventory.locations.areaType')"
          :rules="[(v: unknown) => !!v || $t('validation.required')]"
          :error-messages="fieldErrors.area_type"
          data-testid="area-type"
        />
      </v-col>
      <v-col cols="12">
        <v-text-field
          v-model="description"
          :label="$t('inventory.locations.description')"
          :error-messages="fieldErrors.description"
          maxlength="150"
        />
      </v-col>
      <v-col v-if="isEdit" cols="12">
        <v-switch
          v-model="isActive"
          :label="$t('customers.status.active')"
          :error-messages="fieldErrors.is_active"
          color="primary"
          inset
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
