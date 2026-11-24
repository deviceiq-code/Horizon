<script setup lang="ts">
/**
 * An inspection report: a draft opens the step-by-step inspection (inspectors); otherwise the
 * report as a document — printable ("Print → Save as PDF") — with the supervisor's approval
 * (another user than the technician; findings' values may be adjusted with a justification),
 * sending it back for review, and marking it as sent to the customer.
 */
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useNotificationsStore } from '@/stores/notifications'
import { formatMoney, parseMoney, toInputMoney } from '@/utils/money'
import InspectionWizard from './InspectionWizard.vue'
import ReportSheet from './ReportSheet.vue'
import {
  approveReport,
  createDispute,
  getReport,
  markReportSent,
  returnReport,
  updateFinding,
  type Finding,
  type InspectionReport,
} from './api'
import { useInventoryRoles } from './roles'

const props = defineProps<{ id: number }>()

const { t, locale } = useI18n()
const auth = useAuthStore()
const notifications = useNotificationsStore()
const { canInspect, isSupervisor, canSend } = useInventoryRoles()

const report = ref<InspectionReport | null>(null)
const loadError = ref(false)
const busy = ref(false)
const actionError = ref('')

async function load() {
  try {
    report.value = await getReport(props.id)
  } catch {
    loadError.value = true
  }
}
onMounted(load)

const editing = computed(() => report.value?.status === 'draft' && canInspect.value)
const STATUS_COLORS = {
  draft: 'info',
  awaiting_approval: 'warning',
  approved: 'success',
  superseded: undefined,
} as const

async function act(call: () => Promise<InspectionReport>, message: string) {
  busy.value = true
  actionError.value = ''
  try {
    report.value = await call()
    notifications.notify(t(message))
  } catch (error) {
    actionError.value = error instanceof ApiError ? error.message : t('common.saveError')
  } finally {
    busy.value = false
  }
}

const approve = () => act(() => approveReport(props.id), 'inventory.reports.approved')
const markSent = () => act(() => markReportSent(props.id), 'inventory.reports.sent')

// --- A customer's dispute (within the deadline) ----------------------------------------------------

const today = new Date().toISOString().slice(0, 10)
const canDispute = computed(
  () =>
    !!report.value &&
    canSend.value &&
    report.value.status === 'approved' &&
    report.value.is_current &&
    !!report.value.sent_to_customer_at &&
    (!report.value.dispute_deadline || report.value.dispute_deadline >= today) &&
    report.value.findings.some((f) => f.status === 'approved') &&
    !report.value.asset_detail.held_for_dispute,
)
const disputeOpen = ref(false)
const disputed = ref<number[]>([])
const justification = ref('')
const disputeError = ref('')
function openDispute() {
  disputed.value = []
  justification.value = ''
  disputeError.value = ''
  disputeOpen.value = true
}
async function registerDispute() {
  disputeError.value = ''
  try {
    await createDispute({
      report: props.id,
      findings: disputed.value,
      justification: justification.value,
    })
    disputeOpen.value = false
    notifications.notify(t('inventory.disputes.registered'))
    await load()
  } catch (error) {
    disputeError.value = error instanceof ApiError ? error.message : t('common.saveError')
  }
}

const returnOpen = ref(false)
const returnNotes = ref('')
async function sendBack() {
  await act(() => returnReport(props.id, returnNotes.value), 'inventory.reports.sentBack')
  if (!actionError.value) returnOpen.value = false
}

// A supervisor adjusts a finding's value (empty: back to the table's)
const valueOpen = ref(false)
const valueFinding = ref<Finding | null>(null)
const valueText = ref('')
const valueReason = ref('')
function editValue(finding: Finding) {
  valueFinding.value = finding
  valueText.value = finding.value ? toInputMoney(finding.value, locale.value, 2) : ''
  valueReason.value = finding.value_justification
  valueOpen.value = true
}
async function saveValue() {
  if (!valueFinding.value) return
  const value = valueText.value.trim() ? parseMoney(valueText.value, locale.value, 2) : null
  await act(
    () =>
      updateFinding(props.id, valueFinding.value!.id, {
        value,
        value_justification: valueReason.value,
      }),
    'inventory.findings.valueSaved',
  )
  if (!actionError.value) valueOpen.value = false
}

const isOwnReport = computed(() => !!report.value && report.value.technician === auth.user?.id)

function print() {
  window.print()
}
</script>

