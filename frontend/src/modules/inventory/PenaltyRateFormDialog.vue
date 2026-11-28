<script setup lang="ts">
/** A penalty: asset class, kind of finding, value (BRL) and validity (open end allowed).
 * Periods of the same class and kind never overlap (the server refuses). */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import FormDialog from '@/components/FormDialog.vue'
import MoneyField from '@/components/MoneyField.vue'
import AssetClassPicker from '@/modules/catalogs/asset-classes/AssetClassPicker.vue'
import { parseMoney, toInputMoney } from '@/utils/money'
import {
  FINDING_KINDS,
  createPenaltyRate,
  updatePenaltyRate,
  type FindingKind,
  type PenaltyRate,
} from './api'

const props = defineProps<{ rate: PenaltyRate | null }>()
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ saved: [rate: PenaltyRate, created: boolean] }>()

const { t, locale } = useI18n()

const assetClass = ref<number | null>(null)
const kind = ref<FindingKind>('damage')
const value = ref('')
const validFrom = ref('')
const validTo = ref('')
const fieldErrors = ref<Record<string, string[]>>({})
const generalError = ref('')
const saving = ref(false)
const openCount = ref(0)
const formRef = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(null)

const kindOptions = computed(() =>
  FINDING_KINDS.map((v) => ({ value: v, title: t(`inventory.findings.kinds.${v}`) })),
)
const required = [
  (v: unknown) => (v !== null && v !== undefined && v !== '') || t('validation.required'),
]
const moneyRule = (v: string) => parseMoney(v, locale.value, 2) !== null || t('validation.required')

watch(open, (isOpen) => {
  if (!isOpen) return
  const r = props.rate
  assetClass.value = r?.asset_class ?? null
  kind.value = r?.finding_kind ?? 'damage'
  value.value = r ? toInputMoney(r.value, locale.value, 2) : ''
  validFrom.value = r?.valid_from ?? new Date().toISOString().slice(0, 10)
  validTo.value = r?.valid_to ?? ''
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
    const data = {
      asset_class: assetClass.value,
      finding_kind: kind.value,
      value: parseMoney(value.value, locale.value, 2) ?? '',
      valid_from: validFrom.value,
      valid_to: validTo.value || null,
    }
    const saved = props.rate
      ? await updatePenaltyRate(props.rate.id, data)
      : await createPenaltyRate(data)
    emit('saved', saved, !props.rate)
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
    :audit="rate"
    ref="formRef"
    v-model="open"
    :title="rate ? $t('inventory.penalties.edit') : $t('inventory.penalties.new')"
    :subtitle="rate ? rate.asset_class_name : null"
    icon="mdi-cash-multiple"
    max-width="640"
    :persistent="saving"
    @submit="submit"
  >
    <v-row dense>
      <v-col cols="12">
        <AssetClassPicker
          :key="`class-${openCount}`"
          v-model="assetClass"
          :label="$t('inventory.fields.assetClass')"
          :initial-option="
            rate
              ? ({
                  id: rate.asset_class,
                  name: rate.asset_class_name,
                  sub_vertical_detail: { label: '' },
                } as never)
              : null
          "
          :rules="required"
          :error-messages="fieldErrors.asset_class"
          data-testid="penalty-class"
        />
      </v-col>
      <v-col cols="12" md="7">
        <v-select
          v-model="kind"
          :items="kindOptions"
          :label="$t('inventory.penalties.kind')"
          :error-messages="fieldErrors.finding_kind"
          data-testid="penalty-kind"
        />
      </v-col>
      <v-col cols="12" md="5">
        <MoneyField
          v-model="value"
          :label="$t('inventory.penalties.value')"
          :rules="[moneyRule]"
          :error-messages="fieldErrors.value"
          data-testid="penalty-value"
        />
      </v-col>
      <v-col cols="6">
        <v-text-field
          v-model="validFrom"
          type="date"
          :label="$t('inventory.penalties.validFrom')"
          :rules="required"
          :error-messages="fieldErrors.valid_from"
          data-testid="penalty-from"
        />
      </v-col>
      <v-col cols="6">
        <v-text-field
          v-model="validTo"
          type="date"
          :label="$t('inventory.penalties.validTo')"
          :hint="$t('inventory.penalties.validToHint')"
          persistent-hint
          :error-messages="fieldErrors.valid_to"
        />
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
