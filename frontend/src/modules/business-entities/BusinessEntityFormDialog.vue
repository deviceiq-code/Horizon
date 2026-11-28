<script setup lang="ts">
/**
 * Create (entity = null) or edit a business entity and its roles. The first tab is the entity
 * — identification, head office (another entity; a Brazilian CNPJ suggests the one with the
 * same root), contact, address, its roles (switches), keywords and notes; each role turned on
 * opens a tab of its own with that role's data and "active". Saved together: a role turned off
 * is removed (the server refuses, 409, when records point to it — deactivate it instead).
 */
import AddressFields from '@/components/AddressFields.vue'
import FormDialog from '@/components/FormDialog.vue'
import KeywordsField from '@/components/KeywordsField.vue'
import WebSearchButton from '@/components/WebSearchButton.vue'
import { computed, nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import { useValidationRules } from '@/composables/useValidationRules'
import AccountManagerPicker from '@/modules/account-managers/AccountManagerPicker.vue'
import type { AccountManagerRef } from '@/modules/account-managers/api'
import { formatPostalCode, formatTaxId } from '@/modules/customers/format'
import { SERVICE_ICONS, SERVICE_KINDS, type ServiceKind } from '@/modules/service-providers/api'
import { countryOptions } from '@/utils/countries'
import EntityPicker from './EntityPicker.vue'
import {
  CONTRACT_TYPES,
  createBusinessEntity,
  ENTITY_ROLES,
  parentSuggestion,
  ROLE_ICONS,
  SUPPLY_KINDS,
  updateBusinessEntity,
  type BusinessEntity,
  type BusinessEntityInput,
  type ContractType,
  type EntityRef,
  type EntityRole,
  type SupplyKind,
} from './api'

const props = withDefaults(
  defineProps<{
    entity: BusinessEntity | null
    /** A new entity starts with this role (New in a role's tab) */
    startRole?: EntityRole | null
  }>(),
  { startRole: null },
)
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ saved: [entity: BusinessEntity, created: boolean] }>()

const { t, locale } = useI18n()
const rules = useValidationRules()

type EntityFields = Omit<
  BusinessEntityInput,
  'customer' | 'supplier' | 'service_provider' | 'buyer'
>

