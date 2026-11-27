<script setup lang="ts">
/**
 * A new eFMV analysis, in three steps:
 * 1. Premises: account manager (with their figures: analyses, most explored verticals, customers
 *    they are the primary account manager of), customer (one they serve) and vertical (or one
 *    of its sub-verticals). Fixed once the analysis is created.
 * 2. Services and 3. Partnerships and Alliances: to come (shown, nothing to choose yet).
 * Creating it opens the analysis with a first scenario ("36 Months") to fill in.
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { ApiError } from '@/api'
import KeywordsField from '@/components/KeywordsField.vue'
import PersonAvatar from '@/components/PersonAvatar.vue'
import AccountManagerPicker from '@/modules/account-managers/AccountManagerPicker.vue'
import type { AccountManagerRef } from '@/modules/account-managers/api'
import { userPhotoUrl } from '@/modules/users/api'
import { useAuthStore } from '@/stores/auth'
import { useNotificationsStore } from '@/stores/notifications'
import CustomerPicker from './CustomerPicker.vue'
import VerticalScopePicker, { type VerticalScope } from './VerticalScopePicker.vue'
import { createEfmvAnalysis, getAccountManagerSummary, type AccountManagerSummary } from './api'
import { blankScenario, scenarioInput } from './draft'

const { t, locale } = useI18n()
const router = useRouter()
const auth = useAuthStore()
const notifications = useNotificationsStore()
const required = (v: unknown) => (v !== null && v !== undefined) || t('validation.required')

// --- Steps ---------------------------------------------------------------------------------------

const STEPS = [
  { key: 'premises', icon: 'mdi-account-tie-outline' },
  { key: 'services', icon: 'mdi-toolbox-outline' },
  { key: 'partnerships', icon: 'mdi-handshake-outline' },
] as const
const step = ref(0)
/** The furthest step reached (earlier ones can be opened again from the header) */
const reached = ref(0)
const isLast = computed(() => step.value === STEPS.length - 1)

// --- Step 1: premises ----------------------------------------------------------------------------

const accountManager = ref<number | null>(null)
const managerOptions = ref<AccountManagerRef[]>([])
const customer = ref<number | null>(null)
// The customer list depends on the account manager: remounted when it changes
const customerKey = ref(0)
const scope = ref<VerticalScope>({ vertical: null, sub_vertical: null })
const keywords = ref<string[]>([])
// E.g. the opportunity's number in a CRM (not a premise)
const externalReference = ref('')
const premisesForm = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(null)
const errors = ref<Record<string, string[]>>({})

// An account manager starts their own analysis
const me = auth.user
if (me && me.roles.includes('Account Manager')) {
  accountManager.value = me.id
  managerOptions.value = [{ id: me.id, full_name: me.name }]
}

function onManagerChange(value: number | number[] | null) {
  const id = typeof value === 'number' ? value : null
  if (id === accountManager.value) return
  accountManager.value = id
  // Another account manager serves other customers
  customer.value = null
  customerKey.value++
}

// The account manager's figures, next to the fields
const summary = ref<AccountManagerSummary | null>(null)
const summaryLoading = ref(false)
const summaryFailed = ref(false)
let summaryRequest = 0
watch(
  accountManager,
  async (id) => {
    summary.value = null
    summaryFailed.value = false
    if (id === null) return
    const current = ++summaryRequest
    summaryLoading.value = true
    try {
      const data = await getAccountManagerSummary(id)
      if (current === summaryRequest) summary.value = data
    } catch {
      if (current === summaryRequest) summaryFailed.value = true
    } finally {
      if (current === summaryRequest) summaryLoading.value = false
    }
  },
  { immediate: true },
)
/** The verticals the account manager works in: the only ones offered (none until known) */
const managerVerticals = computed(() => summary.value?.verticals.map((v) => v.id) ?? [])
// Another account manager may not work in the vertical chosen
watch(managerVerticals, (ids) => {
  if (scope.value.vertical !== null && !ids.includes(scope.value.vertical)) {
    scope.value = { vertical: null, sub_vertical: null }
  }
})

/** Bar length of a vertical among the top ones (the first is the longest) */
const barPercent = (count: number) =>
  Math.round((count / Math.max(1, summary.value?.top_verticals[0]?.analyses ?? 1)) * 100)

// --- Navigation and creation ---------------------------------------------------------------------

