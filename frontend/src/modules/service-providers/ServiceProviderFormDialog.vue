<script setup lang="ts">
/** Create (provider = null) or edit a service provider: identification, services, contact and
 * address (as customers'). */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import AddressFields from '@/components/AddressFields.vue'
import FormDialog from '@/components/FormDialog.vue'
import KeywordsField from '@/components/KeywordsField.vue'
import WebSearchButton from '@/components/WebSearchButton.vue'
import { useValidationRules } from '@/composables/useValidationRules'
import { formatPostalCode, formatTaxId } from '@/modules/customers/format'
import { countryOptions } from '@/utils/countries'
import {
  createServiceProvider,
  SERVICE_ICONS,
  SERVICE_KINDS,
  updateServiceProvider,
  type ServiceProvider,
  type ServiceProviderInput,
} from './api'

const props = defineProps<{ provider: ServiceProvider | null }>()
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ saved: [provider: ServiceProvider, created: boolean] }>()

const { t, locale } = useI18n()
const rules = useValidationRules()

function emptyForm(): ServiceProviderInput {
  return {
    name: '',
    trade_name: '',
    tax_id: '',
    country: 'BR',
    services: [],
    contact_name: '',
    email: '',
    phone: '',
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

/** Editable fields of an existing provider, with documents formatted for reading. */
function toInput(p: ServiceProvider): ServiceProviderInput {
  return {
    name: p.name,
    trade_name: p.trade_name,
    country: p.country,
    contact_name: p.contact_name,
    email: p.email,
    phone: p.phone,
    street: p.street,
    number: p.number,
    complement: p.complement,
    district: p.district,
    city: p.city,
    state: p.state,
    is_active: p.is_active,
    notes: p.notes,
    tax_id: formatTaxId(p.tax_id, p.country),
    postal_code: formatPostalCode(p.postal_code, p.country),
    services: [...p.services],
    keywords: [...p.keywords],
  }
}

const form = ref<ServiceProviderInput>(emptyForm())
const fieldErrors = ref<Record<string, string[]>>({})
const generalError = ref('')
const saving = ref(false)
const formRef = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(null)

const isEdit = computed(() => props.provider !== null)
const isBrazil = computed(() => form.value.country === 'BR')
const countries = computed(() => countryOptions(locale.value))

const servicesRules = [
  (v: unknown) => (Array.isArray(v) && v.length > 0) || t('serviceProviders.servicesRequired'),
]

watch(open, (isOpen) => {
  if (!isOpen) return
  form.value = props.provider ? toInput(props.provider) : emptyForm()
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
    const data = { ...form.value }
    const saved = props.provider
      ? await updateServiceProvider(props.provider.id, data)
      : await createServiceProvider(data)
    emit('saved', saved, !props.provider)
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
    ref="formRef"
    v-model="open"
    :title="isEdit ? $t('serviceProviders.edit') : $t('serviceProviders.new')"
    :subtitle="provider?.name ?? null"
    icon="mdi-account-hard-hat-outline"
    max-width="880"
    :persistent="saving"
    @submit="submit"
  >
    <!-- Identification -->
    <div class="text-subtitle-2 text-medium-emphasis mb-2">
      {{ $t('customers.sections.identification') }}
    </div>
    <v-row dense>
      <v-col cols="12" md="8">
        <v-text-field
          v-model="form.name"
          :label="$t('serviceProviders.fields.name')"
          :rules="[rules.required, rules.maxLength(200)]"
          :error-messages="fieldErrors.name"
          maxlength="200"
          autofocus
          data-testid="name"
          @update:model-value="clearError('name')"
        >
          <template #append-inner><WebSearchButton :term="form.name" /></template>
        </v-text-field>
      </v-col>
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
      <v-col cols="12" md="8">
        <v-text-field
          v-model="form.trade_name"
          :label="$t('customers.fields.tradeName')"
          :rules="[rules.maxLength(200)]"
          :error-messages="fieldErrors.trade_name"
          maxlength="200"
          @update:model-value="clearError('trade_name')"
        >
          <template #append-inner><WebSearchButton :term="form.trade_name" /></template>
        </v-text-field>
      </v-col>
      <v-col cols="12" md="4">
        <v-text-field
          v-model="form.tax_id"
          :label="isBrazil ? $t('customers.fields.taxIdBrazil') : $t('customers.fields.taxId')"
          :rules="[rules.required, rules.maxLength(30)]"
          :error-messages="fieldErrors.tax_id"
          maxlength="30"
          data-testid="tax-id"
          @update:model-value="clearError('tax_id')"
        >
          <template #append-inner><WebSearchButton :term="form.tax_id" /></template>
        </v-text-field>
      </v-col>
    </v-row>

    <!-- Services it can provide (at least one) -->
    <div class="text-subtitle-2 text-medium-emphasis mb-1 mt-2">
      {{ $t('serviceProviders.fields.services') }}
    </div>
    <v-input
      :model-value="form.services"
      :rules="servicesRules"
      :error-messages="fieldErrors.services"
      class="mb-2"
    >
      <v-chip-group
        v-model="form.services"
        multiple
        column
        selected-class="text-primary"
        data-testid="services"
        @update:model-value="clearError('services')"
      >
        <v-chip
          v-for="kind in SERVICE_KINDS"
          :key="kind"
          :value="kind"
          :prepend-icon="SERVICE_ICONS[kind]"
          variant="outlined"
          filter
          :data-testid="`service-${kind}`"
        >
          {{ $t(`serviceProviders.services.${kind}`) }}
        </v-chip>
      </v-chip-group>
    </v-input>

    <!-- Contact -->
    <div class="text-subtitle-2 text-medium-emphasis mb-2 mt-2">
      {{ $t('customers.sections.contact') }}
    </div>
    <v-row dense>
      <v-col cols="12" md="4">
        <v-text-field
          v-model="form.contact_name"
          :label="$t('serviceProviders.fields.contactName')"
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
          :label="$t('serviceProviders.fields.active')"
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
