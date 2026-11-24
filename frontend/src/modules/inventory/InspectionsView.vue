<script setup lang="ts">
/**
 * Inspection: the queue (assets awaiting inspection), reports in progress, reports awaiting
 * approval (supervisors approve them) and the latest approved. "Start Inspection" reads the
 * asset and the bench with the gun.
 */
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { ApiError } from '@/api'
import { useDateFormat } from '@/composables/useDateFormat'
import AreaChip from './AreaChip.vue'
import { listAssets, listReports, startInspection, type Asset, type ReportSummary } from './api'
import { useInventoryRoles } from './roles'

const { t } = useI18n()
const { d } = useDateFormat()
const router = useRouter()
const { canInspect } = useInventoryRoles()

const tab = ref('queue')
const queue = ref<Asset[]>([])
const drafts = ref<ReportSummary[]>([])
const awaiting = ref<ReportSummary[]>([])
const approved = ref<ReportSummary[]>([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const [q, dr, aw, ap] = await Promise.all([
      listAssets({
        page: 1,
        pageSize: 100,
        ordering: 'updated_at',
        filters: { status: 'awaiting_inspection' },
      }),
      listReports({ page: 1, pageSize: 100, filters: { status: 'draft' } }),
      listReports({
        page: 1,
        pageSize: 100,
        ordering: 'finished_at',
        filters: { status: 'awaiting_approval' },
      }),
      listReports({
        page: 1,
        pageSize: 50,
        ordering: '-approved_at',
        filters: { status: 'approved' },
      }),
    ])
    queue.value = q.results
    drafts.value = dr.results
    awaiting.value = aw.results
    approved.value = ap.results
  } finally {
    loading.value = false
  }
}
onMounted(load)

// --- Start -------------------------------------------------------------------------------------

const startOpen = ref(false)
const assetCode = ref('')
const benchCode = ref('')
const startError = ref('')
const starting = ref(false)
const benchField = ref<{ focus: () => void } | null>(null)

function openStart(asset?: Asset) {
  assetCode.value = asset?.horizon_id ?? ''
  startError.value = ''
  startOpen.value = true
}

async function start() {
  starting.value = true
  startError.value = ''
  try {
    const report = await startInspection(assetCode.value, benchCode.value)
    startOpen.value = false
    router.push({ name: 'inventory-report', params: { id: report.id } })
  } catch (error) {
    startError.value = error instanceof ApiError ? error.message : t('common.saveError')
  } finally {
    starting.value = false
  }
}

function open(report: ReportSummary) {
  router.push({ name: 'inventory-report', params: { id: report.id } })
}

const when = (value: string | null) => (value ? d(new Date(value), 'dateTime') : '—')
</script>

