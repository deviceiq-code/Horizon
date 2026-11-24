<script setup lang="ts">
/**
 * Disputes of inspection reports (registered on the report page, within the dispute deadline)
 * and their analysis by a supervisor other than the report's technician; and the findings to
 * charge customers (marked charged by commercial — billing happens outside Horizon).
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { ApiError } from '@/api'
import { useDateFormat } from '@/composables/useDateFormat'
import { useAuthStore } from '@/stores/auth'
import { useNotificationsStore } from '@/stores/notifications'
import { formatMoney } from '@/utils/money'
import {
  analyzeDispute,
  decideDispute,
  listCharges,
  listDisputes,
  markCharged,
  type ChargeFinding,
  type Dispute,
  type DisputeDecision,
  type DisputeStatus,
} from './api'
import { useInventoryRoles } from './roles'

const { t, locale } = useI18n()
const { d } = useDateFormat()
const router = useRouter()
const auth = useAuthStore()
const notifications = useNotificationsStore()
const { isSupervisor, canSend } = useInventoryRoles()

const tab = ref('disputes')
const status = ref<DisputeStatus | null>(null)
const disputes = ref<Dispute[]>([])
const charges = ref<ChargeFinding[]>([])
const chargeStatus = ref<'chargeable' | 'charged'>('chargeable')
const loading = ref(false)

const COLORS: Record<DisputeStatus, string | undefined> = {
  open: 'warning',
  in_analysis: 'info',
  decided: 'success',
  escalated: 'error',
}
const statusOptions = computed(() => [
  { value: null, title: t('common.filters.all') },
  ...(['open', 'in_analysis', 'escalated', 'decided'] as const).map((value) => ({
    value,
    title: t(`inventory.disputes.statuses.${value}`),
  })),
])

async function load() {
  loading.value = true
  try {
    disputes.value = (
      await listDisputes({
        page: 1,
        pageSize: 200,
        filters: status.value ? { status: status.value } : {},
      })
    ).results
    charges.value = (
      await listCharges({ page: 1, pageSize: 200, filters: { status: chargeStatus.value } })
    ).results
  } finally {
    loading.value = false
  }
}
onMounted(load)
watch([status, chargeStatus], load)

function fail(error: unknown) {
  notifications.notify(error instanceof ApiError ? error.message : t('common.saveError'), 'error')
}

// --- Analysis and decision -----------------------------------------------------------------------

const open = ref(false)
const shown = ref<Dispute | null>(null)
const decision = ref<DisputeDecision>('rejected')
const notes = ref('')
const upheld = ref<number[]>([])
const reinspected = ref(false)
const error = ref('')

function show(dispute: Dispute) {
  shown.value = dispute
  decision.value = 'rejected'
  notes.value = ''
  upheld.value = []
  reinspected.value = false
  error.value = ''
  open.value = true
}

const ownReport = computed(() => shown.value?.report_technician === auth.user?.id)

async function analyze() {
  if (!shown.value) return
  try {
    shown.value = await analyzeDispute(shown.value.id)
    await load()
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : t('common.saveError')
  }
}

async function decide() {
  if (!shown.value) return
  try {
    shown.value = await decideDispute(shown.value.id, {
      decision: decision.value,
      notes: notes.value,
      upheld_findings: upheld.value,
      reinspected: reinspected.value,
    })
    notifications.notify(t('inventory.disputes.decided'))
    await load()
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : t('common.saveError')
  }
}

async function charge(finding: ChargeFinding) {
  try {
    await markCharged(finding.id)
    notifications.notify(t('inventory.charges.marked'))
    await load()
  } catch (e) {
    fail(e)
  }
}

const day = (value: string) => d(new Date(`${value}T12:00`), 'short')
const money = (value: string | null) => (value ? formatMoney(value, 'BRL', locale.value) : '—')
const totalCharges = computed(() =>
  charges.value.reduce((sum, f) => sum + (f.value ? Number(f.value) : 0), 0).toFixed(2),
)
</script>

<template>
  <v-container fluid class="module-page">
    <h1 class="mb-1">{{ $t('inventory.disputes.title') }}</h1>
    <p class="text-medium-emphasis mb-4">{{ $t('inventory.disputes.subtitle') }}</p>

    <v-card :loading="loading">
      <v-tabs v-model="tab">
        <v-tab value="disputes" data-testid="tab-disputes">{{
          $t('inventory.disputes.tab')
        }}</v-tab>
        <v-tab value="charges" data-testid="tab-charges">{{ $t('inventory.charges.tab') }}</v-tab>
      </v-tabs>
      <v-divider />
      <v-card-text>
        <v-window v-model="tab">
          <v-window-item value="disputes">
            <v-select
              v-model="status"
              :items="statusOptions"
              :label="$t('inventory.fields.status')"
              density="compact"
              style="max-width: 240px"
              class="mb-2"
            />
            <v-table density="comfortable" data-testid="disputes">
              <thead>
                <tr>
                  <th>{{ $t('inventory.fields.horizonId') }}</th>
                  <th>{{ $t('inventory.appointments.customer') }}</th>
                  <th>{{ $t('inventory.disputes.findings') }}</th>
                  <th>{{ $t('inventory.disputes.analysisDue') }}</th>
                  <th>{{ $t('inventory.fields.status') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="dispute in disputes"
                  :key="dispute.id"
                  class="cursor-pointer"
                  @click="show(dispute)"
                >
                  <td>
                    <div class="font-weight-medium">
                      {{ dispute.asset_detail.horizon_id }} · v{{ dispute.report_version }}
                    </div>
                    <div class="text-caption text-medium-emphasis">
                      {{ dispute.asset_detail.model }}
                    </div>
                  </td>
                  <td>{{ dispute.asset_detail.customer ?? '—' }}</td>
                  <td>{{ dispute.findings_detail.length }}</td>
                  <td>{{ day(dispute.analysis_due) }}</td>
                  <td>
                    <v-chip :color="COLORS[dispute.status]" size="small" variant="tonal" label>
                      {{ $t(`inventory.disputes.statuses.${dispute.status}`) }}
                    </v-chip>
                  </td>
                </tr>
                <tr v-if="!disputes.length">
                  <td colspan="5" class="text-medium-emphasis">
                    {{ $t('inventory.disputes.empty') }}
                  </td>
                </tr>
              </tbody>
            </v-table>
          </v-window-item>

          <v-window-item value="charges">
            <div class="d-flex align-center ga-3 mb-2">
              <v-btn-toggle
                v-model="chargeStatus"
                mandatory
                density="compact"
                variant="outlined"
                divided
              >
                <v-btn value="chargeable">{{ $t('inventory.charges.chargeable') }}</v-btn>
                <v-btn value="charged">{{ $t('inventory.charges.charged') }}</v-btn>
              </v-btn-toggle>
              <v-spacer />
              <span class="text-subtitle-1"
                >{{ $t('inventory.reports.total') }}:
                <strong>{{ money(totalCharges) }}</strong></span
              >
            </div>
            <v-table density="comfortable" data-testid="charges">
              <thead>
                <tr>
                  <th>{{ $t('inventory.appointments.customer') }}</th>
                  <th>{{ $t('inventory.fields.horizonId') }}</th>
                  <th>{{ $t('inventory.findings.kind') }}</th>
                  <th class="text-right">{{ $t('inventory.penalties.value') }}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                <tr v-for="f in charges" :key="f.id">
                  <td>{{ f.asset_detail.customer ?? '—' }}</td>
                  <td>
                    <a
                      class="text-primary cursor-pointer"
                      @click="
                        router.push({ name: 'inventory-report', params: { id: f.report_id } })
                      "
                    >
                      {{ f.asset_detail.horizon_id }}
                    </a>
                  </td>
                  <td>
                    {{ $t(`inventory.findings.kinds.${f.kind}`) }}
                    <span class="text-caption">{{ f.item || f.description }}</span>
                  </td>
                  <td class="text-right">{{ money(f.value) }}</td>
                  <td class="text-right">
                    <v-btn
                      v-if="canSend && chargeStatus === 'chargeable'"
                      size="small"
                      variant="tonal"
                      data-testid="mark-charged"
                      @click="charge(f)"
                    >
                      {{ $t('inventory.charges.markCharged') }}
                    </v-btn>
                  </td>
                </tr>
                <tr v-if="!charges.length">
                  <td colspan="5" class="text-medium-emphasis">
                    {{ $t('inventory.charges.empty') }}
                  </td>
                </tr>
              </tbody>
            </v-table>
          </v-window-item>
        </v-window>
      </v-card-text>
    </v-card>

    <v-dialog v-model="open" max-width="760">
      <v-card
        v-if="shown"
        :title="`${shown.asset_detail.horizon_id} · v${shown.report_version}`"
        :subtitle="shown.asset_detail.customer ?? ''"
      >
        <v-card-text>
          <div class="text-subtitle-2 mb-1">{{ $t('inventory.disputes.justification') }}</div>
          <p class="text-body-2 mb-3">{{ shown.justification }}</p>
          <div class="text-subtitle-2 mb-1">{{ $t('inventory.disputes.findings') }}</div>
          <v-list density="compact" class="mb-3">
            <v-list-item v-for="f in shown.findings_detail" :key="f.id" class="px-0">
              <template
                v-if="decision === 'partially_upheld' && shown.status !== 'decided'"
                #prepend
              >
                <v-checkbox-btn v-model="upheld" :value="f.id" density="compact" />
              </template>
              <v-list-item-title
                >{{ $t(`inventory.findings.kinds.${f.kind}`) }} ·
                {{ f.item || f.description }}</v-list-item-title
              >
              <v-list-item-subtitle>{{ money(f.value) }}</v-list-item-subtitle>
            </v-list-item>
          </v-list>
          <p class="text-caption text-medium-emphasis">
            {{
              $t('inventory.disputes.registeredBy', {
                name: shown.registered_by_name,
                date: d(new Date(shown.registered_at), 'dateTime'),
              })
            }}
            <template v-if="shown.analyst_name">
              · {{ $t('inventory.disputes.analyst') }}: {{ shown.analyst_name }}</template
            >
          </p>

          <template v-if="shown.status === 'decided'">
            <v-alert type="success" variant="tonal" density="compact">
              {{ $t(`inventory.disputes.decisions.${shown.decision}`) }} —
              {{ shown.decision_notes }}
            </v-alert>
          </template>
          <template v-else-if="isSupervisor">
            <v-alert v-if="ownReport" type="info" variant="tonal" density="compact" class="mb-2">
              {{ $t('inventory.disputes.ownReport') }}
            </v-alert>
            <template v-else-if="shown.status !== 'in_analysis'">
              <v-btn color="primary" variant="tonal" data-testid="analyze" @click="analyze">{{
                $t('inventory.disputes.analyze')
              }}</v-btn>
            </template>
            <template v-else>
              <v-radio-group v-model="decision" inline>
                <v-radio
                  v-for="value in ['upheld', 'partially_upheld', 'rejected'] as const"
                  :key="value"
                  :value="value"
                  :label="$t(`inventory.disputes.decisions.${value}`)"
                />
              </v-radio-group>
              <p v-if="decision === 'partially_upheld'" class="text-caption text-medium-emphasis">
                {{ $t('inventory.disputes.partialHint') }}
              </p>
              <v-checkbox
                v-model="reinspected"
                :label="$t('inventory.disputes.reinspected')"
                hide-details
                density="compact"
              />
              <v-textarea
                v-model="notes"
                :label="$t('inventory.disputes.decisionNotes')"
                rows="2"
                auto-grow
                data-testid="decision-notes"
              />
            </template>
          </template>
          <v-alert v-if="error" type="error" variant="tonal" density="compact" class="mt-2">{{
            error
          }}</v-alert>
        </v-card-text>
        <v-card-actions>
          <v-btn
            variant="text"
            @click="
              router.push({
                name: 'inventory-report',
                params: { id: shown.new_report ?? shown.report },
              })
            "
          >
            {{ $t('inventory.disputes.openReport') }}
          </v-btn>
          <v-spacer />
          <v-btn variant="text" @click="open = false">{{ $t('common.close') }}</v-btn>
          <v-btn
            v-if="isSupervisor && shown.status === 'in_analysis' && !ownReport"
            color="primary"
            variant="flat"
            data-testid="decide-dispute"
            @click="decide"
          >
            {{ $t('inventory.disputes.decide') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>
