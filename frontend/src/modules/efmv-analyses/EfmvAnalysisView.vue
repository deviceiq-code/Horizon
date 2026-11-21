<script setup lang="ts">
/**
 * A new eFMV analysis (no `id`) or an existing one, in one form. On top, what is fixed for the
 * whole analysis: account manager, customer (one the account manager serves) and creation
 * date. Below, one tab per scenario (at least one); on wide screens the page fills the window
 * and only the assets of the open scenario scroll. Figures come from the API.
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
import ScenarioPanel from './ScenarioPanel.vue'
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
  isEfmvInput,
  parseTerm,
  parseUnitValue,
  scenarioDraft,
  scenarioInput,
  scenarioTitle,
  titleKey,
  type ScenarioDraft,
  type ScenarioErrors,
} from './draft'

const props = defineProps<{ id?: number }>()

const { t, d, locale } = useI18n()
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
/** Key of the scenario whose tab is open */
const tab = ref<number | null>(null)

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
  // After saving, the scenarios keep their keys (found by their official name, unique; the API
  // returns them in its order): new keys would replace every tab and window item while the
  // open tab changes, and the window lost its selection (no scenario shown)
  const previous = new Map(scenarios.value.map((s) => [titleKey(s.term, s.name), s.key]))
  scenarios.value = data.scenarios.map((s) => {
    const draft = scenarioDraft(s, locale.value)
    return { ...draft, key: previous.get(titleKey(draft.term, draft.name)) ?? draft.key }
  })
  // Stay on the same scenario after saving
  const open = scenarios.value.find((s) => s.key === tab.value) ?? ordered.value[0]?.scenario
  tab.value = open?.key ?? null
}

