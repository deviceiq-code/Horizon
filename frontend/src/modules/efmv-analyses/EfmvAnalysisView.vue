<script setup lang="ts">
/**
 * An eFMV analysis (created by the wizard, EfmvWizardView.vue; deleted from the list's grid). On top, its premises — account
 * manager, customer, vertical — and creation date, as labels (they do not change). Below, one
 * tab per scenario (at least one); on wide screens the page fills the window and only the
 * assets of the open scenario scroll. Figures come from the API.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import PersonAvatar from '@/components/PersonAvatar.vue'
import { userPhotoUrl } from '@/modules/users/api'
import { useNotificationsStore } from '@/stores/notifications'
import ScenarioPanel from './ScenarioPanel.vue'
import {
  getAccountManagerSummary,
  getEfmvAnalysis,
  updateEfmvAnalysis,
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

const props = defineProps<{ id: number }>()

const { t, d, locale } = useI18n()
const notifications = useNotificationsStore()

const loading = ref(false)
const loadFailed = ref(false)
const saving = ref(false)
const analysis = ref<EfmvAnalysis | null>(null)

/** The account manager's photo version (their photo on the header), loaded with the analysis */
const managerPhoto = ref<string | null>(null)
const scenarios = ref<ScenarioDraft[]>([])
/** Key of the scenario whose tab is open */
const tab = ref<number | null>(null)

const form = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(null)
const errors = ref<Record<string, unknown>>({})
const formError = ref('')

/** The assets the scenarios admit: the analysis's vertical (or sub-vertical) */
const scope = computed(() => ({
  vertical: analysis.value?.vertical ?? null,
  sub_vertical: analysis.value?.sub_vertical ?? null,
}))

function fill(data: EfmvAnalysis) {
  analysis.value = data
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
  loading.value = true
  loadFailed.value = false
  try {
    fill(await getEfmvAnalysis(props.id))
  } catch {
    loadFailed.value = true
  } finally {
    loading.value = false
  }
  // The account manager's photo (only shown: a failure leaves their initials)
  if (analysis.value) {
    getAccountManagerSummary(analysis.value.account_manager)
      .then((summary) => (managerPhoto.value = summary.photo_version))
      .catch(() => undefined)
  }
}
onMounted(load)

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
      formError.value = ''
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

// --- Save -------------------------------------------------------------------------------------

async function save() {
  errors.value = {}
  formError.value = ''
  const { valid } = (await form.value?.validate()) ?? { valid: false }
  if (!valid) {
    openFirstWithIssues()
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
  saving.value = true
  try {
    // Only the scenarios: the premises do not change
    const saved = await updateEfmvAnalysis(props.id, {
      scenarios: scenarios.value.map((s) => scenarioInput(s, locale.value)),
    })
    notifications.notify(t('efmv.updated', { code: saved.code }))
    fill(saved)
  } catch (error) {
    if (error instanceof ApiError && error.status === 400 && error.data) {
      errors.value = error.data as Record<string, unknown>
      const general = errors.value.non_field_errors ?? errors.value.detail
      formError.value = Array.isArray(general) ? general.join(' ') : t('efmv.fixErrors')
      if (typeof general === 'string') formError.value = general
      openFirstWithIssues()
    } else {
      formError.value = t('common.saveError')
    }
  } finally {
    saving.value = false
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
              {{ analysis?.code }}
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
          <!-- The premises, set by the wizard: labels only -->
          <div v-if="analysis" class="premises" data-testid="premises">
            <div class="premise" data-testid="premise-account-manager">
              <div class="premise-label">{{ $t('efmv.fields.accountManager') }}</div>
              <div class="premise-value">
                <PersonAvatar
                  :name="analysis.account_manager_detail.full_name"
                  :src="managerPhoto ? userPhotoUrl(analysis.account_manager, managerPhoto) : null"
                  :size="24"
                  color="primary"
                  class="mr-2"
                />
                {{ analysis.account_manager_detail.full_name }}
              </div>
            </div>
            <div class="premise" data-testid="premise-customer">
              <div class="premise-label">{{ $t('efmv.fields.customer') }}</div>
              <div class="premise-value">
                <v-icon icon="mdi-domain" size="small" class="mr-2 text-medium-emphasis" />
                {{ analysis.customer_detail.name }}
                <span v-if="analysis.customer_detail.trade_name" class="text-medium-emphasis ml-1">
                  ({{ analysis.customer_detail.trade_name }})
                </span>
              </div>
            </div>
            <div class="premise" data-testid="premise-vertical">
              <div class="premise-label">{{ $t('efmv.fields.vertical') }}</div>
              <div class="premise-value">
                <v-icon icon="mdi-shape-outline" size="small" class="mr-2 text-medium-emphasis" />
                {{ analysis.vertical_label ?? '—' }}
              </div>
            </div>
            <div
              class="premise"
              :title="analysis.created_by_name ?? undefined"
              data-testid="created-at"
            >
              <div class="premise-label">{{ $t('efmv.fields.createdAt') }}</div>
              <div class="premise-value">
                <v-icon
                  icon="mdi-calendar-outline"
                  size="small"
                  class="mr-2 text-medium-emphasis"
                />
                {{ d(new Date(analysis.created_at), 'short') }}
              </div>
            </div>
          </div>
          <div class="d-flex align-center ga-2 header-actions">
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
              <span class="d-none d-md-inline">{{ $t('efmv.scenario.addShort') }}</span>
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
              :scope="scope"
              :scope-label="analysis?.vertical_label ?? null"
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
  </v-container>
</template>

<style scoped>
.header-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
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
/* The premises: small captions over their values, side by side */
.premises {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 28px;
  flex: 1 1 auto;
  min-height: 40px;
  padding-left: 12px;
  border-left: thin solid rgba(var(--v-border-color), var(--v-border-opacity));
}
.premise-label {
  font-size: 0.75rem;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.premise-value {
  display: flex;
  align-items: center;
  font-weight: 500;
  white-space: nowrap;
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
