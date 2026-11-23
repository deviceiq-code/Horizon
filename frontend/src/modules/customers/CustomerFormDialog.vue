<script setup lang="ts">
import FormDialog from '@/components/FormDialog.vue'
import WebSearchButton from '@/components/WebSearchButton.vue'
import KeywordsField from '@/components/KeywordsField.vue'
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import { useValidationRules } from '@/composables/useValidationRules'
import AccountManagerPicker from '@/modules/account-managers/AccountManagerPicker.vue'
import type { AccountManagerRef } from '@/modules/account-managers/api'
import { countryOptions } from '@/utils/countries'
import { createCustomer, updateCustomer, type Customer, type CustomerInput } from './api'
import { BRAZILIAN_STATES, formatPostalCode, formatTaxId } from './format'

/** Create (customer = null) or edit a customer. */
const props = defineProps<{ customer: Customer | null }>()
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ saved: [customer: Customer, created: boolean] }>()

const { t, locale } = useI18n()
const rules = useValidationRules()

const FIELDS = [
  'name',
  'trade_name',
  'tax_id',
  'country',
  'email',
  'phone',
  'postal_code',
  'street',
  'number',
  'complement',
  'district',
  'city',
  'state',
  'primary_account_manager',
  'secondary_account_managers',
  'is_active',
  'notes',
  'keywords',
] as const

function emptyForm(): CustomerInput {
  return {
    name: '',
    trade_name: '',
    tax_id: '',
    country: 'BR',
    email: '',
    phone: '',
    postal_code: '',
    street: '',
    number: '',
    complement: '',
    district: '',
    city: '',
    state: '',
    primary_account_manager: null,
    secondary_account_managers: [],
    is_active: true,
    notes: '',
    keywords: [],
  }
}

const form = ref<CustomerInput>(emptyForm())
const fieldErrors = ref<Record<string, string[]>>({})
const generalError = ref('')
const saving = ref(false)
const formRef = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(null)

const isEdit = computed(() => props.customer !== null)
const isBrazil = computed(() => form.value.country === 'BR')
const countries = computed(() => countryOptions(locale.value))
const stateOptions: string[] = [...BRAZILIAN_STATES]

// --- Open / reset ----------------------------------------------------------------------------

/** Editable fields of an existing customer, with documents formatted for reading. */
function toInput(c: Customer): CustomerInput {
  return {
    name: c.name,
    trade_name: c.trade_name,
    tax_id: formatTaxId(c.tax_id, c.country),
    country: c.country,
    email: c.email,
    phone: c.phone,
    postal_code: formatPostalCode(c.postal_code, c.country),
    street: c.street,
    number: c.number,
    complement: c.complement,
    district: c.district,
    city: c.city,
    state: c.state,
    primary_account_manager: c.primary_account_manager,
    secondary_account_managers: [...c.secondary_account_managers],
    is_active: c.is_active,
    notes: c.notes,
    keywords: [...c.keywords],
  }
}

// The account manager pickers start fresh (remount) every time the dialog opens
const openCount = ref(0)
const initialPrimary = computed<AccountManagerRef[]>(() => {
  const c = props.customer
  return c?.primary_account_manager
    ? [{ id: c.primary_account_manager, full_name: c.primary_account_manager_name }]
    : []
})
const initialSecondaries = computed(() => props.customer?.secondary_account_managers_detail ?? [])

const primaryRules = [(v: unknown) => (v !== null && v !== undefined) || t('validation.required')]

/** The primary account manager is never also a secondary one. */
function onPrimaryChange(primary: number | number[] | null) {
  clearError('primary_account_manager')
  if (typeof primary === 'number') {
    form.value.secondary_account_managers = form.value.secondary_account_managers.filter(
      (id) => id !== primary,
    )
  }
}

const excludedFromSecondaries = computed(() =>
  form.value.primary_account_manager === null ? [] : [form.value.primary_account_manager],
)

watch(open, (isOpen) => {
  if (!isOpen) return
  const c = props.customer
  form.value = c ? toInput(c) : emptyForm()
  fieldErrors.value = {}
  generalError.value = ''
  openCount.value += 1
})

// --- Save ------------------------------------------------------------------------------------

