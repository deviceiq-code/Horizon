<script setup lang="ts">
/** Create (warehouse = null) or edit a warehouse: own, or outsourced to a service provider of
 * warehousing (picked here; only active providers offering it are listed). */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import AddressFields from '@/components/AddressFields.vue'
import FormDialog from '@/components/FormDialog.vue'
import KeywordsField from '@/components/KeywordsField.vue'
import { useValidationRules } from '@/composables/useValidationRules'
import { formatPostalCode } from '@/modules/customers/format'
import VerticalPicker from '@/modules/catalogs/verticals/VerticalPicker.vue'
import ServiceProviderPicker from '@/modules/service-providers/ServiceProviderPicker.vue'
import { countryOptions } from '@/utils/countries'
import { createWarehouse, updateWarehouse, type Warehouse, type WarehouseInput } from './api'

const props = defineProps<{ warehouse: Warehouse | null }>()
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ saved: [warehouse: Warehouse, created: boolean] }>()

const { t, locale } = useI18n()
const rules = useValidationRules()

function emptyForm(): WarehouseInput {
  return {
    name: '',
    ownership: 'own',
    service_provider: null,
    verticals: [],
    contact_name: '',
    email: '',
    phone: '',
    country: 'BR',
    postal_code: '',
    street: '',
    number: '',
    complement: '',
    district: '',
    city: '',
    state: '',
    is_active: true,
    notes: '',
    keywords: [],
  }
}

function toInput(w: Warehouse): WarehouseInput {
  return {
    name: w.name,
    ownership: w.ownership,
    service_provider: w.service_provider,
    verticals: [...w.verticals],
    contact_name: w.contact_name,
    email: w.email,
    phone: w.phone,
    country: w.country,
    street: w.street,
    number: w.number,
    complement: w.complement,
    district: w.district,
    city: w.city,
    state: w.state,
    is_active: w.is_active,
    notes: w.notes,
    postal_code: formatPostalCode(w.postal_code, w.country),
    keywords: [...w.keywords],
  }
}

const form = ref<WarehouseInput>(emptyForm())
const fieldErrors = ref<Record<string, string[]>>({})
const generalError = ref('')
const saving = ref(false)
const formRef = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(null)
// The provider picker starts fresh (remount) every time the dialog opens
const openCount = ref(0)

const isEdit = computed(() => props.warehouse !== null)
const outsourced = computed(() => form.value.ownership === 'outsourced')
const countries = computed(() => countryOptions(locale.value))
const verticalsRules = [
  (v: unknown) => (Array.isArray(v) && v.length > 0) || t('warehouses.verticalsRequired'),
]
const providerRules = [(v: unknown) => typeof v === 'number' || t('validation.required')]

watch(open, (isOpen) => {
  if (!isOpen) return
  form.value = props.warehouse ? toInput(props.warehouse) : emptyForm()
  fieldErrors.value = {}
  generalError.value = ''
  openCount.value += 1
})

function onOwnershipChange() {
  clearError('ownership')
  clearError('service_provider')
}

