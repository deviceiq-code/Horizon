<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import { useValidationRules } from '@/composables/useValidationRules'
import { listAccountManagers } from '@/modules/account-managers/api'
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
  'account_manager',
  'is_active',
  'notes',
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
    account_manager: null,
    is_active: true,
    notes: '',
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

// --- Account manager picker (searches the server as the user types) -------------------------

interface ManagerOption {
  id: number
  full_name: string
}

const managerOptions = ref<ManagerOption[]>([])
const managerLoading = ref(false)
let managerTimer: ReturnType<typeof setTimeout> | undefined
let managerRequest = 0

async function fetchManagers(term: string) {
  const request = ++managerRequest
  managerLoading.value = true
  try {
    const data = await listAccountManagers({
      page: 1,
      pageSize: 20,
      search: term,
      ordering: 'full_name',
    })
    if (request !== managerRequest) return
    // Keep the selected manager in the list so its name stays visible
    const selected = managerOptions.value.find((m) => m.id === form.value.account_manager)
    const results = data.results.map(({ id, full_name }) => ({ id, full_name }))
    managerOptions.value =
      selected && !results.some((m) => m.id === selected.id) ? [selected, ...results] : results
  } catch {
    /* keep the current options; the field still works with what is loaded */
  } finally {
    if (request === managerRequest) managerLoading.value = false
  }
}

function onManagerSearch(term: string | null) {
  clearTimeout(managerTimer)
  const selected = managerOptions.value.find((m) => m.id === form.value.account_manager)
  // Vuetify sets the search text to the selected item's name; no need to search for it
  if (term && selected && term === selected.full_name) return
  managerTimer = setTimeout(() => fetchManagers(term ?? ''), 300)
}

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
    account_manager: c.account_manager,
    is_active: c.is_active,
    notes: c.notes,
  }
}

watch(open, (isOpen) => {
  if (!isOpen) return
  const c = props.customer
  form.value = c ? toInput(c) : emptyForm()
  managerOptions.value =
    c?.account_manager && c.account_manager_name
      ? [{ id: c.account_manager, full_name: c.account_manager_name }]
      : []
  fieldErrors.value = {}
  generalError.value = ''
  fetchManagers('')
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
  <v-dialog v-model="open" max-width="880" scrollable :persistent="saving">
    <v-card :title="isEdit ? $t('customers.edit') : $t('customers.new')">
      <v-form
        ref="formRef"
        class="d-flex flex-column"
        style="min-height: 0"
        @submit.prevent="submit"
      >
        <v-card-text>
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
              />
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
                @update:model-value="clearError('trade_name')"
              />
            </v-col>
            <v-col cols="12" md="4">
              <v-text-field
                v-model="form.tax_id"
                :label="
                  isBrazil ? $t('customers.fields.taxIdBrazil') : $t('customers.fields.taxId')
                "
                :rules="[rules.required, rules.maxLength(30)]"
                :error-messages="fieldErrors.tax_id"
                maxlength="30"
                data-testid="tax-id"
                @update:model-value="clearError('tax_id')"
              />
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
                  isBrazil
                    ? $t('customers.fields.postalCodeBrazil')
                    : $t('customers.fields.postalCode')
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
              <v-autocomplete
                v-model="form.account_manager"
                :items="managerOptions"
                item-title="full_name"
                item-value="id"
                :label="$t('customers.fields.accountManager')"
                :loading="managerLoading"
                :error-messages="fieldErrors.account_manager"
                :no-data-text="$t('customers.noAccountManagers')"
                no-filter
                clearable
                data-testid="account-manager"
                @update:search="onManagerSearch"
                @update:model-value="clearError('account_manager')"
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
        </v-card-text>

        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" :disabled="saving" @click="open = false">
            {{ $t('common.cancel') }}
          </v-btn>
          <v-btn type="submit" color="primary" variant="flat" :loading="saving" data-testid="save">
            {{ $t('common.save') }}
          </v-btn>
        </v-card-actions>
      </v-form>
    </v-card>
  </v-dialog>
</template>
