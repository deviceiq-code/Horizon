<script setup lang="ts">
/**
 * A new eFMV analysis (no `id`) or an existing one: account manager, customer (one the account
 * manager serves) and its scenarios (at least one). Figures come from the API.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { ApiError } from '@/api'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import AccountManagerPicker from '@/modules/account-managers/AccountManagerPicker.vue'
import type { AccountManagerRef } from '@/modules/account-managers/api'
import { useAuthStore } from '@/stores/auth'
import { useNotificationsStore } from '@/stores/notifications'
import CustomerPicker from './CustomerPicker.vue'
import ScenarioCard from './ScenarioCard.vue'
import {
  createEfmvAnalysis,
  deleteEfmvAnalysis,
  getEfmvAnalysis,
  updateEfmvAnalysis,
  type CustomerRef,
  type EfmvAnalysis,
} from './api'
import {
  blankScenario,
  copyName,
  copyScenario,
  nextScenarioName,
  scenarioDraft,
  scenarioInput,
  type ScenarioDraft,
  type ScenarioErrors,
} from './draft'

const props = defineProps<{ id?: number }>()

const { t, d } = useI18n()
const router = useRouter()
const auth = useAuthStore()
const notifications = useNotificationsStore()
const required = (v: unknown) => (v !== null && v !== undefined) || t('validation.required')

const loading = ref(false)
const loadFailed = ref(false)
const saving = ref(false)
const analysis = ref<EfmvAnalysis | null>(null)

const accountManager = ref<number | null>(null)
const managerOptions = ref<AccountManagerRef[]>([])
const customer = ref<number | null>(null)
const customerOptions = ref<CustomerRef[]>([])
// The customer list depends on the account manager: remounted when it changes
const customerKey = ref(0)
const scenarios = ref<ScenarioDraft[]>([])

const form = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(null)
const errors = ref<Record<string, unknown>>({})
const formError = ref('')

const isNew = computed(() => props.id === undefined)

function fill(data: EfmvAnalysis) {
  analysis.value = data
  accountManager.value = data.account_manager
  managerOptions.value = [data.account_manager_detail]
  customer.value = data.customer
  customerOptions.value = [data.customer_detail]
  customerKey.value++
  scenarios.value = data.scenarios.map(scenarioDraft)
}

async function load() {
  if (isNew.value) {
    scenarios.value = [blankScenario(t('efmv.scenario.defaultName', { n: 1 }))]
    // An account manager starts their own analysis
    const me = auth.user
    if (me && me.roles.includes('Account Manager')) {
      accountManager.value = me.id
      managerOptions.value = [{ id: me.id, full_name: me.name }]
    }
    return
  }
  loading.value = true
  loadFailed.value = false
  try {
    fill(await getEfmvAnalysis(props.id!))
  } catch {
    loadFailed.value = true
  } finally {
    loading.value = false
  }
}
onMounted(load)

function onManagerChange(value: number | number[] | null) {
  const id = typeof value === 'number' ? value : null
  if (id === accountManager.value) return
  accountManager.value = id
  // Another account manager serves other customers
  customer.value = null
  customerOptions.value = []
  customerKey.value++
}

// --- Scenarios -----------------------------------------------------------------------------------

const names = computed(() => scenarios.value.map((s) => s.name))
const otherNames = (index: number) => names.value.filter((_, i) => i !== index)

function addScenario() {
  const name = nextScenarioName(t('efmv.scenario.defaultBase'), names.value)
  scenarios.value.push(blankScenario(name))
}

function duplicateScenario(index: number) {
  const source = scenarios.value[index]!
  const name = copyName(source.name, t('efmv.scenario.copy'), names.value)
  scenarios.value.splice(index + 1, 0, copyScenario(source, name))
}

const removing = ref<number | null>(null)
function removeScenario() {
  if (removing.value !== null) scenarios.value.splice(removing.value, 1)
  removing.value = null
}

// What the server refused no longer applies once the scenarios change
watch(
  () => JSON.stringify(scenarios.value.map(scenarioInput)),
  () => {
    if (errors.value.scenarios) {
      errors.value = { ...errors.value, scenarios: undefined }
      if (!fieldErrors('customer') && !fieldErrors('account_manager')) formError.value = ''
    }
  },
)

function scenarioErrors(index: number): ScenarioErrors | undefined {
  const all = errors.value.scenarios
  if (all && typeof all === 'object' && !Array.isArray(all)) {
    return (all as Record<string, ScenarioErrors>)[String(index)]
  }
  return undefined
}

const fieldErrors = (key: string) => {
  const value = errors.value[key]
  return Array.isArray(value) ? (value as string[]) : undefined
}

// --- Save / delete -------------------------------------------------------------------------------

async function save() {
  errors.value = {}
  formError.value = ''
  const { valid } = (await form.value?.validate()) ?? { valid: false }
  if (!valid) return
  // Assets whose average price was deleted are dropped when saving
  for (const scenario of scenarios.value) {
    const kept = scenario.items
      .map((item, i) => [item, scenario.preview?.items[i]] as const)
      .filter(([item]) => item.average_price !== null)
    scenario.items = kept.map(([item]) => item)
    if (scenario.preview) {
      scenario.preview.items = kept.map(([, detail]) => detail!).filter(Boolean)
    }
  }
  const data = {
    account_manager: accountManager.value!,
    customer: customer.value!,
    scenarios: scenarios.value.map(scenarioInput),
  }
  saving.value = true
  try {
    const saved = isNew.value
      ? await createEfmvAnalysis(data)
      : await updateEfmvAnalysis(props.id!, data)
    notifications.notify(t(isNew.value ? 'efmv.created' : 'efmv.updated', { code: saved.code }))
    if (isNew.value) {
      await router.replace({ name: 'efmv-analysis', params: { id: saved.id } })
    }
    fill(saved)
  } catch (error) {
    if (error instanceof ApiError && error.status === 400 && error.data) {
      errors.value = error.data as Record<string, unknown>
      const general = errors.value.non_field_errors ?? errors.value.detail
      formError.value = Array.isArray(general) ? general.join(' ') : t('efmv.fixErrors')
      if (typeof general === 'string') formError.value = general
    } else {
      formError.value = t('common.saveError')
    }
  } finally {
    saving.value = false
  }
}

const confirmDelete = ref(false)
const deleting = ref(false)
async function remove() {
  deleting.value = true
  try {
    await deleteEfmvAnalysis(props.id!)
    notifications.notify(t('efmv.deleted', { code: analysis.value?.code ?? '' }))
    await router.push({ name: 'efmv-analyses-list' })
  } catch {
    notifications.notify(t('common.deleteError'), 'error')
  } finally {
    deleting.value = false
    confirmDelete.value = false
  }
}
</script>

<template>
  <v-container fluid class="module-page">
    <div class="d-flex flex-wrap align-center ga-3 mb-4">
      <v-btn
        icon="mdi-arrow-left"
        variant="text"
        :to="{ name: 'efmv-analyses-list' }"
        :title="$t('efmv.backToList')"
        :aria-label="$t('efmv.backToList')"
        data-testid="back"
      />
      <div class="mr-auto">
        <h1 class="text-h5" data-testid="analysis-title">
          {{ analysis ? analysis.code : $t('efmv.newTitle') }}
        </h1>
        <div v-if="analysis" class="text-caption text-medium-emphasis">
          {{
            $t('efmv.createdBy', {
              date: d(new Date(analysis.created_at), 'short'),
              name: analysis.created_by_name ?? '—',
            })
          }}
        </div>
      </div>
      <v-btn
        v-if="analysis"
        variant="text"
        color="error"
        prepend-icon="mdi-delete-outline"
        data-testid="delete"
        @click="confirmDelete = true"
      >
        {{ $t('common.delete') }}
      </v-btn>
      <v-btn
        color="primary"
        prepend-icon="mdi-content-save-outline"
        :loading="saving"
        :disabled="loading || loadFailed"
        data-testid="save"
        @click="save"
      >
        {{ $t('common.save') }}
      </v-btn>
    </div>

    <v-progress-linear v-if="loading" indeterminate class="mb-4" />
    <v-alert v-else-if="loadFailed" type="error" variant="tonal" class="mb-4">
      {{ $t('common.loadError') }}
      <template #append>
        <v-btn variant="text" size="small" @click="load">{{ $t('common.retry') }}</v-btn>
      </template>
    </v-alert>

    <v-form v-if="!loading && !loadFailed" ref="form" @submit.prevent="save">
      <v-alert v-if="formError" type="error" variant="tonal" class="mb-4" data-testid="form-error">
        {{ formError }}
      </v-alert>

      <v-card class="mb-4">
        <v-card-title class="text-subtitle-1">{{ $t('efmv.general') }}</v-card-title>
        <v-card-text>
          <v-row dense>
            <v-col cols="12" md="6">
              <AccountManagerPicker
                :model-value="accountManager"
                :label="`${$t('efmv.fields.accountManager')} *`"
                :initial-options="managerOptions"
                :rules="[required]"
                :error-messages="fieldErrors('account_manager')"
                data-testid="account-manager"
                @update:model-value="onManagerChange"
              />
            </v-col>
            <v-col cols="12" md="6">
              <CustomerPicker
                v-if="accountManager !== null"
                :key="customerKey"
                v-model="customer"
                :account-manager="accountManager"
                :label="`${$t('efmv.fields.customer')} *`"
                :initial-options="customerOptions"
                :rules="[required]"
                :error-messages="fieldErrors('customer')"
                :no-data-text="$t('efmv.noCustomers')"
                data-testid="customer"
              />
              <v-text-field
                v-else
                :label="`${$t('efmv.fields.customer')} *`"
                :hint="$t('efmv.pickManagerFirst')"
                persistent-hint
                disabled
                data-testid="customer-disabled"
              />
            </v-col>
          </v-row>
        </v-card-text>
      </v-card>

      <div class="d-flex align-center mb-3">
        <h2 class="text-h6 mr-auto">{{ $t('efmv.scenarios') }}</h2>
        <v-btn
          variant="tonal"
          color="primary"
          prepend-icon="mdi-plus"
          data-testid="add-scenario"
          @click="addScenario"
        >
          {{ $t('efmv.scenario.add') }}
        </v-btn>
      </div>
      <div class="d-flex flex-column ga-4">
        <ScenarioCard
          v-for="(scenario, index) in scenarios"
          :key="scenario.key"
          v-model="scenarios[index]!"
          :index="index"
          :can-remove="scenarios.length > 1"
          :errors="scenarioErrors(index)"
          :other-names="otherNames(index)"
          @duplicate="duplicateScenario(index)"
          @remove="removing = index"
        />
      </div>
    </v-form>

    <ConfirmDialog
      :model-value="removing !== null"
      :title="$t('efmv.scenario.removeTitle')"
      :message="$t('efmv.scenario.removeConfirm', { name: scenarios[removing ?? -1]?.name ?? '' })"
      :confirm-text="$t('efmv.scenario.remove')"
      @update:model-value="!$event && (removing = null)"
      @confirm="removeScenario"
    />
    <ConfirmDialog
      v-model="confirmDelete"
      :title="$t('efmv.deleteTitle')"
      :message="$t('efmv.deleteConfirm', { code: analysis?.code ?? '' })"
      :confirm-text="$t('common.delete')"
      :loading="deleting"
      @confirm="remove"
    />
  </v-container>
</template>
