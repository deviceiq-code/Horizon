<script setup lang="ts">
/** One asset: identification, specifications, where it is and its whole history of events
 * (newest first). Its label can be printed again (same Horizon ID — RN-16). */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { ApiError } from '@/api'
import AssetModelPicker from '@/modules/catalogs/asset-models/AssetModelPicker.vue'
import FormDialog from '@/components/FormDialog.vue'
import { useDateFormat } from '@/composables/useDateFormat'
import { useNumberFormat } from '@/composables/useNumberFormat'
import { specText } from '@/modules/average-prices/specText'
import { useNotificationsStore } from '@/stores/notifications'
import AreaChip from './AreaChip.vue'
import StatusChip from './StatusChip.vue'
import {
  assetReports,
  disassemble,
  getAsset,
  newReportVersion,
  reprintAsset,
  type AssetDetail,
  type MovementEvent,
  type ReportSummary,
} from './api'
import { useInventoryRoles } from './roles'
import { printLabels } from './labels'

const props = defineProps<{ assetId: number | null }>()
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ changed: [] }>()

const { t } = useI18n()
const { d } = useDateFormat()
const { n } = useNumberFormat()
const notifications = useNotificationsStore()

const asset = ref<AssetDetail | null>(null)
const loading = ref(false)
const loadError = ref(false)

const reports = ref<ReportSummary[]>([])

watch(open, async (isOpen) => {
  if (!isOpen || props.assetId === null) return
  asset.value = null
  reports.value = []
  loadError.value = false
  loading.value = true
  try {
    asset.value = await getAsset(props.assetId)
    reports.value = await assetReports(props.assetId)
  } catch {
    loadError.value = true
  } finally {
    loading.value = false
  }
})

// --- Reports, new version, part harvesting ------------------------------------------------------

const router = useRouter()
const { canInspect } = useInventoryRoles()
const hasCurrent = computed(() => reports.value.some((r) => r.is_current))
const hasOpen = computed(() =>
  reports.value.some((r) => r.status === 'draft' || r.status === 'awaiting_approval'),
)

function openReport(id: number) {
  open.value = false
  router.push({ name: 'inventory-report', params: { id } })
}

const versionOpen = ref(false)
const versionReason = ref('')
const versionError = ref('')
async function createVersion() {
  if (!asset.value) return
  versionError.value = ''
  try {
    const { id } = await newReportVersion(asset.value.id, versionReason.value)
    versionOpen.value = false
    openReport(id)
  } catch (error) {
    versionError.value = error instanceof ApiError ? error.message : t('common.saveError')
  }
}

const partsOpen = ref(false)
const parts = ref<{ key: number; model: number | null; quantity: string; serial: string }[]>([])
const partsReason = ref('')
const partsError = ref('')
let partKey = 0
function openParts() {
  parts.value = [{ key: partKey++, model: null, quantity: '1', serial: '' }]
  partsReason.value = ''
  partsError.value = ''
  partsOpen.value = true
}
async function saveParts() {
  if (!asset.value) return
  partsError.value = ''
  try {
    await disassemble(
      asset.value.id,
      parts.value
        .filter((p) => p.model)
        .map((p) => ({
          asset_model: p.model!,
          quantity: Number(p.quantity) || 1,
          serial: p.serial,
        })),
      partsReason.value,
    )
    partsOpen.value = false
    notifications.notify(t('inventory.assets.disassembled'))
    asset.value = await getAsset(asset.value.id)
    emit('changed')
  } catch (error) {
    partsError.value = error instanceof ApiError ? error.message : t('common.saveError')
  }
}

const title = computed(() =>
  asset.value
    ? `${asset.value.asset_model_detail.manufacturer_name} ${asset.value.asset_model_detail.name}`
    : '',
)

async function reprint() {
  if (!asset.value) return
  try {
    await reprintAsset(asset.value.id)
    printLabels(
      [{ code: asset.value.horizon_id, title: title.value, subtitle: asset.value.serial }],
      asset.value.horizon_id,
    )
    asset.value = await getAsset(asset.value.id)
    emit('changed')
  } catch {
    notifications.notify(t('common.saveError'), 'error')
  }
}

function placeText(location: string | null, container: string | null): string {
  if (!location && !container) return '—'
  return container ? `${location ?? ''} · ${container}` : (location ?? '')
}

function eventPlaces(event: MovementEvent): string {
  const from = placeText(event.from_location_code, event.from_container_code)
  const to = placeText(event.to_location_code, event.to_container_code)
  if (event.kind === 'label_reprint') return ''
  return event.from_location_code ? `${from} → ${to}` : to
}
</script>

