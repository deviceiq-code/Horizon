<script setup lang="ts">
/**
 * A new transfer (origin and destination warehouses, reason, days it may take on the road) or
 * its header before sending (reason, transit days, notes, keywords).
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import FormDialog from '@/components/FormDialog.vue'
import KeywordsField from '@/components/KeywordsField.vue'
import { listWarehouses, type Warehouse } from '@/modules/warehouses/api'
import { createTransfer, updateTransfer, type TransferDetail } from './api'

const props = defineProps<{ transfer: TransferDetail | null }>()
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ saved: [transfer: TransferDetail] }>()

const { t } = useI18n()

const warehouses = ref<Warehouse[]>([])
const origin = ref<number | null>(null)
const destination = ref<number | null>(null)
const reason = ref('')
const transitDays = ref('5')
const notes = ref('')
const keywords = ref<string[]>([])
const fieldErrors = ref<Record<string, string[]>>({})
const generalError = ref('')
const saving = ref(false)
const formRef = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(null)

const editing = computed(() => props.transfer !== null)
const warehouseOptions = computed(() =>
  warehouses.value
    .filter((w) => w.is_active)
    .map((w) => ({ value: w.id, title: `${w.code} · ${w.name}` })),
)
const required = [
  (v: unknown) => (v !== null && v !== undefined && v !== '') || t('validation.required'),
]
const days = [
  (v: string) =>
    (/^\d+$/.test(v.trim()) && Number(v) >= 1 && Number(v) <= 90) ||
    t('inventory.transfers.daysRange'),
]

watch(open, async (isOpen) => {
  if (!isOpen) return
  const current = props.transfer
  origin.value = current?.origin ?? null
  destination.value = current?.destination ?? null
  reason.value = current?.reason ?? ''
  transitDays.value = String(current?.transit_days ?? 5)
  notes.value = current?.notes ?? ''
  keywords.value = [...(current?.keywords ?? [])]
  fieldErrors.value = {}
  generalError.value = ''
  if (!warehouses.value.length) {
    try {
      warehouses.value = (
        await listWarehouses({ page: 1, pageSize: 200, ordering: 'name' })
      ).results
    } catch {
      generalError.value = t('common.loadError')
    }
  }
})

async function submit() {
  const result = await formRef.value?.validate()
  if (!result?.valid) return
  saving.value = true
  fieldErrors.value = {}
  generalError.value = ''
  const data = {
    reason: reason.value,
    transit_days: Number(transitDays.value),
    notes: notes.value,
    keywords: keywords.value,
  }
  try {
    const saved = props.transfer
      ? await updateTransfer(props.transfer.id, data)
      : await createTransfer({
          ...data,
          origin: origin.value ?? undefined,
          destination: destination.value ?? undefined,
        })
    emit('saved', saved)
    open.value = false
  } catch (error) {
    if (error instanceof ApiError) {
      const body = (error.data ?? {}) as { field?: string; detail?: string }
      const errors = error.fieldErrors()
      if (body.field && body.detail) {
        fieldErrors.value = { [body.field]: [body.detail] }
        if (!['origin', 'destination', 'reason', 'transit_days'].includes(body.field))
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
</script>

<template>
  <FormDialog
    ref="formRef"
    v-model="open"
    :title="editing ? $t('inventory.transfers.edit') : $t('inventory.transfers.new')"
    :subtitle="
      transfer ? `${transfer.code} · ${transfer.origin_code} → ${transfer.destination_code}` : ''
    "
    icon="mdi-swap-horizontal"
    max-width="640"
    :persistent="saving"
    @submit="submit"
  >
    <v-row dense>
      <v-col cols="12" md="6">
        <v-select
          v-model="origin"
          :items="warehouseOptions"
          :label="$t('inventory.transfers.origin')"
          :rules="required"
          :disabled="editing"
          :error-messages="fieldErrors.origin"
          data-testid="transfer-origin"
        />
      </v-col>
      <v-col cols="12" md="6">
        <v-select
          v-model="destination"
          :items="warehouseOptions.filter((w) => w.value !== origin)"
          :label="$t('inventory.transfers.destination')"
          :rules="required"
          :disabled="editing"
          :error-messages="fieldErrors.destination"
          data-testid="transfer-destination"
        />
      </v-col>
      <v-col cols="12" md="9">
        <v-text-field
          v-model="reason"
          :label="$t('inventory.transfers.reason')"
          :rules="required"
          :error-messages="fieldErrors.reason"
          data-testid="transfer-reason"
        />
      </v-col>
      <v-col cols="12" md="3">
        <v-text-field
          v-model="transitDays"
          :label="$t('inventory.transfers.transitDays')"
          inputmode="numeric"
          :rules="days"
          :error-messages="fieldErrors.transit_days"
          data-testid="transfer-days"
        />
      </v-col>
      <v-col cols="12">
        <v-textarea v-model="notes" :label="$t('inventory.transfers.notes')" rows="2" auto-grow />
      </v-col>
      <v-col cols="12">
        <KeywordsField v-model="keywords" :error-messages="fieldErrors.keywords" />
      </v-col>
    </v-row>
    <v-alert v-if="generalError" type="error" variant="tonal" density="compact" class="mt-2">
      {{ generalError }}
    </v-alert>
    <template #actions>
      <v-btn variant="text" :disabled="saving" @click="open = false">{{
        $t('common.cancel')
      }}</v-btn>
      <v-btn
        type="submit"
        color="primary"
        variant="flat"
        :loading="saving"
        data-testid="transfer-save"
        >{{ editing ? $t('common.save') : $t('inventory.transfers.create') }}</v-btn
      >
    </template>
  </FormDialog>
</template>