<template>
  <v-container fluid class="module-page">
    <v-alert v-if="loadError" type="error" variant="tonal">{{ $t('common.loadError') }}</v-alert>
    <template v-if="report">
      <div class="d-flex flex-wrap align-center ga-3 mb-4 no-print">
        <h1>{{ report.asset_code }} · v{{ report.version }}</h1>
        <v-chip :color="STATUS_COLORS[report.status]" variant="tonal" label>
          {{ $t(`inventory.reports.statuses.${report.status}`) }}
        </v-chip>
        <v-spacer />
        <template v-if="!editing">
          <v-btn
            variant="text"
            prepend-icon="mdi-printer-outline"
            data-testid="print"
            @click="print"
          >
            {{ $t('inventory.reports.print') }}
          </v-btn>
          <template v-if="report.status === 'awaiting_approval' && isSupervisor">
            <v-btn
              variant="tonal"
              prepend-icon="mdi-undo"
              :loading="busy"
              data-testid="send-back"
              @click="returnOpen = true"
            >
              {{ $t('inventory.reports.sendBack') }}
            </v-btn>
            <v-btn
              color="primary"
              prepend-icon="mdi-check-decagram"
              :loading="busy"
              data-testid="approve"
              @click="approve"
            >
              {{ $t('inventory.reports.approve') }}
            </v-btn>
          </template>
          <v-btn
            v-if="
              report.status === 'approved' &&
              report.is_current &&
              canSend &&
              !report.sent_to_customer_at
            "
            variant="tonal"
            prepend-icon="mdi-email-check-outline"
            :loading="busy"
            data-testid="mark-sent"
            @click="markSent"
          >
            {{ $t('inventory.reports.markSent') }}
          </v-btn>
          <v-btn
            v-if="canDispute"
            variant="tonal"
            color="warning"
            prepend-icon="mdi-gavel"
            data-testid="register-dispute"
            @click="openDispute"
          >
            {{ $t('inventory.disputes.register') }}
          </v-btn>
        </template>
      </div>

      <v-alert
        v-if="actionError"
        type="error"
        variant="tonal"
        density="compact"
        class="mb-4 no-print"
        data-testid="report-error"
      >
        {{ actionError }}
      </v-alert>
      <v-alert
        v-if="report.status === 'awaiting_approval' && isSupervisor && isOwnReport"
        type="info"
        variant="tonal"
        density="compact"
        class="mb-4 no-print"
      >
        {{ $t('inventory.reports.ownReport') }}
      </v-alert>

      <InspectionWizard v-if="editing" v-model="report" @submitted="load" />
      <template v-else>
        <v-card class="pa-6 sheet-card">
          <ReportSheet :report="report" />
        </v-card>
        <!-- Supervisors adjust values before approving -->
        <v-card
          v-if="report.status === 'awaiting_approval' && isSupervisor && report.findings.length"
          class="pa-4 mt-4 no-print"
        >
          <div class="text-subtitle-1 font-weight-medium mb-2">
            {{ $t('inventory.findings.values') }}
          </div>
          <v-list density="compact">
            <v-list-item v-for="f in report.findings" :key="f.id" class="px-0">
              <v-list-item-title>
                {{ $t(`inventory.findings.kinds.${f.kind}`) }} · {{ f.item || f.description }}
              </v-list-item-title>
              <v-list-item-subtitle>
                {{
                  f.value ? formatMoney(f.value, 'BRL', locale) : $t('inventory.findings.noRate')
                }}
                <template v-if="f.value_overridden"> · {{ f.value_justification }}</template>
              </v-list-item-subtitle>
              <template #append>
                <v-btn size="small" variant="tonal" data-testid="edit-value" @click="editValue(f)">
                  {{ $t('inventory.findings.editValue') }}
                </v-btn>
              </template>
            </v-list-item>
          </v-list>
        </v-card>
      </template>
    </template>

    <v-dialog v-model="disputeOpen" max-width="620">
      <v-card :title="$t('inventory.disputes.register')">
        <v-card-text>
          <p class="text-body-2 text-medium-emphasis mb-2">
            {{ $t('inventory.disputes.registerHint') }}
          </p>
          <v-list density="compact">
            <v-list-item
              v-for="f in report?.findings.filter((x) => x.status === 'approved') ?? []"
              :key="f.id"
              class="px-0"
            >
              <template #prepend>
                <v-checkbox-btn
                  v-model="disputed"
                  :value="f.id"
                  density="compact"
                  data-testid="dispute-finding"
                />
              </template>
              <v-list-item-title
                >{{ $t(`inventory.findings.kinds.${f.kind}`) }} ·
                {{ f.item || f.description }}</v-list-item-title
              >
              <v-list-item-subtitle>{{
                f.value ? formatMoney(f.value, 'BRL', locale) : '—'
              }}</v-list-item-subtitle>
            </v-list-item>
          </v-list>
          <v-textarea
            v-model="justification"
            :label="$t('inventory.disputes.justification')"
            rows="3"
            auto-grow
            data-testid="dispute-justification"
          />
          <v-alert v-if="disputeError" type="error" variant="tonal" density="compact">{{
            disputeError
          }}</v-alert>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="disputeOpen = false">{{ $t('common.cancel') }}</v-btn>
          <v-btn
            color="primary"
            variant="flat"
            :disabled="!disputed.length"
            data-testid="dispute-save"
            @click="registerDispute"
          >
            {{ $t('inventory.disputes.register') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="returnOpen" max-width="560">
      <v-card :title="$t('inventory.reports.sendBack')">
        <v-card-text>
          <v-textarea
            v-model="returnNotes"
            :label="$t('inventory.reports.reviewNotes')"
            rows="3"
            auto-grow
            autofocus
            data-testid="return-notes"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="returnOpen = false">{{ $t('common.cancel') }}</v-btn>
          <v-btn color="primary" variant="flat" @click="sendBack">{{
            $t('inventory.reports.sendBack')
          }}</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="valueOpen" max-width="520">
      <v-card :title="$t('inventory.findings.editValue')">
        <v-card-text>
          <v-text-field
            v-model="valueText"
            :label="$t('inventory.penalties.value')"
            :hint="$t('inventory.findings.valueHint')"
            persistent-hint
            inputmode="decimal"
          />
          <v-textarea
            v-model="valueReason"
            :label="$t('inventory.findings.justification')"
            rows="2"
            auto-grow
            class="mt-2"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="valueOpen = false">{{ $t('common.cancel') }}</v-btn>
          <v-btn color="primary" variant="flat" @click="saveValue">{{ $t('common.save') }}</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<style scoped>
@media print {
  :global(.v-navigation-drawer),
  :global(.v-app-bar),
  .no-print {
    display: none !important;
  }
  :global(.v-main) {
    padding: 0 !important;
  }
  .sheet-card {
    box-shadow: none !important;
  }
}
</style>