<template>
  <FormDialog
    v-model="open"
    :title="asset?.horizon_id ?? $t('inventory.assets.details')"
    :subtitle="title || null"
    icon="mdi-package-variant-closed"
    max-width="880"
    @submit="open = false"
  >
    <template v-if="asset" #heading-end>
      <v-chip
        v-if="asset.condition_grade"
        color="primary"
        variant="flat"
        label
        class="mr-2 font-weight-bold"
        :title="$t('inventory.reports.grade')"
        data-testid="asset-grade"
      >
        {{ asset.condition_grade }}
      </v-chip>
      <StatusChip :status="asset.status" :held="asset.held_for_dispute" size="default" />
    </template>

    <v-progress-linear v-if="loading" indeterminate class="mb-4" />
    <v-alert v-if="loadError" type="error" variant="tonal">{{ $t('common.loadError') }}</v-alert>

    <template v-if="asset">
      <v-row dense>
        <v-col cols="12" md="6">
          <div class="text-subtitle-2 text-medium-emphasis mb-2">
            {{ $t('inventory.assets.identification') }}
          </div>
          <v-table density="compact" class="detail-table">
            <tbody>
              <tr>
                <th>{{ $t('inventory.fields.assetClass') }}</th>
                <td>{{ asset.asset_model_detail.asset_class_name }}</td>
              </tr>
              <tr>
                <th>{{ $t('inventory.fields.serial') }}</th>
                <td>
                  {{ asset.serial || '—' }}
                  <span v-if="asset.serial_status !== 'captured'" class="text-medium-emphasis">
                    ({{ $t(`inventory.serialStatus.${asset.serial_status}`)
                    }}<template v-if="asset.no_serial_reason"
                      >: {{ $t(`inventory.noSerialReasons.${asset.no_serial_reason}`) }}</template
                    >)
                  </span>
                </td>
              </tr>
              <tr v-for="(value, key) in asset.other_ids" :key="key">
                <th>{{ $t(`inventory.otherIds.${key}`) }}</th>
                <td>{{ value }}</td>
              </tr>
              <tr>
                <th>{{ $t('inventory.fields.location') }}</th>
                <td>
                  <span class="d-inline-flex align-center flex-wrap ga-2">
                    <span v-if="asset.warehouse">{{ asset.warehouse.name }} ·</span>
                    {{ asset.current_location_detail.code }}
                    <AreaChip :area="asset.current_location_detail.area_type" size="x-small" />
                    <span v-if="asset.current_container_detail">
                      · {{ asset.current_container_detail.code }}
                    </span>
                  </span>
                </td>
              </tr>
              <tr>
                <th>{{ $t('inventory.fields.enteredAt') }}</th>
                <td>{{ d(new Date(asset.created_at), 'dateTime') }}</td>
              </tr>
            </tbody>
          </v-table>
        </v-col>
        <v-col cols="12" md="6">
          <div class="text-subtitle-2 text-medium-emphasis mb-2">
            {{ $t('inventory.assets.specs') }}
          </div>
          <v-table v-if="asset.specs.length" density="compact" class="detail-table">
            <tbody>
              <tr v-for="spec in asset.specs" :key="spec.key">
                <th>{{ spec.label }}</th>
                <td>{{ specText(spec, t, n) }}</td>
              </tr>
            </tbody>
          </v-table>
          <p v-else class="text-body-2 text-medium-emphasis">
            {{ $t('inventory.assets.noSpecs') }}
          </p>
        </v-col>
      </v-row>

      <div class="text-subtitle-2 text-medium-emphasis mb-2 mt-4">
        {{ $t('inventory.assets.reports') }}
      </div>
      <v-list v-if="reports.length" density="compact" data-testid="asset-reports">
        <v-list-item v-for="r in reports" :key="r.id" class="px-0" @click="openReport(r.id)">
          <v-list-item-title>
            v{{ r.version }} · {{ $t(`inventory.reports.statuses.${r.status}`) }}
            <strong v-if="r.grade"> · {{ r.grade }}</strong>
          </v-list-item-title>
          <v-list-item-subtitle>{{ r.technician_name }}</v-list-item-subtitle>
          <template #append><v-icon icon="mdi-chevron-right" /></template>
        </v-list-item>
      </v-list>
      <p v-else class="text-body-2 text-medium-emphasis">{{ $t('inventory.assets.noReports') }}</p>

      <div class="text-subtitle-2 text-medium-emphasis mb-2 mt-4">
        {{ $t('inventory.assets.history') }}
      </div>
      <v-timeline density="compact" side="end" truncate-line="both" data-testid="history">
        <v-timeline-item
          v-for="event in asset.events"
          :key="event.id"
          dot-color="primary"
          size="x-small"
        >
          <div class="d-flex flex-wrap align-center ga-2">
            <strong>{{ $t(`inventory.eventKinds.${event.kind}`) }}</strong>
            <span class="text-body-2">{{ eventPlaces(event) }}</span>
            <template v-if="event.status_before !== event.status_after && event.status_after">
              <StatusChip v-if="event.status_before" :status="event.status_before" size="x-small" />
              <v-icon v-if="event.status_before" icon="mdi-arrow-right" size="14" />
              <StatusChip :status="event.status_after" size="x-small" />
            </template>
          </div>
          <div class="text-caption text-medium-emphasis">
            {{ d(new Date(event.at), 'dateTime') }} · {{ event.user_name }}
            <template v-if="event.reason"> · {{ event.reason }}</template>
          </div>
        </v-timeline-item>
      </v-timeline>
    </template>

    <template #actions>
      <v-btn
        v-if="asset"
        variant="text"
        prepend-icon="mdi-printer-outline"
        data-testid="reprint"
        @click="reprint"
      >
        {{ $t('inventory.labels.reprint') }}
      </v-btn>
      <v-btn
        v-if="asset && canInspect && hasCurrent && !hasOpen && !asset.held_for_dispute"
        variant="text"
        prepend-icon="mdi-file-document-edit-outline"
        data-testid="new-version"
        @click="((versionReason = ''), (versionError = ''), (versionOpen = true))"
      >
        {{ $t('inventory.assets.newVersion') }}
      </v-btn>
      <v-btn
        v-if="asset && canInspect && asset.status === 'scrap'"
        variant="text"
        prepend-icon="mdi-hammer-wrench"
        data-testid="disassemble"
        @click="openParts"
      >
        {{ $t('inventory.assets.disassemble') }}
      </v-btn>
      <v-spacer />
      <v-btn color="primary" variant="flat" @click="open = false">{{ $t('common.close') }}</v-btn>
    </template>
  </FormDialog>

  <v-dialog v-model="versionOpen" max-width="520">
    <v-card :title="$t('inventory.assets.newVersion')">
      <v-card-text>
        <p class="text-body-2 text-medium-emphasis mb-3">
          {{ $t('inventory.assets.newVersionHint') }}
        </p>
        <v-textarea
          v-model="versionReason"
          :label="$t('inventory.reports.versionReason')"
          :error-messages="versionError"
          rows="2"
          auto-grow
          autofocus
          data-testid="version-reason"
        />
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="versionOpen = false">{{ $t('common.cancel') }}</v-btn>
        <v-btn color="primary" variant="flat" data-testid="version-create" @click="createVersion">
          {{ $t('inventory.assets.newVersion') }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <v-dialog v-model="partsOpen" max-width="720">
    <v-card :title="$t('inventory.assets.disassemble')">
      <v-card-text>
        <p class="text-body-2 text-medium-emphasis mb-3">
          {{ $t('inventory.assets.disassembleHint') }}
        </p>
        <v-row v-for="(part, index) in parts" :key="part.key" dense>
          <v-col cols="12" md="6">
            <AssetModelPicker
              v-model="part.model"
              :label="$t('inventory.fields.assetModel')"
              density="compact"
            />
          </v-col>
          <v-col cols="4" md="2">
            <v-text-field
              v-model="part.quantity"
              :label="$t('inventory.expected.quantity')"
              inputmode="numeric"
              density="compact"
            />
          </v-col>
          <v-col cols="6" md="3">
            <v-text-field
              v-model="part.serial"
              :label="$t('inventory.fields.serial')"
              density="compact"
            />
          </v-col>
          <v-col cols="2" md="1">
            <v-btn icon="mdi-close" size="small" variant="text" @click="parts.splice(index, 1)" />
          </v-col>
        </v-row>
        <v-btn
          variant="tonal"
          size="small"
          prepend-icon="mdi-plus"
          class="mb-3"
          @click="parts.push({ key: partKey++, model: null, quantity: '1', serial: '' })"
        >
          {{ $t('inventory.expected.addRow') }}
        </v-btn>
        <v-text-field
          v-model="partsReason"
          :label="$t('inventory.fields.reason')"
          density="compact"
        />
        <v-alert v-if="partsError" type="error" variant="tonal" density="compact">{{
          partsError
        }}</v-alert>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="partsOpen = false">{{ $t('common.cancel') }}</v-btn>
        <v-btn color="primary" variant="flat" data-testid="disassemble-save" @click="saveParts">
          {{ $t('inventory.assets.disassemble') }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.detail-table th {
  width: 40%;
  font-weight: 500;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
</style>
