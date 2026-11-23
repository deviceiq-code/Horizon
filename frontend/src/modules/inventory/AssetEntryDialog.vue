<script setup lang="ts">
/**
 * Manual entry of an asset at a dock (administrators) — until the triage of receiving lots
 * (Phase 2) takes its place. Read the dock (or a container there), the asset's pre-printed
 * label (or leave it empty for a new Horizon ID), the model and the serial number; without a
 * serial, say why.
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import FormDialog from '@/components/FormDialog.vue'
import { useValidationRules } from '@/composables/useValidationRules'
import AssetModelPicker from '@/modules/catalogs/asset-models/AssetModelPicker.vue'
import { parseCode } from '@/utils/inventoryCodes'
import { NO_SERIAL_REASONS, registerEntry, type Asset } from './api'

const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ saved: [asset: Asset] }>()

const { t } = useI18n()
const rules = useValidationRules()

const form = ref({
  location: '',
  horizon_id: '',
  asset_model: null as number | null,
  serial: '',
  no_serial_reason: '',
  reason: '',
})
const fieldErrors = ref<Record<string, string[]>>({})
const generalError = ref('')
const saving = ref(false)
const openCount = ref(0)
const formRef = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(null)

const reasons = computed(() =>
  NO_SERIAL_REASONS.map((value) => ({ value, title: t(`inventory.noSerialReasons.${value}`) })),
)
const requiredModel = [(v: unknown) => typeof v === 'number' || t('validation.required')]
const idRule = (v: string) => {
  if (!v?.trim()) return true
  const parsed = parseCode(v)
  return (parsed.kind === 'asset' && parsed.valid) || t('inventory.movement.wrongDigit')
}
const reasonRule = (v: string) => !!form.value.serial.trim() || !!v || t('validation.required')

watch(open, (isOpen) => {
  if (!isOpen) return
  form.value = {
    location: '',
    horizon_id: '',
    asset_model: null,
    serial: '',
    no_serial_reason: '',
    reason: '',
  }
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
    const asset = await registerEntry({
      ...form.value,
      asset_model: form.value.asset_model!,
      no_serial_reason: form.value.serial.trim() ? '' : form.value.no_serial_reason,
    })
    emit('saved', asset)
    open.value = false
  } catch (error) {
    if (error instanceof ApiError) {
      const body = (error.data ?? {}) as { field?: string; detail?: string }
      const errors = error.fieldErrors()
      const shownFields = ['location', 'horizon_id', 'asset_model', 'serial']
      if (body.field && body.detail && shownFields.includes(body.field)) {
        fieldErrors.value = { [body.field]: [body.detail] }
      } else if (body.detail && !Object.keys(errors).length) {
        generalError.value = body.detail
      } else if (Object.keys(errors).length) fieldErrors.value = errors
      else generalError.value = error.message || t('common.saveError')
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
    :title="$t('inventory.assets.entryTitle')"
    :subtitle="$t('inventory.assets.entrySubtitle')"
    icon="mdi-tray-arrow-down"
    max-width="720"
    :persistent="saving"
    @submit="submit"
  >
    <v-row dense>
      <v-col cols="12" md="6">
        <v-text-field
          v-model="form.location"
          :label="$t('inventory.assets.entryPlace')"
          :rules="[rules.required]"
          :error-messages="fieldErrors.location"
          prepend-inner-icon="mdi-barcode-scan"
          autocomplete="off"
          autofocus
          data-testid="entry-location"
          @update:model-value="clearError('location')"
        />
      </v-col>
      <v-col cols="12" md="6">
        <v-text-field
          v-model="form.horizon_id"
          :label="$t('inventory.fields.horizonId')"
          :hint="$t('inventory.assets.horizonIdHint')"
          persistent-hint
          :rules="[idRule]"
          :error-messages="fieldErrors.horizon_id"
          prepend-inner-icon="mdi-barcode-scan"
          autocomplete="off"
          data-testid="entry-horizon-id"
          @update:model-value="clearError('horizon_id')"
        />
      </v-col>
      <v-col cols="12">
        <AssetModelPicker
          :key="`model-${openCount}`"
          v-model="form.asset_model"
          tracking="unit"
          :label="$t('inventory.fields.assetModel')"
          :rules="requiredModel"
          :error-messages="fieldErrors.asset_model"
          data-testid="entry-model"
          @update:model-value="clearError('asset_model')"
        />
      </v-col>
      <v-col cols="12" md="6">
        <v-text-field
          v-model="form.serial"
          :label="$t('inventory.fields.serial')"
          :error-messages="fieldErrors.serial"
          prepend-inner-icon="mdi-barcode-scan"
          autocomplete="off"
          maxlength="100"
          data-testid="entry-serial"
          @update:model-value="clearError('serial')"
        />
      </v-col>
      <v-col cols="12" md="6">
        <v-select
          v-model="form.no_serial_reason"
          :items="reasons"
          :label="$t('inventory.fields.noSerialReason')"
          :rules="[reasonRule]"
          :disabled="!!form.serial.trim()"
          clearable
          data-testid="entry-no-serial"
        />
      </v-col>
      <v-col cols="12">
        <v-text-field
          v-model="form.reason"
          :label="$t('inventory.fields.reason')"
          maxlength="300"
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
        {{ $t('inventory.assets.register') }}
      </v-btn>
    </template>
  </FormDialog>
</template>
