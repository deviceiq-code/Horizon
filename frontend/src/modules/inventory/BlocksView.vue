<script setup lang="ts">
/**
 * Access blocks the customers must release (cloud account, MDM, BIOS password…), by due date.
 * Commercial marks them notified (the deadline starts; a notice is printed per customer) and
 * records a release the customer reports; a technician checks it (released → back to
 * inspection); expired ones wait for a supervisor's decision (parts, scrap or other).
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import { useDateFormat } from '@/composables/useDateFormat'
import { useNotificationsStore } from '@/stores/notifications'
import { formatMoney } from '@/utils/money'
import {
  checkBlockRelease,
  decideBlock,
  listBlocks,
  notifyBlocks,
  reportBlockRelease,
  type BlockFollowUp,
  type BlockStatus,
} from './api'
import { escapeHtml, printDocument } from './labels'
import { useInventoryRoles } from './roles'

const { t, locale } = useI18n()
const { d } = useDateFormat()
const notifications = useNotificationsStore()
const { canSend, canInspect, isSupervisor } = useInventoryRoles()

const status = ref<BlockStatus | null>('open')
const search = ref('')
const rows = ref<BlockFollowUp[]>([])
const selected = ref<number[]>([])
const loading = ref(false)

const STATUSES: BlockStatus[] = ['open', 'release_reported', 'expired', 'released', 'closed']
const COLORS: Record<BlockStatus, string | undefined> = {
  open: 'warning',
  release_reported: 'info',
  expired: 'error',
  released: 'success',
  closed: undefined,
}
const statusOptions = computed(() => [
  { value: null, title: t('common.filters.all') },
  ...STATUSES.map((value) => ({ value, title: t(`inventory.blocks.statuses.${value}`) })),
])

async function load() {
  loading.value = true
  try {
    rows.value = (
      await listBlocks({
        page: 1,
        pageSize: 200,
        search: search.value,
        filters: status.value ? { status: status.value } : {},
      })
    ).results
    selected.value = []
  } finally {
    loading.value = false
  }
}
onMounted(load)
watch(status, load)

async function run(call: () => Promise<unknown>, message: string) {
  try {
    await call()
    notifications.notify(t(message))
    await load()
  } catch (error) {
    notifications.notify(error instanceof ApiError ? error.message : t('common.saveError'), 'error')
  }
}

const notify = () => run(() => notifyBlocks(selected.value), 'inventory.blocks.notified')
const reportRelease = (b: BlockFollowUp) =>
  run(() => reportBlockRelease(b.id), 'inventory.blocks.releaseReported')
const check = (b: BlockFollowUp, released: boolean) =>
  run(
    () => checkBlockRelease(b.id, released),
    released ? 'inventory.blocks.released' : 'inventory.blocks.notReleased',
  )

// --- Expired: decision ---------------------------------------------------------------------------

const decideOpen = ref(false)
const deciding = ref<BlockFollowUp | null>(null)
const decision = ref<'parts' | 'scrap' | 'other'>('scrap')
const decisionNotes = ref('')
function openDecide(b: BlockFollowUp) {
  deciding.value = b
  decision.value = 'scrap'
  decisionNotes.value = ''
  decideOpen.value = true
}
async function decide() {
  if (!deciding.value) return
  await run(
    () => decideBlock(deciding.value!.id, decision.value, decisionNotes.value),
    'inventory.blocks.decided',
  )
  decideOpen.value = false
}

// --- Notice to the customer (printable) --------------------------------------------------------

function printNotice() {
  const chosen = rows.value.filter((r) => selected.value.includes(r.id))
  const list = chosen.length ? chosen : rows.value
  const byCustomer = new Map<string, BlockFollowUp[]>()
  for (const row of list) {
    const key = row.asset_detail.customer ?? '—'
    byCustomer.set(key, [...(byCustomer.get(key) ?? []), row])
  }
  const sections = [...byCustomer.entries()]
    .map(
      ([customer, items]) => `<section>
  <h2>${escapeHtml(customer)}</h2>
  <p>${escapeHtml(t('inventory.blocks.noticeText'))}</p>
  <table><thead><tr>
    <th>${escapeHtml(t('inventory.fields.horizonId'))}</th><th>${escapeHtml(t('inventory.fields.asset'))}</th>
    <th>${escapeHtml(t('inventory.fields.serial'))}</th><th>${escapeHtml(t('inventory.findings.blockType'))}</th>
    <th>${escapeHtml(t('inventory.blocks.dueDate'))}</th></tr></thead><tbody>
  ${items
    .map(
      (
        r,
      ) => `<tr><td>${escapeHtml(r.asset_detail.horizon_id)}</td><td>${escapeHtml(r.asset_detail.model)}</td>
      <td>${escapeHtml(r.asset_detail.serial || '—')}</td><td>${escapeHtml(t(`inventory.findings.blockTypes.${r.block_type}`))}</td>
      <td>${r.due_date ? escapeHtml(d(new Date(`${r.due_date}T12:00`), 'short')) : '—'}</td></tr>`,
    )
    .join('')}
  </tbody></table></section>`,
    )
    .join('')
  printDocument(`<!doctype html><html><head><meta charset="utf-8"><title>${escapeHtml(t('inventory.blocks.notice'))}</title>
<style>body{font-family:Arial,sans-serif;font-size:11pt;margin:20mm}section{page-break-after:always}
section:last-child{page-break-after:auto}table{border-collapse:collapse;width:100%}
th,td{border:1px solid #999;padding:4px 6px;text-align:left}h1{font-size:16pt}h2{font-size:13pt}</style></head>
<body><h1>${escapeHtml(t('inventory.blocks.notice'))}</h1>${sections}</body></html>`)
}

const day = (value: string | null) => (value ? d(new Date(`${value}T12:00`), 'short') : '—')
const money = (value: string | null) => (value ? formatMoney(value, 'BRL', locale.value) : '—')
const selectable = (b: BlockFollowUp) => b.status === 'open' && !b.notified_at
</script>

<template>
  <v-container fluid class="module-page">
    <h1 class="mb-1">{{ $t('inventory.blocks.title') }}</h1>
    <p class="text-medium-emphasis mb-4">{{ $t('inventory.blocks.subtitle') }}</p>

    <div class="d-flex flex-wrap align-center ga-3 mb-4">
      <v-select
        v-model="status"
        :items="statusOptions"
        :label="$t('inventory.fields.status')"
        density="compact"
        hide-details
        style="max-width: 240px"
      />
      <v-text-field
        v-model="search"
        :placeholder="$t('inventory.blocks.searchPlaceholder')"
        prepend-inner-icon="mdi-magnify"
        density="compact"
        hide-details
        clearable
        style="max-width: 360px"
        @keydown.enter.prevent="load"
        @click:clear="((search = ''), load())"
      />
      <v-spacer />
      <v-btn
        variant="text"
        prepend-icon="mdi-printer-outline"
        :disabled="!rows.length"
        data-testid="print-notice"
        @click="printNotice"
      >
        {{ $t('inventory.blocks.printNotice') }}
      </v-btn>
      <v-btn
        v-if="canSend"
        color="primary"
        prepend-icon="mdi-email-send-outline"
        :disabled="!selected.length"
        data-testid="notify"
        @click="notify"
      >
        {{ $t('inventory.blocks.markNotified', selected.length) }}
      </v-btn>
    </div>

    <v-card :loading="loading">
      <v-table density="comfortable" data-testid="blocks">
        <thead>
          <tr>
            <th style="width: 40px" />
            <th>{{ $t('inventory.fields.horizonId') }}</th>
            <th>{{ $t('inventory.appointments.customer') }}</th>
            <th>{{ $t('inventory.findings.blockType') }}</th>
            <th>{{ $t('inventory.blocks.dueDate') }}</th>
            <th class="text-right">{{ $t('inventory.penalties.value') }}</th>
            <th>{{ $t('inventory.fields.status') }}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          <tr v-for="b in rows" :key="b.id" data-testid="block-row">
            <td>
              <v-checkbox-btn
                v-if="canSend && selectable(b)"
                v-model="selected"
                :value="b.id"
                density="compact"
              />
            </td>
            <td>
              <div class="font-weight-medium">{{ b.asset_detail.horizon_id }}</div>
              <div class="text-caption text-medium-emphasis">{{ b.asset_detail.model }}</div>
            </td>
            <td>{{ b.asset_detail.customer ?? '—' }}</td>
            <td>{{ $t(`inventory.findings.blockTypes.${b.block_type}`) }}</td>
            <td>
              <template v-if="b.due_date">
                {{ day(b.due_date) }}
                <v-chip
                  v-if="b.days_left !== null && ['open', 'release_reported'].includes(b.status)"
                  :color="b.days_left < 0 ? 'error' : b.days_left <= 3 ? 'warning' : undefined"
                  size="x-small"
                  label
                  class="ml-1"
                >
                  {{
                    b.days_left < 0
                      ? $t('inventory.blocks.overdue', { n: -b.days_left })
                      : $t('inventory.blocks.daysLeft', b.days_left)
                  }}
                </v-chip>
              </template>
              <span v-else class="text-medium-emphasis">{{
                $t('inventory.blocks.notNotified')
              }}</span>
            </td>
            <td class="text-right">{{ money(b.finding_value) }}</td>
            <td>
              <v-chip :color="COLORS[b.status]" size="small" variant="tonal" label>
                {{ $t(`inventory.blocks.statuses.${b.status}`) }}
              </v-chip>
              <div v-if="b.decision" class="text-caption">
                {{ $t(`inventory.blocks.decisions.${b.decision}`)
                }}<template v-if="b.decision_notes"> · {{ b.decision_notes }}</template>
              </div>
            </td>
            <td class="text-right text-no-wrap">
              <v-btn
                v-if="canSend && b.status === 'open' && b.notified_at"
                size="small"
                variant="tonal"
                data-testid="report-release"
                @click="reportRelease(b)"
              >
                {{ $t('inventory.blocks.reportRelease') }}
              </v-btn>
              <template v-if="canInspect && b.status === 'release_reported'">
                <v-btn
                  size="small"
                  variant="tonal"
                  color="success"
                  class="mr-1"
                  data-testid="released"
                  @click="check(b, true)"
                >
                  {{ $t('inventory.blocks.confirmRelease') }}
                </v-btn>
                <v-btn
                  size="small"
                  variant="tonal"
                  color="error"
                  data-testid="not-released"
                  @click="check(b, false)"
                >
                  {{ $t('inventory.blocks.denyRelease') }}
                </v-btn>
              </template>
              <v-btn
                v-if="isSupervisor && b.status === 'expired'"
                size="small"
                variant="tonal"
                color="primary"
                data-testid="decide"
                @click="openDecide(b)"
              >
                {{ $t('inventory.blocks.decide') }}
              </v-btn>
            </td>
          </tr>
          <tr v-if="!rows.length && !loading">
            <td colspan="8" class="text-medium-emphasis">{{ $t('inventory.blocks.empty') }}</td>
          </tr>
        </tbody>
      </v-table>
    </v-card>

    <v-dialog v-model="decideOpen" max-width="520">
      <v-card :title="$t('inventory.blocks.decide')">
        <v-card-text>
          <p class="text-body-2 text-medium-emphasis mb-3">
            {{ $t('inventory.blocks.decideHint') }}
          </p>
          <v-radio-group v-model="decision">
            <v-radio
              v-for="value in ['scrap', 'parts', 'other'] as const"
              :key="value"
              :value="value"
              :label="$t(`inventory.blocks.decisions.${value}`)"
            />
          </v-radio-group>
          <v-textarea
            v-model="decisionNotes"
            :label="$t('inventory.blocks.decisionNotes')"
            rows="2"
            auto-grow
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="decideOpen = false">{{ $t('common.cancel') }}</v-btn>
          <v-btn color="primary" variant="flat" data-testid="decide-save" @click="decide">{{
            $t('common.save')
          }}</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>