function emptyForm(): EntityFields {
  return {
    name: '',
    trade_name: '',
    tax_id: '',
    country: 'BR',
    parent: null,
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

/** Each role's data as edited (kept while switched off, so turning it back on restores it) */
interface RoleForms {
  customer: {
    is_active: boolean
    contract_types: ContractType[]
    primary_account_manager: number | null
    secondary_account_managers: number[]
  }
  supplier: { is_active: boolean; supplies: SupplyKind[] }
  service_provider: { is_active: boolean; services: ServiceKind[] }
  buyer: { is_active: boolean }
}

function emptyRoles(): RoleForms {
  return {
    customer: {
      is_active: true,
      contract_types: [],
      primary_account_manager: null,
      secondary_account_managers: [],
    },
    supplier: { is_active: true, supplies: [] },
    service_provider: { is_active: true, services: [] },
    buyer: { is_active: true },
  }
}

const form = ref<EntityFields>(emptyForm())
const roleForms = ref<RoleForms>(emptyRoles())
const enabled = ref<Record<EntityRole, boolean>>(
  Object.fromEntries(ENTITY_ROLES.map((r) => [r, false])) as Record<EntityRole, boolean>,
)
const tab = ref<'entity' | EntityRole>('entity')
const fieldErrors = ref<Record<string, string[]>>({})
const roleErrors = ref<Partial<Record<EntityRole, Record<string, string[]>>>>({})
const generalError = ref('')
const saving = ref(false)
const formRef = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(null)
const openCount = ref(0) // remounts the pickers on every open

const isEdit = computed(() => props.entity !== null)
const isBrazil = computed(() => form.value.country === 'BR')
const countries = computed(() => countryOptions(locale.value))
const enabledRoles = computed(() => ENTITY_ROLES.filter((role) => enabled.value[role]))

// --- Open / reset ----------------------------------------------------------------------------

const initialParent = ref<EntityRef | null>(null)
const initialPrimary = ref<AccountManagerRef[]>([])
const initialSecondaries = ref<AccountManagerRef[]>([])

watch(open, (isOpen) => {
  if (!isOpen) return
  const e = props.entity
  form.value = e
    ? {
        name: e.name,
        trade_name: e.trade_name,
        tax_id: formatTaxId(e.tax_id, e.country),
        country: e.country,
        parent: e.parent,
        contact_name: e.contact_name,
        email: e.email,
        phone: e.phone,
        postal_code: formatPostalCode(e.postal_code, e.country),
        street: e.street,
        number: e.number,
        complement: e.complement,
        district: e.district,
        city: e.city,
        state: e.state,
        is_active: e.is_active,
        notes: e.notes,
        keywords: [...e.keywords],
      }
    : emptyForm()
  const roles = emptyRoles()
  if (e?.customer) {
    roles.customer = {
      is_active: e.customer.is_active,
      contract_types: [...e.customer.contract_types],
      primary_account_manager: e.customer.primary_account_manager,
      secondary_account_managers: [...e.customer.secondary_account_managers],
    }
  }
  if (e?.supplier) {
    roles.supplier = { is_active: e.supplier.is_active, supplies: [...e.supplier.supplies] }
  }
  if (e?.service_provider) {
    roles.service_provider = {
      is_active: e.service_provider.is_active,
      services: [...e.service_provider.services],
    }
  }
  if (e?.buyer) roles.buyer = { is_active: e.buyer.is_active }
  roleForms.value = roles
  for (const role of ENTITY_ROLES) {
    enabled.value[role] = e ? e.roles.includes(role) : role === props.startRole
  }
  initialParent.value = e?.parent_detail ?? null
  initialPrimary.value = e?.customer?.primary_account_manager
    ? [
        {
          id: e.customer.primary_account_manager,
          full_name: e.customer.primary_account_manager_name,
        },
      ]
    : []
  initialSecondaries.value = e?.customer?.secondary_account_managers_detail ?? []
  suggestion.value = null
  fieldErrors.value = {}
  roleErrors.value = {}
  generalError.value = ''
  tab.value = 'entity'
  openCount.value += 1
})

// A role turned off while its tab is open: back to the entity
watch(enabledRoles, (roles) => {
  if (tab.value !== 'entity' && !roles.includes(tab.value)) tab.value = 'entity'
})

// --- Head office: the CNPJ's root suggests one -----------------------------------------------

const suggestion = ref<EntityRef | null>(null)

async function suggestParent() {
  suggestion.value = null
  if (!isBrazil.value || form.value.parent !== null || !form.value.tax_id.trim()) return
  try {
    suggestion.value = await parentSuggestion(
      form.value.country,
      form.value.tax_id,
      props.entity?.id,
    )
  } catch {
    // Only a suggestion: the head office can still be chosen
  }
}

function useSuggestion() {
  if (!suggestion.value) return
  initialParent.value = suggestion.value
  form.value.parent = suggestion.value.id
  openCount.value += 1 // the picker shows it
  suggestion.value = null
}

// --- Customer: the primary account manager is never also a secondary one ---------------------

function onPrimaryChange(primary: number | number[] | null) {
  clearRoleError('customer', 'primary_account_manager')
  if (typeof primary === 'number') {
    roleForms.value.customer.secondary_account_managers =
      roleForms.value.customer.secondary_account_managers.filter((id) => id !== primary)
  }
}

const excludedFromSecondaries = computed(() => {
  const primary = roleForms.value.customer.primary_account_manager
  return primary === null ? [] : [primary]
})

const required = (v: unknown) =>
  (v !== null && v !== undefined && !(Array.isArray(v) && !v.length)) || t('validation.required')

// --- Save ------------------------------------------------------------------------------------

function payload(): BusinessEntityInput {
  const data: BusinessEntityInput = { ...form.value }
  for (const role of ENTITY_ROLES) {
    if (enabled.value[role]) {
      Object.assign(data, { [role]: { ...roleForms.value[role] } })
    } else if (props.entity?.roles.includes(role)) {
      Object.assign(data, { [role]: null }) // turned off: removed
    }
  }
  return data
}

/** The first tab with an error: the entity's, then the roles' in order */
async function openTabWithErrors() {
  await nextTick()
  const field = document.querySelector('[data-entity-tab] .v-input--error')
  const name = field?.closest<HTMLElement>('[data-entity-tab]')?.dataset.entityTab
  if (name) tab.value = name as typeof tab.value
}

async function submit() {
  const result = await formRef.value?.validate()
  if (!result?.valid) {
    await openTabWithErrors()
    return
  }
  saving.value = true
  fieldErrors.value = {}
  roleErrors.value = {}
  generalError.value = ''
  try {
    const saved = props.entity
      ? await updateBusinessEntity(props.entity.id, payload())
      : await createBusinessEntity(payload())
    emit('saved', saved, !props.entity)
    open.value = false
  } catch (error) {
    if (error instanceof ApiError && error.status === 409 && error.message) {
      generalError.value = error.message
    } else if (error instanceof ApiError && error.status === 400) {
      fieldErrors.value = error.fieldErrors()
      const body = (error.data ?? {}) as Record<string, unknown>
      for (const role of ENTITY_ROLES) {
        const errors = body[role]
        if (errors && typeof errors === 'object' && !Array.isArray(errors)) {
          roleErrors.value[role] = errors as Record<string, string[]>
        }
      }
      const known = Object.keys(fieldErrors.value).length + Object.keys(roleErrors.value).length
      if (!known) generalError.value = t('common.saveError')
      else if (!Object.keys(fieldErrors.value).length)
        tab.value = Object.keys(roleErrors.value)[0] as EntityRole
      else tab.value = 'entity'
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

function clearRoleError(role: EntityRole, field: string) {
  const errors = roleErrors.value[role]
  if (errors?.[field]) errors[field] = []
}

const title = computed(() => {
  if (isEdit.value) return t('businessEntities.edit')
  return props.startRole
    ? t('businessEntities.newInRole', { role: t(`businessEntities.roles.${props.startRole}.one`) })
    : t('businessEntities.new')
})
</script>

<template>
  <FormDialog
    :audit="entity"
    ref="formRef"
    v-model="open"
    :title="title"
    :subtitle="entity ? entity.trade_name || entity.name : null"
    icon="mdi-domain"
    max-width="920"
    :persistent="saving"
    @submit="submit"
  >
    <template #header>
      <v-tabs v-model="tab" density="compact" color="primary" class="px-4" data-testid="form-tabs">
        <v-tab value="entity" prepend-icon="mdi-domain" data-testid="form-tab-entity">
          {{ $t('businessEntities.tabs.entity') }}
        </v-tab>
        <v-tab
          v-for="role in enabledRoles"
          :key="role"
          :value="role"
          :prepend-icon="ROLE_ICONS[role]"
          :data-testid="`form-tab-${role}`"
        >
          {{ $t(`businessEntities.roles.${role}.one`) }}
          <v-icon
            v-if="roleErrors[role] && Object.values(roleErrors[role]!).some((e) => e?.length)"
            icon="mdi-alert-circle"
            color="error"
            size="small"
            class="ml-1"
          />
        </v-tab>
      </v-tabs>
    </template>

    <!-- Every tab stays mounted: the whole form validates -->
    <v-window v-model="tab">
      <v-window-item value="entity" eager :transition="false" :reverse-transition="false">
        <div data-entity-tab="entity">
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
                :label="
                  isBrazil ? $t('customers.fields.taxIdBrazil') : $t('customers.fields.taxId')
                "
                :rules="[rules.required, rules.maxLength(30)]"
                :error-messages="fieldErrors.tax_id"
                maxlength="30"
                data-testid="tax-id"
                @update:model-value="clearError('tax_id')"
                @blur="suggestParent"
              >
                <template #append-inner><WebSearchButton :term="form.tax_id" /></template>
              </v-text-field>
            </v-col>
            <!-- Head office: another entity; the group is the tree under the one at the top -->
            <v-col cols="12">
              <EntityPicker
                :key="`parent-${openCount}`"
                v-model="form.parent"
                :label="$t('businessEntities.fields.parent')"
                :initial-option="initialParent"
                :exclude="entity ? [entity.id] : []"
                :error-messages="fieldErrors.parent"
                data-testid="parent"
                @update:model-value="(clearError('parent'), (suggestion = null))"
              />
              <div class="text-caption text-medium-emphasis mt-n1">
                {{ $t('businessEntities.parentHint') }}
              </div>
              <v-alert
                v-if="suggestion"
                type="info"
                variant="tonal"
                density="compact"
                class="mt-2"
                data-testid="parent-suggestion"
              >
                <div class="d-flex align-center flex-wrap ga-2">
                  <span>{{
                    $t('businessEntities.parentSuggestion', {
                      name: suggestion.trade_name || suggestion.name,
                      taxId: formatTaxId(suggestion.tax_id, suggestion.country),
                    })
                  }}</span>
                  <v-spacer />
                  <v-btn
                    size="small"
                    variant="tonal"
                    color="primary"
                    data-testid="use-suggestion"
                    @click="useSuggestion"
                    >{{ $t('businessEntities.useSuggestion') }}</v-btn
                  >
                </div>
              </v-alert>
            </v-col>
          </v-row>

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
                data-testid="contact-name"
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
                data-testid="email"
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

          <!-- Roles: each one turned on opens its tab -->
          <div class="text-subtitle-2 text-medium-emphasis mb-1 mt-2">
            {{ $t('businessEntities.fields.roles') }}
          </div>
          <div class="text-caption text-medium-emphasis mb-2">
            {{ $t('businessEntities.rolesHint') }}
          </div>
          <div class="roles-grid mb-2" data-testid="roles">
            <v-switch
              v-for="role in ENTITY_ROLES"
              :key="role"
              v-model="enabled[role]"
              color="primary"
              inset
              density="compact"
              hide-details
              :data-testid="`role-${role}`"
            >
              <template #label>
                <v-icon :icon="ROLE_ICONS[role]" size="small" class="mr-2" />
                {{ $t(`businessEntities.roles.${role}.one`) }}
              </template>
            </v-switch>
          </div>

          <v-row dense>
            <v-col cols="12" md="8">
              <KeywordsField
                v-model="form.keywords"
                :error-messages="fieldErrors.keywords"
                data-testid="keywords"
                @update:model-value="clearError('keywords')"
              />
            </v-col>
            <v-col cols="12" md="4" class="d-flex align-center">
              <v-switch
                v-model="form.is_active"
                :label="$t('businessEntities.fields.active')"
                color="primary"
                hide-details
                inset
                data-testid="active"
              />
            </v-col>
            <v-col cols="12">
              <v-textarea
                v-model="form.notes"
                :label="$t('customers.fields.notes')"
                :error-messages="fieldErrors.notes"
                rows="2"
                auto-grow
                @update:model-value="clearError('notes')"
              />
            </v-col>
          </v-row>
        </div>
      </v-window-item>

      <!-- One tab per role turned on -->
      <v-window-item
        v-for="role in enabledRoles"
        :key="role"
        :value="role"
        eager
        :transition="false"
        :reverse-transition="false"
      >
        <div :data-entity-tab="role">
          <p class="text-body-2 text-medium-emphasis mb-4">
            {{ $t(`businessEntities.roles.${role}.hint`) }}
          </p>

          <template v-if="role === 'customer'">
            <!-- How it takes Horizon's assets or services; none while only a prospect -->
            <div class="text-subtitle-2 text-medium-emphasis mb-1">
              {{ $t('businessEntities.fields.contractTypes') }}
            </div>
            <v-chip-group
              v-model="roleForms.customer.contract_types"
              multiple
              column
              selected-class="text-primary"
              class="mb-1"
              data-testid="contract-types"
              @update:model-value="clearRoleError('customer', 'contract_types')"
            >
              <v-chip
                v-for="kind in CONTRACT_TYPES"
                :key="kind"
                :value="kind"
                variant="outlined"
                filter
                :data-testid="`contract-type-${kind}`"
              >
                {{ $t(`businessEntities.contractTypes.${kind}`) }}
              </v-chip>
            </v-chip-group>
            <div class="text-caption text-medium-emphasis mb-4">
              {{ $t('businessEntities.contractTypesHint') }}
            </div>
            <v-row dense>
              <v-col cols="12">
                <AccountManagerPicker
                  :key="`primary-${openCount}`"
                  v-model="roleForms.customer.primary_account_manager"
                  :initial-options="initialPrimary"
                  :label="$t('customers.fields.primaryAccountManager')"
                  :rules="[required]"
                  :error-messages="roleErrors.customer?.primary_account_manager"
                  :no-data-text="$t('accountManagers.noneFound')"
                  prepend-inner-icon="mdi-star"
                  data-testid="primary-account-manager"
                  @update:model-value="onPrimaryChange"
                />
              </v-col>
              <v-col cols="12">
                <AccountManagerPicker
                  :key="`secondary-${openCount}`"
                  v-model="roleForms.customer.secondary_account_managers"
                  multiple
                  :initial-options="initialSecondaries"
                  :exclude="excludedFromSecondaries"
                  :label="$t('customers.fields.secondaryAccountManagers')"
                  :error-messages="roleErrors.customer?.secondary_account_managers"
                  :no-data-text="$t('accountManagers.noneFound')"
                  data-testid="secondary-account-managers"
                  @update:model-value="clearRoleError('customer', 'secondary_account_managers')"
                />
              </v-col>
            </v-row>
          </template>

          <template v-else-if="role === 'supplier'">
            <div class="text-subtitle-2 text-medium-emphasis mb-1">
              {{ $t('businessEntities.fields.supplies') }}
            </div>
            <v-input
              :model-value="roleForms.supplier.supplies"
              :rules="[required]"
              :error-messages="roleErrors.supplier?.supplies"
              class="mb-2"
            >
              <v-chip-group
                v-model="roleForms.supplier.supplies"
                multiple
                column
                selected-class="text-primary"
                data-testid="supplies"
                @update:model-value="clearRoleError('supplier', 'supplies')"
              >
                <v-chip
                  v-for="kind in SUPPLY_KINDS"
                  :key="kind"
                  :value="kind"
                  variant="outlined"
                  filter
                  :data-testid="`supply-${kind}`"
                >
                  {{ $t(`businessEntities.supplies.${kind}`) }}
                </v-chip>
              </v-chip-group>
            </v-input>
          </template>

          <template v-else-if="role === 'service_provider'">
            <div class="text-subtitle-2 text-medium-emphasis mb-1">
              {{ $t('serviceProviders.fields.services') }}
            </div>
            <v-input
              :model-value="roleForms.service_provider.services"
              :rules="[required]"
              :error-messages="roleErrors.service_provider?.services"
              class="mb-2"
            >
              <v-chip-group
                v-model="roleForms.service_provider.services"
                multiple
                column
                selected-class="text-primary"
                data-testid="services"
                @update:model-value="clearRoleError('service_provider', 'services')"
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
            <div
              v-if="entity?.service_provider?.warehouses_count"
              class="text-caption text-medium-emphasis mb-2"
            >
              <v-icon icon="mdi-warehouse" size="x-small" class="mr-1" />
              {{ $t('businessEntities.runsWarehouses', entity.service_provider.warehouses_count) }}
            </div>
          </template>

          <v-switch
            v-model="roleForms[role].is_active"
            :label="
              $t('businessEntities.roleActive', {
                role: $t(`businessEntities.roles.${role}.one`),
              })
            "
            color="primary"
            inset
            hide-details
            :data-testid="`${role}-active`"
          />
        </div>
      </v-window-item>
    </v-window>

    <v-alert
      v-if="generalError"
      type="error"
      variant="tonal"
      density="compact"
      class="mt-2"
      data-testid="general-error"
    >
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

<style scoped>
.roles-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 0 16px;
}
</style>