async function next() {
  if (step.value === 0) {
    const { valid } = (await premisesForm.value?.validate()) ?? { valid: false }
    if (!valid) return
  }
  if (isLast.value) {
    await create()
    return
  }
  step.value++
  reached.value = Math.max(reached.value, step.value)
}

function back() {
  if (step.value > 0) step.value--
}

function goTo(index: number) {
  if (index <= reached.value) step.value = index
}

const creating = ref(false)
const formError = ref('')
async function create() {
  creating.value = true
  formError.value = ''
  errors.value = {}
  try {
    const created = await createEfmvAnalysis({
      account_manager: accountManager.value!,
      customer: customer.value!,
      vertical: scope.value.vertical!,
      sub_vertical: scope.value.sub_vertical,
      keywords: keywords.value,
      external_reference: externalReference.value.trim(),
      // A first scenario, called by its term ("36 Months"), to fill in
      scenarios: [scenarioInput(blankScenario(), locale.value)],
    })
    notifications.notify(t('efmv.created', { code: created.code }))
    await router.replace({ name: 'efmv-analysis', params: { id: created.id } })
  } catch (error) {
    if (error instanceof ApiError && error.status === 400 && error.data) {
      const data = error.data as Record<string, unknown>
      errors.value = Object.fromEntries(
        Object.entries(data).filter(([, value]) => Array.isArray(value)),
      ) as Record<string, string[]>
      formError.value = t('efmv.fixErrors')
      // What was refused is in the premises
      step.value = 0
    } else {
      formError.value = t('common.saveError')
    }
  } finally {
    creating.value = false
  }
}
</script>