async function load() {
  if (isNew.value) {
    // Without a name: called by its term ("36 Months")
    scenarios.value = [blankScenario()]
    tab.value = scenarios.value[0]!.key
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

/** Some average price used is past its validity (as the API reports, live while editing) */
const outdated = computed(() => scenarios.value.some((s) => s.preview?.has_expired))

const names = computed(() => scenarios.value.map((s) => s.name))
/** Official names (term + name) of the scenarios; they must be different */
const keys = computed(() => scenarios.value.map((s) => titleKey(s.term, s.name)))
const otherKeys = (index: number) => keys.value.filter((_, i) => i !== index)

/**
 * Tabs in the order of the official names: the term (as a number), then the name — "12 Months",
 * "36 Months", "36 Months - Desktops", "120 Months" (as the API orders them). `index` is the
 * scenario's place in `scenarios`.
 */
const collator = computed(() => new Intl.Collator(locale.value, { sensitivity: 'base' }))
const ordered = computed(() =>
  scenarios.value
    .map((scenario, index) => ({ scenario, index, term: parseTerm(scenario.term) }))
    .sort(
      (a, b) =>
        (a.term ?? Infinity) - (b.term ?? Infinity) ||
        collator.value.compare(a.scenario.name.trim(), b.scenario.name.trim()) ||
        a.index - b.index,
    ),
)

/** "36 Months - Desktops" / "60 Months" (the tab shows it) */
const titleOf = (scenario: ScenarioDraft) =>
  scenarioTitle(
    scenario.term,
    scenario.name,
    (count) => t('efmv.scenario.termTitle', count),
    t('efmv.scenario.untitled'),
  )

function addScenario() {
  // Without a name when its official name ("36 Months") is free
  const fresh = blankScenario()
  const name = keys.value.includes(titleKey(fresh.term, ''))
    ? nextScenarioName(t('efmv.scenario.defaultBase'), names.value)
    : ''
  const scenario = blankScenario(name)
  scenarios.value.push(scenario)
  tab.value = scenario.key
}

/** Position in `scenarios` of the open tab's scenario (the toolbar acts on it) */
const openIndex = computed(() => scenarios.value.findIndex((s) => s.key === tab.value))

function duplicateScenario(index: number) {
  const source = scenarios.value[index]!
  const name = source.name.trim()
    ? copyName(source.name, t('efmv.scenario.copy'), names.value)
    : nextScenarioName(t('efmv.scenario.copyBase'), names.value)
  const copy = copyScenario(source, name)
  scenarios.value.splice(index + 1, 0, copy)
  tab.value = copy.key
}

const removing = ref<number | null>(null)
function removeScenario() {
  if (removing.value !== null) {
    scenarios.value.splice(removing.value, 1)
    tab.value = scenarios.value[Math.min(removing.value, scenarios.value.length - 1)]!.key
  }
  removing.value = null
}

// What the server refused no longer applies once the scenarios change
watch(
  () => JSON.stringify(scenarios.value.map((s) => scenarioInput(s, locale.value))),
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

/** Whether a scenario needs attention before saving (its tab is marked; saving opens it). */
function hasIssues(index: number): boolean {
  const scenario = scenarios.value[index]!
  return (
    !!scenarioErrors(index) ||
    scenario.name.length > 100 ||
    otherKeys(index).includes(keys.value[index]!) ||
    parseTerm(scenario.term) === null ||
    scenario.vertical === null ||
    !!scenario.preview?.items.some((i) => i.out_of_scope) ||
    scenario.items.some(
      (i) =>
        i.average_price !== null &&
        (!Number.isInteger(i.quantity) ||
          i.quantity < 1 ||
          (!!i.unit_value.trim() && parseUnitValue(i.unit_value, locale.value) === null) ||
          !isEfmvInput(i.efmv_value, locale.value)),
    ) ||
    !!scenario.preview?.items.some((i) => i.out_of_curve)
  )
}

function openFirstWithIssues() {
  const index = scenarios.value.findIndex((_, i) => hasIssues(i))
  if (index >= 0) tab.value = scenarios.value[index]!.key
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
  if (!valid) {
    if (accountManager.value !== null && customer.value !== null) openFirstWithIssues()
    return
  }
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
    scenarios: scenarios.value.map((s) => scenarioInput(s, locale.value)),
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
      if (!fieldErrors('customer') && !fieldErrors('account_manager')) openFirstWithIssues()
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
  <v-container fluid class="module-page efmv-page">
    <v-progress-linear v-if="loading" indeterminate class="mb-4" />
    <v-alert v-else-if="loadFailed" type="error" variant="tonal" class="mb-4">
      {{ $t('common.loadError') }}
      <template #append>
        <v-btn variant="text" size="small" @click="load">{{ $t('common.retry') }}</v-btn>
      </template>
    </v-alert>

    <v-form v-if="!loading && !loadFailed" ref="form" class="efmv-form" @submit.prevent="save">
      <!-- What is fixed for the whole analysis -->
      <v-card class="mb-3 flex-shrink-0 pa-3" data-testid="analysis-header">
        <div class="header-row">
          <div class="d-flex align-center ga-1 header-title">
            <v-btn
              icon="mdi-arrow-left"
              variant="text"
              size="small"
              :to="{ name: 'efmv-analyses-list' }"
              :title="$t('efmv.backToList')"
              :aria-label="$t('efmv.backToList')"
              data-testid="back"
            />
            <h1 class="analysis-title text-no-wrap" data-testid="analysis-title">
              {{ analysis ? analysis.code : $t('efmv.newTitle') }}
            </h1>
            <v-chip
              v-if="outdated"
              color="warning"
              prepend-icon="mdi-calendar-alert"
              size="small"
              variant="tonal"
              label
              class="ml-2"
              :title="$t('efmv.outdatedHint')"
              data-testid="outdated"
            >
              {{ $t('efmv.outdated') }}
            </v-chip>
          </div>
          <AccountManagerPicker
            :model-value="accountManager"
            :label="`${$t('efmv.fields.accountManager')} *`"
            :initial-options="managerOptions"
            :rules="[required]"
            :error-messages="fieldErrors('account_manager')"
            density="compact"
            hide-details="auto"
            class="header-field"
            data-testid="account-manager"
            @update:model-value="onManagerChange"
          />
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
            density="compact"
            hide-details="auto"
            class="header-field wide"
            data-testid="customer"
          />
          <v-text-field
            v-else
            :label="`${$t('efmv.fields.customer')} *`"
            :hint="$t('efmv.pickManagerFirst')"
            persistent-hint
            disabled
            density="compact"
            class="header-field wide"
            data-testid="customer-disabled"
          />
          <v-text-field
            :model-value="
              analysis ? d(new Date(analysis.created_at), 'short') : $t('efmv.notSavedYet')
            "
            :label="$t('efmv.fields.createdAt')"
            :title="analysis?.created_by_name ?? undefined"
            prepend-inner-icon="mdi-calendar-outline"
            readonly
            density="compact"
            hide-details
            tabindex="-1"
            class="header-field date"
            data-testid="created-at"
          />
          <div class="d-flex align-center ga-2 header-actions">
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
              data-testid="save"
              @click="save"
            >
              {{ $t('common.save') }}
            </v-btn>
          </div>
        </div>
      </v-card>

      <v-alert
        v-if="formError"
        type="error"
        variant="tonal"
        density="compact"
        class="mb-3 flex-shrink-0"
        data-testid="form-error"
      >
        {{ formError }}
      </v-alert>

      <!-- Scenarios: one tab each -->
      <v-card class="scenarios">
        <div class="d-flex align-center tabs-bar">
          <v-tabs v-model="tab" color="primary" show-arrows class="flex-grow-1" data-testid="tabs">
            <v-tab
              v-for="{ scenario, index } in ordered"
              :key="scenario.key"
              :value="scenario.key"
              class="text-none"
              :data-testid="`tab-${index}`"
            >
              <v-icon
                v-if="hasIssues(index)"
                icon="mdi-alert-circle"
                color="error"
                size="small"
                class="mr-1"
                data-testid="tab-issue"
              />
              <v-icon
                v-else-if="scenario.preview?.has_expired"
                icon="mdi-calendar-alert"
                color="warning"
                size="small"
                class="mr-1"
                :title="$t('efmv.outdatedHint')"
                data-testid="tab-expired"
              />
              {{ titleOf(scenario) }}
            </v-tab>
          </v-tabs>
          <!-- Toolbar of the scenarios: add one; duplicate or remove the open one. On narrow
               screens only the icons show (the names are in their tooltips). -->
          <div
            class="scenario-toolbar d-flex align-center ga-1 px-2"
            data-testid="scenario-toolbar"
          >
            <v-btn
              variant="text"
              color="primary"
              prepend-icon="mdi-plus"
              class="text-none"
              :title="$t('efmv.scenario.add')"
              data-testid="add-scenario"
              @click="addScenario"
            >
              <span class="d-none d-md-inline">{{ $t('efmv.scenario.add') }}</span>
            </v-btn>
            <v-divider vertical class="my-2" />
            <v-btn
              variant="text"
              prepend-icon="mdi-content-copy"
              class="text-none"
              :disabled="openIndex < 0"
              :title="$t('efmv.scenario.duplicate')"
              data-testid="duplicate-scenario"
              @click="duplicateScenario(openIndex)"
            >
              <span class="d-none d-md-inline">{{ $t('efmv.scenario.duplicateShort') }}</span>
            </v-btn>
            <!-- The wrapper keeps the tooltip while the button is disabled (one scenario left) -->
            <span
              :title="$t(scenarios.length > 1 ? 'efmv.scenario.remove' : 'efmv.scenario.keepOne')"
            >
              <v-btn
                variant="text"
                color="error"
                prepend-icon="mdi-delete-outline"
                class="text-none"
                :disabled="scenarios.length < 2 || openIndex < 0"
                data-testid="remove-scenario"
                @click="removing = openIndex"
              >
                <span class="d-none d-md-inline">{{ $t('efmv.scenario.removeShort') }}</span>
              </v-btn>
            </span>
          </div>
        </div>
        <!-- No animation when switching scenarios -->
        <v-window v-model="tab" class="scenario-window">
          <!-- Eager: every scenario is validated and keeps its figures, open or not; no animation
               when switching scenarios -->
          <v-window-item
            v-for="(scenario, index) in scenarios"
            :key="scenario.key"
            :value="scenario.key"
            eager
            :transition="false"
            :reverse-transition="false"
            class="h-100"
          >
            <ScenarioPanel
              v-model="scenarios[index]!"
              :index="index"
              :errors="scenarioErrors(index)"
              :other-keys="otherKeys(index)"
              :title="titleOf(scenario)"
            />
          </v-window-item>
        </v-window>
      </v-card>
    </v-form>

    <ConfirmDialog
      :model-value="removing !== null"
      :title="$t('efmv.scenario.removeTitle')"
      :message="
        $t('efmv.scenario.removeConfirm', {
          name: removing === null ? '' : titleOf(scenarios[removing]!),
        })
      "
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

<style scoped>
.header-row {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 12px;
}
.header-title {
  min-height: 40px;
}
.analysis-title {
  font-size: 1.25rem;
  font-weight: 500;
  line-height: 1.2;
}
.header-field {
  flex: 1 1 220px;
  min-width: 200px;
}
.header-field.wide {
  flex: 2 1 280px;
}
.header-field.date {
  flex: 0 1 190px;
  min-width: 160px;
}
.header-actions {
  min-height: 40px;
  margin-left: auto;
}
.tabs-bar {
  border-bottom: thin solid rgba(var(--v-border-color), var(--v-border-opacity));
}
/* Wide screens: the page fills the window under the path bar; the open scenario takes the
   rest of it and only its assets scroll */
@media (min-width: 960px) {
  .efmv-page {
    height: calc(
      100dvh / var(--ui-zoom, 1) - var(--v-layout-top, 0px) - var(--horizon-path-bar-height)
    );
    display: flex;
    flex-direction: column;
  }
  .efmv-form {
    flex: 1 1 0;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }
  .scenarios {
    flex: 1 1 0;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }
  .scenario-window {
    flex: 1 1 0;
    min-height: 0;
  }
  .scenario-window :deep(.v-window__container) {
    height: 100%;
  }
}
</style>