async function submit() {
  const result = await formRef.value?.validate()
  if (!result?.valid) return

  saving.value = true
  fieldErrors.value = {}
  generalError.value = ''
  try {
    const data = { ...form.value }
    const saved = props.customer
      ? await updateCustomer(props.customer.id, data)
      : await createCustomer(data)
    emit('saved', saved, !props.customer)
    open.value = false
  } catch (error) {
    const errors = error instanceof ApiError ? error.fieldErrors() : {}
    const known = Object.keys(errors).filter((k) => (FIELDS as readonly string[]).includes(k))
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
    :title="isEdit ? $t('customers.edit') : $t('customers.new')"
    :subtitle="customer?.name ?? null"
    icon="mdi-domain"
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
          :label="$t('customers.fields.name')"
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
          data-testid="country"
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
          data-testid="trade-name"
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

    <!-- Contact -->
    <div class="text-subtitle-2 text-medium-emphasis mb-2 mt-2">
      {{ $t('customers.sections.contact') }}
    </div>
    <v-row dense>
      <v-col cols="12" md="8">
        <v-text-field
          v-model="form.email"
          :label="$t('customers.fields.email')"
          type="email"
          :rules="[rules.email, rules.maxLength(254)]"
          :error-messages="fieldErrors.email"
          maxlength="254"
          data-testid="email"
          @update:model-value="clearError('email')"
        />
      </v-col>
      <v-col cols="12" md="4">
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
      <v-col cols="12" sm="4" md="3">
        <v-text-field
          v-model="form.postal_code"
          :label="
            isBrazil ? $t('customers.fields.postalCodeBrazil') : $t('customers.fields.postalCode')
          "
          :rules="[rules.maxLength(10)]"
          :error-messages="fieldErrors.postal_code"
          maxlength="10"
          @update:model-value="clearError('postal_code')"
        />
      </v-col>
      <v-col cols="12" sm="8" md="7">
        <v-text-field
          v-model="form.street"
          :label="$t('customers.fields.street')"
          :rules="[rules.maxLength(200)]"
          :error-messages="fieldErrors.street"
          maxlength="200"
          @update:model-value="clearError('street')"
        />
      </v-col>
      <v-col cols="4" md="2">
        <v-text-field
          v-model="form.number"
          :label="$t('customers.fields.number')"
          :rules="[rules.maxLength(20)]"
          :error-messages="fieldErrors.number"
          maxlength="20"
          @update:model-value="clearError('number')"
        />
      </v-col>
      <v-col cols="8" md="4">
        <v-text-field
          v-model="form.complement"
          :label="$t('customers.fields.complement')"
          :rules="[rules.maxLength(100)]"
          :error-messages="fieldErrors.complement"
          maxlength="100"
          @update:model-value="clearError('complement')"
        />
      </v-col>
      <v-col cols="12" md="3">
        <v-text-field
          v-model="form.district"
          :label="$t('customers.fields.district')"
          :rules="[rules.maxLength(100)]"
          :error-messages="fieldErrors.district"
          maxlength="100"
          @update:model-value="clearError('district')"
        />
      </v-col>
      <v-col cols="8" md="3">
        <v-text-field
          v-model="form.city"
          :label="$t('customers.fields.city')"
          :rules="[rules.maxLength(100)]"
          :error-messages="fieldErrors.city"
          maxlength="100"
          @update:model-value="clearError('city')"
        />
      </v-col>
      <v-col cols="4" md="2">
        <v-autocomplete
          v-if="isBrazil"
          v-model="form.state"
          :items="stateOptions"
          :label="$t('customers.fields.state')"
          :error-messages="fieldErrors.state"
          clearable
          @update:model-value="clearError('state')"
        />
        <v-text-field
          v-else
          v-model="form.state"
          :label="$t('customers.fields.state')"
          :rules="[rules.maxLength(50)]"
          :error-messages="fieldErrors.state"
          maxlength="50"
          @update:model-value="clearError('state')"
        />
      </v-col>
    </v-row>

    <!-- Relationship -->
    <div class="text-subtitle-2 text-medium-emphasis mb-2 mt-2">
      {{ $t('customers.sections.relationship') }}
    </div>
    <v-row dense>
      <v-col cols="12" md="8">
        <AccountManagerPicker
          :key="`primary-${openCount}`"
          v-model="form.primary_account_manager"
          :initial-options="initialPrimary"
          :label="$t('customers.fields.primaryAccountManager')"
          :rules="primaryRules"
          :error-messages="fieldErrors.primary_account_manager"
          :no-data-text="$t('accountManagers.noneFound')"
          prepend-inner-icon="mdi-star"
          data-testid="primary-account-manager"
          @update:model-value="onPrimaryChange"
        />
      </v-col>
      <v-col cols="12" md="4" class="d-flex align-center">
        <v-switch
          v-model="form.is_active"
          :label="$t('customers.fields.active')"
          color="primary"
          hide-details
          inset
        />
      </v-col>
      <v-col cols="12">
        <AccountManagerPicker
          :key="`secondary-${openCount}`"
          v-model="form.secondary_account_managers"
          multiple
          :initial-options="initialSecondaries"
          :exclude="excludedFromSecondaries"
          :label="$t('customers.fields.secondaryAccountManagers')"
          :error-messages="fieldErrors.secondary_account_managers"
          :no-data-text="$t('accountManagers.noneFound')"
          data-testid="secondary-account-managers"
          @update:model-value="clearError('secondary_account_managers')"
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