<template>
  <v-container fluid class="module-page">
    <div class="d-flex flex-wrap align-center ga-3 mb-1">
      <h1>{{ $t('inventory.inspections.title') }}</h1>
      <v-spacer />
      <v-btn
        v-if="canInspect"
        color="primary"
        prepend-icon="mdi-barcode-scan"
        data-testid="start"
        @click="openStart()"
      >
        {{ $t('inventory.inspections.start') }}
      </v-btn>
    </div>
    <p class="text-medium-emphasis mb-4">{{ $t('inventory.inspections.subtitle') }}</p>

    <v-card :loading="loading">
      <v-tabs v-model="tab">
        <v-tab value="queue" data-testid="tab-queue">
          {{ $t('inventory.inspections.queue') }}
          <v-chip size="x-small" class="ml-2">{{ queue.length }}</v-chip>
        </v-tab>
        <v-tab value="drafts" data-testid="tab-drafts">
          {{ $t('inventory.inspections.inProgress') }}
          <v-chip size="x-small" class="ml-2">{{ drafts.length }}</v-chip>
        </v-tab>
        <v-tab value="awaiting" data-testid="tab-awaiting">
          {{ $t('inventory.inspections.awaitingApproval') }}
          <v-chip size="x-small" :color="awaiting.length ? 'warning' : undefined" class="ml-2">{{
            awaiting.length
          }}</v-chip>
        </v-tab>
        <v-tab value="approved">{{ $t('inventory.inspections.approved') }}</v-tab>
      </v-tabs>
      <v-divider />
      <v-card-text>
        <v-window v-model="tab">
          <v-window-item value="queue">
            <v-table density="comfortable" data-testid="queue">
              <thead>
                <tr>
                  <th>{{ $t('inventory.fields.horizonId') }}</th>
                  <th>{{ $t('inventory.fields.asset') }}</th>
                  <th>{{ $t('inventory.fields.location') }}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                <tr v-for="a in queue" :key="a.id">
                  <td class="font-weight-medium">{{ a.horizon_id }}</td>
                  <td>
                    {{ a.asset_model_detail.manufacturer_name }} {{ a.asset_model_detail.name }}
                  </td>
                  <td>
                    {{ a.current_location_detail.code }}
                    <AreaChip
                      :area="a.current_location_detail.area_type"
                      size="x-small"
                      class="ml-1"
                    />
                  </td>
                  <td class="text-right">
                    <v-btn v-if="canInspect" size="small" variant="tonal" @click="openStart(a)">
                      {{ $t('inventory.inspections.start') }}
                    </v-btn>
                  </td>
                </tr>
                <tr v-if="!queue.length">
                  <td colspan="4" class="text-medium-emphasis">
                    {{ $t('inventory.inspections.emptyQueue') }}
                  </td>
                </tr>
              </tbody>
            </v-table>
          </v-window-item>
          <v-window-item
            v-for="key in ['drafts', 'awaiting', 'approved'] as const"
            :key="key"
            :value="key"
          >
            <v-table density="comfortable" :data-testid="`reports-${key}`">
              <thead>
                <tr>
                  <th>{{ $t('inventory.fields.horizonId') }}</th>
                  <th>{{ $t('inventory.fields.asset') }}</th>
                  <th>{{ $t('inventory.reports.grade') }}</th>
                  <th>{{ $t('inventory.reports.technician') }}</th>
                  <th>
                    {{
                      key === 'approved'
                        ? $t('inventory.reports.approvedAt')
                        : key === 'awaiting'
                          ? $t('inventory.reports.finishedAt')
                          : $t('inventory.reports.startedAt')
                    }}
                  </th>
                  <th />
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="r in key === 'drafts' ? drafts : key === 'awaiting' ? awaiting : approved"
                  :key="r.id"
                  class="cursor-pointer"
                  @click="open(r)"
                >
                  <td class="font-weight-medium">
                    {{ r.asset_code }} <span class="text-caption">v{{ r.version }}</span>
                  </td>
                  <td>{{ r.asset_model_label }}</td>
                  <td class="font-weight-bold">{{ r.grade || '—' }}</td>
                  <td>{{ r.technician_name }}</td>
                  <td>
                    {{
                      when(
                        key === 'approved'
                          ? r.approved_at
                          : key === 'awaiting'
                            ? r.finished_at
                            : r.started_at,
                      )
                    }}
                  </td>
                  <td class="text-right"><v-icon icon="mdi-chevron-right" /></td>
                </tr>
                <tr
                  v-if="
                    !(key === 'drafts' ? drafts : key === 'awaiting' ? awaiting : approved).length
                  "
                >
                  <td colspan="6" class="text-medium-emphasis">
                    {{ $t('inventory.inspections.emptyReports') }}
                  </td>
                </tr>
              </tbody>
            </v-table>
          </v-window-item>
        </v-window>
      </v-card-text>
    </v-card>

    <v-dialog v-model="startOpen" max-width="520">
      <v-card :title="$t('inventory.inspections.start')">
        <v-card-text>
          <v-text-field
            v-model="assetCode"
            :label="$t('inventory.inspections.readAsset')"
            prepend-inner-icon="mdi-barcode-scan"
            autocomplete="off"
            autofocus
            data-testid="start-asset"
            @keydown.enter.prevent="benchField?.focus()"
          />
          <v-text-field
            ref="benchField"
            v-model="benchCode"
            :label="$t('inventory.inspections.readBench')"
            prepend-inner-icon="mdi-barcode-scan"
            autocomplete="off"
            :error-messages="startError"
            data-testid="start-bench"
            @keydown.enter.prevent="start"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="startOpen = false">{{ $t('common.cancel') }}</v-btn>
          <v-btn
            color="primary"
            variant="flat"
            :loading="starting"
            data-testid="start-confirm"
            @click="start"
          >
            {{ $t('inventory.inspections.start') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>