async function submit() {
  const result = await formRef.value?.validate()
  if (!result?.valid) return

  saving.value = true
  fieldErrors.value = {}
  generalError.value = ''
  try {
    // Own warehouses have no provider
    const data = {
      ...form.value,
      service_provider: outsourced.value ? form.value.service_provider : null,
    }
    const saved = props.warehouse
      ? await updateWarehouse(props.warehouse.id, data)
      : await createWarehouse(data)
    emit('saved', saved, !props.warehouse)
    open.value = false
  } catch (error) {
    const errors = error instanceof ApiError ? error.fieldErrors() : {}
    const known = Object.keys(errors).filter((key) => key in form.value)
    if (known.length) fieldErrors.value = errors
    else generalError.value = t('common.saveError')
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
    :audit="warehouse"
    ref="formRef"
    v-model="open"
    :title="isEdit ? $t('warehouses.edit') : $t('warehouses.new')"
    :subtitle="warehouse ? `${warehouse.code} · ${warehouse.name}` : null"
    icon="mdi-warehouse"
    max-width="880"
    :persistent="saving"
    @submit="submit"
  >
    <!-- Identification and who runs it -->
    <div class="text-subtitle-2 text-medium-emphasis mb-2">
      {{ $t('customers.sections.identification') }}
    </div>
    <p v-if="!isEdit" class="text-caption text-medium-emphasis mb-2" data-testid="code-hint">
      {{ $t('warehouses.codeHint') }}
    </p>
    <v-row dense>
      <v-col cols="12" md="7">
        <v-text-field
          v-model="form.name"
          :label="$t('warehouses.fields.name')"
          :rules="[rules.required, rules.maxLength(100)]"
          :error-messages="fieldErrors.name"
          maxlength="100"
          autofocus
          data-testid="name"
          @update:model-value="clearError('name')"
        />
      </v-col>
      <v-col cols="12" md="5">
        <v-btn-toggle
          v-model="form.ownership"
          mandatory
          color="primary"
          variant="outlined"
          divided
          class="w-100"
          data-testid="ownership"
          @update:model-value="onOwnershipChange"
        >
          <v-btn value="own" prepend-icon="mdi-home-city-outline" class="flex-grow-1">
            {{ $t('warehouses.ownership.own') }}
          </v-btn>
          <v-btn value="outsourced" prepend-icon="mdi-handshake-outline" class="flex-grow-1">
            {{ $t('warehouses.ownership.outsourced') }}
          </v-btn>
        </v-btn-toggle>
      </v-col>
      <v-col v-if="outsourced" cols="12">
        <ServiceProviderPicker
          :key="`provider-${openCount}`"
          v-model="form.service_provider"
          service="warehousing"
          :initial-option="warehouse?.service_provider_detail ?? null"
          :label="$t('warehouses.fields.serviceProvider')"
          :rules="providerRules"
          :error-messages="fieldErrors.service_provider"
          data-testid="service-provider"
          @update:model-value="clearError('service_provider')"
        />
        <div class="text-caption text-medium-emphasis mt-n2 mb-2">
          {{ $t('warehouses.serviceProviderHint') }}
        </div>
      </v-col>
    </v-row>

    <!-- Business verticals it serves -->
    <div class="text-subtitle-2 text-medium-emphasis mb-2 mt-2">
      {{ $t('warehouses.fields.verticals') }}
    </div>
    <VerticalPicker
      :key="`verticals-${openCount}`"
      v-model="form.verticals"
      multiple
      :initial-options="warehouse?.verticals_detail ?? []"
      :label="$t('warehouses.fields.verticals')"
      :rules="verticalsRules"
      :error-messages="fieldErrors.verticals"
      data-testid="verticals"
      @update:model-value="clearError('verticals')"
    />

    <!-- Contact on site -->
    <div class="text-subtitle-2 text-medium-emphasis mb-2 mt-2">
      {{ $t('customers.sections.contact') }}
    </div>
    <v-row dense>
      <v-col cols="12" md="4">
        <v-text-field
          v-model="form.contact_name"
          :label="$t('warehouses.fields.contactName')"
          :rules="[rules.maxLength(150)]"
          :error-messages="fieldErrors.contact_name"
          maxlength="150"
          @update:model-value="clearError('contact_name')"
        />
      </v-col>
      <v-col cols="12" md="5">
        <v-text-field
          v-model="form.email"
          :label="$t('customers.fields.email')"
          type="email"
          :rules="[rules.email, rules.maxLength(254)]"
          :error-messages="fieldErrors.email"
          maxlength="254"
          @update:model-value="clearError('email')"
        />
      </v-col>
      <v-col cols="12" md="3">
        <v-text-field
          v-model="form.phone"
          :label="$t('customers.fields.phone')"
          type="tel"
          :rules="[rules.maxLength(30)]"
          :error-messages="fieldErrors.phone"
          maxlength="30"
          @update:model-value="clearError('phone')"
        />
      </v-col>
    </v-row>

    <!-- Address -->
    <div class="text-subtitle-2 text-medium-emphasis mb-2 mt-2">
      {{ $t('customers.sections.address') }}
    </div>
    <v-row dense>
      <v-col cols="12" md="4">
        <v-autocomplete
          v-model="form.country"
          :items="countries"
          item-title="name"
          item-value="code"
          :label="$t('customers.fields.country')"
          :error-messages="fieldErrors.country"
          @update:model-value="clearError('country')"
        />
      </v-col>
    </v-row>
    <AddressFields
      v-model="form"
      :country="form.country"
      :errors="fieldErrors"
      @clear="clearError"
    />

    <!-- Other -->
    <v-row dense class="mt-2">
      <v-col cols="12">
        <v-switch
          v-model="form.is_active"
          :label="$t('warehouses.fields.active')"
          color="primary"
          hide-details
          inset
        />
      </v-col>
      <v-col cols="12">
        <KeywordsField
          v-model="form.keywords"
          :error-messages="fieldErrors.keywords"
          data-testid="keywords"
          @update:model-value="clearError('keywords')"
        />
      </v-col>
      <v-col cols="12">
        <v-textarea
          v-model="form.notes"
          :label="$t('customers.fields.notes')"
          :error-messages="fieldErrors.notes"
          rows="3"
          auto-grow
          @update:model-value="clearError('notes')"
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
