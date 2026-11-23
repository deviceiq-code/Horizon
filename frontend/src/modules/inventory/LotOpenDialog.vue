<script setup lang="ts">
/**
 * A vehicle arrived: open its lot. From a receiving appointment (customer and warehouse come
 * from it; its expected list stays hidden — blind count) or unscheduled (choose the warehouse
 * and the customer). The dock where the triage happens is read with the gun.
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import FormDialog from '@/components/FormDialog.vue'
import { useValidationRules } from '@/composables/useValidationRules'
import { listWarehouses, type Warehouse } from '@/modules/warehouses/api'
import CustomerSelect from './CustomerSelect.vue'
import { openLot, type Appointment, type Lot } from './api'

const props = defineProps<{ appointment: Appointment | null }>()
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ opened: [lot: Lot] }>()

const { t } = useI18n()
const rules = useValidationRules()

const warehouses = ref<Warehouse[]>([])
const warehouseId = ref<number | null>(null)
const customer = ref<number | null>(null)
const dockCode = ref('')
const fiscalNumber = ref('')
const notes = ref('')
const fieldErrors = ref<Record<string, string[]>>({})
const generalError = ref('')
const saving = ref(false)
const openCount = ref(0)
const formRef = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(null)

const warehouseOptions = computed(() =>
  warehouses.value.map((w) => ({ value: w.id, title: `${w.code} · ${w.name}` })),
)
const required = [(v: unknown) => (v !== null && v !== undefined) || t('validation.required')]

watch(open, async (isOpen) => {
  if (!isOpen) return
  customer.value = null
  dockCode.value = ''
  fiscalNumber.value = ''
  notes.value = ''
  fieldErrors.value = {}
  generalError.value = ''
  openCount.value += 1
  if (!props.appointment && !warehouses.value.length) {
    try {
      warehouses.value = (
        await listWarehouses({ page: 1, pageSize: 200, ordering: 'name' })
      ).results
      warehouseId.value = warehouses.value[0]?.id ?? null
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
  try {
    const lot = await openLot({
      ...(props.appointment
        ? { appointment: props.appointment.id }
        : { warehouse: warehouseId.value, customer: customer.value }),
      dock_code: dockCode.value,
      fiscal_document_number: fiscalNumber.value,
      notes: notes.value,
    })
    emit('opened', lot)
    open.value = false
  } catch (error) {
    if (error instanceof ApiError) {
      const body = (error.data ?? {}) as { field?: string; detail?: string }
      const errors = error.fieldErrors()
      if (body.field && body.detail) {
        const field = body.field === 'dock' ? 'dock_code' : body.field
        fieldErrors.value = { [field]: [body.detail] }
        if (!['dock_code', 'customer', 'warehouse'].includes(field))
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
    :title="$t('inventory.lots.open')"
    :subtitle="
      appointment
        ? `${appointment.code} · ${appointment.customer_name ?? ''}`
        : $t('inventory.lots.unscheduled')
    "
    icon="mdi-truck-check-outline"
    max-width="640"
    :persistent="saving"
    @submit="submit"
  >
    <v-row dense>
      <template v-if="!appointment">
        <v-col cols="12" md="5">
          <v-select
            v-model="warehouseId"
            :items="warehouseOptions"
            :label="$t('inventory.fields.warehouse')"
            :rules="required"
            :error-messages="fieldErrors.warehouse"
            data-testid="lot-warehouse"
          />
        </v-col>
        <v-col cols="12" md="7">
          <CustomerSelect
            :key="`customer-${openCount}`"
            v-model="customer"
            :label="$t('inventory.appointments.customer')"
            :rules="required"
            :error-messages="fieldErrors.customer"
            data-testid="lot-customer"
          />
        </v-col>
      </template>
      <v-col cols="12" md="6">
        <v-text-field
          v-model="dockCode"
          :label="$t('inventory.lots.dock')"
          :hint="$t('inventory.lots.dockHint')"
          persistent-hint
          :rules="[rules.required]"
          :error-messages="fieldErrors.dock_code"
          prepend-inner-icon="mdi-barcode-scan"
          autocomplete="off"
          autofocus
          data-testid="lot-dock"
        />
      </v-col>
      <v-col cols="12" md="6">
        <v-text-field
          v-model="fiscalNumber"
          :label="$t('inventory.lots.fiscalNumber')"
          maxlength="60"
          data-testid="lot-fiscal"
        />
      </v-col>
      <v-col cols="12">
        <v-textarea v-model="notes" :label="$t('customers.fields.notes')" rows="2" auto-grow />
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
        {{ $t('inventory.lots.openButton') }}
      </v-btn>
    </template>
  </FormDialog>
</template>
