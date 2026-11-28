<script setup lang="ts">
/**
 * A new disposal (kind and warehouse, then who it is for) or its header while open: the
 * customer (the lessee), the buyer of a third-party sale (an entity with the Buyer role), the
 * contract of a relocation, the provider of a discard, a shipping appointment, notes, keywords.
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import FormDialog from '@/components/FormDialog.vue'
import KeywordsField from '@/components/KeywordsField.vue'
import { useDateFormat } from '@/composables/useDateFormat'
import ServiceProviderPicker from '@/modules/service-providers/ServiceProviderPicker.vue'
import { listWarehouses, type Warehouse } from '@/modules/warehouses/api'
import BuyerPicker from '@/modules/business-entities/BuyerPicker.vue'
import CustomerSelect from './CustomerSelect.vue'
import {
  CUSTOMER_KINDS,
  DISPOSAL_KINDS,
  createDisposal,
  listAppointments,
  updateDisposal,
  type Appointment,
  type DisposalDetail,
  type DisposalKind,
} from './api'

const props = defineProps<{ disposal: DisposalDetail | null }>()
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ saved: [disposal: DisposalDetail] }>()

const { t } = useI18n()
const { d } = useDateFormat()

const warehouses = ref<Warehouse[]>([])
const appointments = ref<Appointment[]>([])
const kind = ref<DisposalKind>('lessee_sale')
const warehouseId = ref<number | null>(null)
const customer = ref<number | null>(null)
const buyer = ref<number | null>(null)
const contract = ref('')
const provider = ref<number | null>(null)
const appointment = ref<number | null>(null)
const notes = ref('')
const keywords = ref<string[]>([])
const fieldErrors = ref<Record<string, string[]>>({})
const generalError = ref('')
const saving = ref(false)
const openCount = ref(0)
const formRef = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(null)

const editing = computed(() => props.disposal !== null)
const kindOptions = computed(() =>
  DISPOSAL_KINDS.map((value) => ({ value, title: t(`inventory.disposals.kinds.${value}`) })),
)
const warehouseOptions = computed(() =>
  warehouses.value.map((w) => ({ value: w.id, title: `${w.code} · ${w.name}` })),
)
const appointmentOptions = computed(() => [
  { value: null, title: t('inventory.disposals.noAppointment') },
  ...appointments.value.map((a) => ({
    value: a.id,
    title: `${a.code} · ${d(new Date(a.starts_at), 'dateTime')}`,
  })),
])
const hasCustomer = computed(() => CUSTOMER_KINDS.includes(kind.value))
const hasBuyer = computed(() => kind.value === 'third_party_sale')
const required = [(v: unknown) => (v !== null && v !== undefined) || t('validation.required')]

async function loadAppointments() {
  appointments.value = []
  if (!warehouseId.value) return
  try {
    const data = await listAppointments({
      page: 1,
      pageSize: 100,
      filters: { kind: 'shipping', warehouse: warehouseId.value },
    })
    appointments.value = data.results.filter(
      (a) =>
        !['done', 'cancelled', 'no_show'].includes(a.status) ||
        a.id === props.disposal?.appointment,
    )
  } catch {
    // Without appointments, the field offers none
  }
}

watch(open, async (isOpen) => {
  if (!isOpen) return
  const current = props.disposal
  kind.value = (current?.kind as DisposalKind) ?? 'lessee_sale'
  customer.value = current?.customer ?? null
  buyer.value = current?.buyer ?? null
  contract.value = current?.contract ?? ''
  provider.value = current?.discard_provider ?? null
  appointment.value = current?.appointment ?? null
  notes.value = current?.notes ?? ''
  keywords.value = [...(current?.keywords ?? [])]
  fieldErrors.value = {}
  generalError.value = ''
  openCount.value += 1
  if (!warehouses.value.length) {
    try {
      warehouses.value = (
        await listWarehouses({ page: 1, pageSize: 200, ordering: 'name' })
      ).results
    } catch {
      generalError.value = t('common.loadError')
    }
  }
  warehouseId.value = current?.warehouse ?? warehouses.value[0]?.id ?? null
  await loadAppointments()
})
watch(warehouseId, (now, before) => {
  if (before !== null && now !== before) {
    appointment.value = null
    loadAppointments()
  }
})

async function submit() {
  const result = await formRef.value?.validate()
  if (!result?.valid) return
  saving.value = true
  fieldErrors.value = {}
  generalError.value = ''
  const data = {
    customer: hasCustomer.value ? customer.value : null,
    buyer: hasBuyer.value ? buyer.value : null,
    contract: kind.value === 'relocation' ? contract.value : '',
    discard_provider: kind.value === 'discard' ? provider.value : null,
    appointment: appointment.value,
    notes: notes.value,
    keywords: keywords.value,
  }
  try {
    const saved = props.disposal
      ? await updateDisposal(props.disposal.id, data)
      : await createDisposal({
          ...data,
          kind: kind.value,
          warehouse: warehouseId.value ?? undefined,
        })
    emit('saved', saved)
    open.value = false
  } catch (error) {
    if (error instanceof ApiError) {
      const body = (error.data ?? {}) as { field?: string; detail?: string }
      const errors = error.fieldErrors()
      if (body.field && body.detail) {
        fieldErrors.value = { [body.field]: [body.detail] }
        if (!['customer', 'buyer', 'discard_provider', 'appointment', 'kind'].includes(body.field))
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
    :title="editing ? $t('inventory.disposals.edit') : $t('inventory.disposals.new')"
    :subtitle="
      disposal ? `${disposal.code} · ${$t(`inventory.disposals.kinds.${disposal.kind}`)}` : ''
    "
    icon="mdi-truck-delivery-outline"
    max-width="720"
    :persistent="saving"
    @submit="submit"
  >
    <v-row dense>
      <v-col cols="12" md="6">
        <v-select
          v-model="kind"
          :items="kindOptions"
          :label="$t('inventory.disposals.kind')"
          :disabled="editing"
          :error-messages="fieldErrors.kind"
          data-testid="disposal-kind"
        />
      </v-col>
      <v-col cols="12" md="6">
        <v-select
          v-model="warehouseId"
          :items="warehouseOptions"
          :label="$t('inventory.fields.warehouse')"
          :rules="required"
          :disabled="editing"
          :error-messages="fieldErrors.warehouse"
          data-testid="disposal-warehouse"
        />
      </v-col>
      <v-col v-if="hasCustomer" cols="12" :md="kind === 'relocation' ? 8 : 12">
        <CustomerSelect
          :key="`customer-${openCount}-${kind}`"
          v-model="customer"
          :label="$t('inventory.appointments.customer')"
          :initial-option="
            disposal?.customer
              ? { id: disposal.customer, name: disposal.customer_name ?? '' }
              : null
          "
          :rules="required"
          :error-messages="fieldErrors.customer"
          data-testid="disposal-customer"
        />
      </v-col>
      <v-col v-if="hasBuyer" cols="12">
        <BuyerPicker
          :key="`buyer-${openCount}`"
          v-model="buyer"
          :label="$t('inventory.disposals.buyer')"
          :initial-option="
            disposal?.buyer ? { id: disposal.buyer, name: disposal.buyer_name ?? '' } : null
          "
          :rules="required"
          :error-messages="fieldErrors.buyer"
          data-testid="disposal-buyer"
        />
      </v-col>
      <v-col v-if="kind === 'relocation'" cols="12" md="4">
        <v-text-field
          v-model="contract"
          :label="$t('inventory.disposals.contract')"
          :error-messages="fieldErrors.contract"
          data-testid="disposal-contract"
        />
      </v-col>
      <v-col v-if="kind === 'discard'" cols="12">
        <ServiceProviderPicker
          :key="`provider-${openCount}`"
          v-model="provider"
          service="disposal"
          :initial-option="
            disposal?.discard_provider
              ? { id: disposal.discard_provider, name: disposal.discard_provider_name ?? '' }
              : null
          "
          :label="$t('inventory.disposals.discardProvider')"
          :rules="required"
          :error-messages="fieldErrors.discard_provider"
          data-testid="disposal-provider"
        />
      </v-col>
      <v-col cols="12">
        <v-select
          v-model="appointment"
          :items="appointmentOptions"
          :label="$t('inventory.disposals.appointment')"
          :hint="$t('inventory.disposals.appointmentHint')"
          persistent-hint
          :error-messages="fieldErrors.appointment"
        />
      </v-col>
      <v-col cols="12">
        <v-textarea v-model="notes" :label="$t('inventory.disposals.notes')" rows="2" auto-grow />
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
        data-testid="disposal-save"
        >{{ editing ? $t('common.save') : $t('inventory.disposals.create') }}</v-btn
      >
    </template>
  </FormDialog>
</template>