<template>
  <v-container fluid class="module-page" style="max-width: 1200px">
    <h1 class="mb-1">{{ $t('efmv.newTitle') }}</h1>
    <p class="text-medium-emphasis mb-6">{{ $t('efmv.wizard.subtitle') }}</p>

    <v-card class="pa-6" data-testid="wizard">
      <!-- Steps: number (a check once done), name, and a line to the next one -->
      <ol class="steps mb-8" data-testid="wizard-steps">
        <li
          v-for="(item, index) in STEPS"
          :key="item.key"
          class="step"
          :class="{
            current: index === step,
            done: index < step,
            open: index <= reached,
          }"
          :data-testid="`step-${item.key}`"
        >
          <button
            type="button"
            class="step-button"
            :disabled="index > reached"
            :aria-current="index === step ? 'step' : undefined"
            @click="goTo(index)"
          >
            <span class="step-mark">
              <v-icon v-if="index < step" icon="mdi-check" size="18" />
              <template v-else>{{ index + 1 }}</template>
            </span>
            <span class="step-name">{{ $t(`efmv.wizard.steps.${item.key}`) }}</span>
          </button>
          <span v-if="index < STEPS.length - 1" class="step-line" />
        </li>
      </ol>

      <v-alert
        v-if="formError"
        type="error"
        variant="tonal"
        density="compact"
        class="mb-4"
        data-testid="form-error"
      >
        {{ formError }}
      </v-alert>

      <!-- 1. Premises -->
      <div v-show="step === 0" data-testid="step-premises-content">
        <h2 class="step-title">{{ $t('efmv.wizard.premisesTitle') }}</h2>
        <p class="text-medium-emphasis text-body-2 mb-5">{{ $t('efmv.wizard.premisesHint') }}</p>
        <v-row>
          <v-col cols="12" md="6">
            <v-form ref="premisesForm" @submit.prevent="next">
              <AccountManagerPicker
                :model-value="accountManager"
                :label="`${$t('efmv.fields.accountManager')} *`"
                :initial-options="managerOptions"
                :rules="[required]"
                :error-messages="errors.account_manager"
                class="mb-2"
                data-testid="account-manager"
                @update:model-value="onManagerChange"
              />
              <CustomerPicker
                v-if="accountManager !== null"
                :key="customerKey"
                v-model="customer"
                :account-manager="accountManager"
                :label="`${$t('efmv.fields.customer')} *`"
                :rules="[required]"
                :error-messages="errors.customer"
                :no-data-text="$t('efmv.noCustomers')"
                class="mb-2"
                data-testid="customer"
              />
              <v-text-field
                v-else
                :label="`${$t('efmv.fields.customer')} *`"
                :hint="$t('efmv.pickManagerFirst')"
                persistent-hint
                disabled
                class="mb-2"
                data-testid="customer-disabled"
              />
              <VerticalScopePicker
                v-model="scope"
                :label="`${$t('efmv.fields.vertical')} *`"
                :rules="[() => scope.vertical !== null || t('validation.required')]"
                :error-messages="[...(errors.vertical ?? []), ...(errors.sub_vertical ?? [])]"
                :verticals="managerVerticals"
                :disabled="accountManager === null"
                :hint="
                  summary && !summary.verticals.length
                    ? $t('efmv.wizard.noManagerVerticals')
                    : $t('efmv.wizard.verticalHint')
                "
                persistent-hint
                :no-data-text="$t('efmv.wizard.noManagerVerticals')"
                data-testid="vertical"
              />
              <!-- Not premises: they can change on the analysis -->
              <v-text-field
                v-model="externalReference"
                :label="$t('efmv.fields.externalReference')"
                :hint="$t('efmv.fields.externalReferenceHint')"
                persistent-hint
                maxlength="100"
                :error-messages="errors.external_reference"
                prepend-inner-icon="mdi-link-variant"
                class="mt-2"
                data-testid="external-reference"
              />
              <KeywordsField
                v-model="keywords"
                :error-messages="errors.keywords"
                class="mt-2"
                data-testid="keywords"
              />
            </v-form>
          </v-col>

          <!-- The account manager, at a glance -->
          <v-col cols="12" md="6">
            <v-card variant="outlined" class="manager-card pa-5 h-100" data-testid="manager-card">
              <div
                v-if="accountManager === null"
                class="text-medium-emphasis text-body-2 d-flex align-center ga-3 h-100"
              >
                <v-icon icon="mdi-account-search-outline" size="32" />
                {{ $t('efmv.wizard.manager.pick') }}
              </div>
              <v-skeleton-loader
                v-else-if="summaryLoading"
                type="list-item-avatar-two-line, article"
              />
              <v-alert v-else-if="summaryFailed" type="warning" variant="tonal" density="compact">
                {{ $t('efmv.wizard.manager.loadError') }}
              </v-alert>
              <template v-else-if="summary">
                <div class="d-flex align-center ga-4 mb-5">
                  <PersonAvatar
                    :name="summary.full_name"
                    :src="
                      summary.photo_version ? userPhotoUrl(summary.id, summary.photo_version) : null
                    "
                    :size="64"
                    color="primary"
                  />
                  <div class="min-w-0">
                    <div class="text-subtitle-1 font-weight-bold" data-testid="manager-name">
                      {{ summary.full_name }}
                    </div>
                    <div v-if="summary.job_title" class="text-body-2 text-medium-emphasis">
                      {{ summary.job_title }}
                    </div>
                    <div class="text-body-2 text-medium-emphasis text-truncate">
                      {{ summary.email }}
                    </div>
                  </div>
                </div>

                <div class="figures mb-5">
                  <div class="figure" data-testid="manager-analyses">
                    <div class="figure-value">{{ $n(summary.analyses_count) }}</div>
                    <div class="figure-label">{{ $t('efmv.wizard.manager.analyses') }}</div>
                  </div>
                  <div class="figure" data-testid="manager-customers">
                    <div class="figure-value">{{ $n(summary.primary_customers_count) }}</div>
                    <div class="figure-label">
                      {{ $t('efmv.wizard.manager.primaryCustomers') }}
                    </div>
                  </div>
                </div>

                <div class="text-subtitle-2 mb-2">{{ $t('efmv.wizard.manager.topVerticals') }}</div>
                <div
                  v-if="!summary.top_verticals.length"
                  class="text-body-2 text-medium-emphasis"
                  data-testid="manager-no-analyses"
                >
                  {{ $t('efmv.wizard.manager.noAnalyses') }}
                </div>
                <div
                  v-for="vertical in summary.top_verticals"
                  :key="vertical.id"
                  class="top-vertical"
                  data-testid="manager-top-vertical"
                >
                  <div class="d-flex justify-space-between text-body-2 mb-1">
                    <span>{{ vertical.name }}</span>
                    <span class="text-medium-emphasis">
                      {{ $t('efmv.wizard.manager.analysesCount', vertical.analyses) }}
                    </span>
                  </div>
                  <v-progress-linear
                    :model-value="barPercent(vertical.analyses)"
                    color="primary"
                    bg-color="primary"
                    rounded
                    height="6"
                  />
                </div>
                <div v-if="summary.verticals.length" class="mt-4 text-body-2">
                  <span class="text-medium-emphasis">{{ $t('efmv.wizard.manager.worksIn') }}:</span>
                  {{ summary.verticals.map((v) => v.name).join(', ') }}
                </div>
              </template>
            </v-card>
          </v-col>
        </v-row>
      </div>

      <!-- 2. Services and 3. Partnerships and Alliances: to come -->
      <div
        v-for="item in STEPS.slice(1)"
        v-show="STEPS[step]!.key === item.key"
        :key="item.key"
        :data-testid="`step-${item.key}-content`"
      >
        <h2 class="step-title">{{ $t(`efmv.wizard.steps.${item.key}`) }}</h2>
        <div class="coming-soon">
          <v-avatar color="primary" variant="tonal" size="64" rounded="lg">
            <v-icon :icon="item.icon" size="32" />
          </v-avatar>
          <v-chip size="small" label class="mt-4">{{ $t('apps.comingSoon') }}</v-chip>
          <p class="text-body-2 text-medium-emphasis mt-3">
            {{ $t(`efmv.wizard.${item.key}Text`) }}
          </p>
        </div>
      </div>

      <!-- Footer: cancel or back; next, or create on the last step -->
      <v-divider class="my-6" />
      <div class="d-flex align-center ga-2">
        <v-btn
          v-if="step === 0"
          variant="text"
          :to="{ name: 'efmv-analyses-list' }"
          data-testid="wizard-cancel"
        >
          {{ $t('common.cancel') }}
        </v-btn>
        <v-btn
          v-else
          variant="text"
          prepend-icon="mdi-arrow-left"
          data-testid="wizard-back"
          @click="back"
        >
          {{ $t('efmv.wizard.back') }}
        </v-btn>
        <v-spacer />
        <v-btn
          color="primary"
          :append-icon="isLast ? 'mdi-check' : 'mdi-arrow-right'"
          :loading="creating"
          :data-testid="isLast ? 'wizard-create' : 'wizard-next'"
          @click="next"
        >
          {{ $t(isLast ? 'efmv.wizard.create' : 'efmv.wizard.next') }}
        </v-btn>
      </div>
    </v-card>
  </v-container>
</template>

<style scoped>
/* --- Steps header ---------------------------------------------------------------------------- */
.steps {
  list-style: none;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 12px;
  padding: 0;
  margin: 0;
}
.step {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 0 1 auto;
}
.step-button {
  display: flex;
  align-items: center;
  gap: 12px;
  background: none;
  border: 0;
  padding: 0;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
  cursor: pointer;
  font: inherit;
}
.step-button:disabled {
  cursor: default;
}
.step-mark {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-weight: 600;
  border: 1.5px solid rgba(var(--v-border-color), 0.4);
  background: rgb(var(--v-theme-surface));
  flex: 0 0 auto;
}
.step-name {
  font-weight: 500;
  white-space: nowrap;
}
.step.current .step-mark,
.step.done .step-mark {
  background: rgb(var(--v-theme-primary));
  border-color: rgb(var(--v-theme-primary));
  color: rgb(var(--v-theme-on-primary));
}
.step.current .step-button,
.step.done .step-button {
  color: rgb(var(--v-theme-on-surface));
}
.step-line {
  width: clamp(32px, 10vw, 160px);
  height: 1.5px;
  background: rgba(var(--v-border-color), 0.4);
}
.step.done .step-line {
  background: rgb(var(--v-theme-primary));
}
@media (max-width: 700px) {
  .step-name {
    display: none;
  }
}

.step-title {
  font-size: 1.125rem;
  font-weight: 600;
  margin-bottom: 4px;
}

/* --- Account manager card --------------------------------------------------------------------- */
.manager-card {
  border-color: rgba(var(--v-border-color), var(--v-border-opacity));
  box-shadow: none !important;
}
.figures {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.figure {
  padding: 12px 16px;
  border-radius: 12px;
  background: rgba(var(--v-theme-primary), 0.08);
}
.figure-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: rgb(var(--v-theme-primary));
  line-height: 1.2;
}
.figure-label {
  font-size: 0.8125rem;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.top-vertical + .top-vertical {
  margin-top: 10px;
}
.top-vertical :deep(.v-progress-linear__background) {
  opacity: 0.12;
}
.min-w-0 {
  min-width: 0;
}

/* --- Steps to come ---------------------------------------------------------------------------- */
.coming-soon {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  max-width: 520px;
  margin: 24px auto 8px;
}
</style>
