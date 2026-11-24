<script setup lang="ts">
/**
 * An inventory count. While counting (blind — nothing expected is shown): read the location,
 * then each asset's ID (color + sound); accessories by model and quantity (at the location or
 * in a container there). Closing finds the divergences; each is an adjustment a supervisor who
 * did not count approves or rejects with a reason (RN-26).
 */
import { computed, nextTick, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import { useDateFormat } from '@/composables/useDateFormat'
import AssetModelPicker from '@/modules/catalogs/asset-models/AssetModelPicker.vue'
import { useNotificationsStore } from '@/stores/notifications'
import CountStatusChip from './CountStatusChip.vue'
import {
  cancelCount,
  closeCount,
  decideDivergence,
  deleteCountReading,
  getCount,
  listCountReadings,
  listDivergences,
  readCountAccessories,
  readCountAsset,
  type CountDivergence,
  type CountReading,
  type InventoryCountDetail,
} from './api'
import { beep } from './beep'
import { useInventoryRoles } from './roles'

const props = defineProps<{ id: number }>()

const { t } = useI18n()
const { d } = useDateFormat()
const notifications = useNotificationsStore()
const { canCount, isSupervisor } = useInventoryRoles()

const count = ref<InventoryCountDetail | null>(null)
const readings = ref<CountReading[]>([])
const divergences = ref<CountDivergence[]>([])
const failed = ref(false)
const tab = ref<'counting' | 'readings' | 'divergences'>('counting')

const counting = computed(() => count.value?.status === 'counting')

async function load() {
  try {
    count.value = await getCount(props.id)
    readings.value = await listCountReadings(props.id)
    if (!counting.value) {
      divergences.value = await listDivergences(props.id)
      tab.value = 'divergences'
    } else if (!canCount.value) tab.value = 'readings'
  } catch {
    failed.value = true
  }
}
onMounted(load)

function errorText(error: unknown) {
  return error instanceof ApiError ? error.message : t('common.saveError')
}

// --- Reading (scan) -------------------------------------------------------------------------------

const location = ref('')
const code = ref('')
const feedback = ref<{ ok: boolean; text: string } | null>(null)
const codeField = ref<{ focus: () => void } | null>(null)

function locationRead() {
  if (location.value.trim()) codeField.value?.focus()
}

async function readAsset() {
  const read = code.value.trim()
  if (!read) return
  try {
    readings.value = await readCountAsset(props.id, location.value.trim(), read)
    feedback.value = { ok: true, text: t('inventory.counts.read', { code: read }) }
    beep(true)
  } catch (error) {
    feedback.value = { ok: false, text: errorText(error) }
    beep(false)
  } finally {
    code.value = ''
    await nextTick()
    codeField.value?.focus()
  }
}

const accessoryModel = ref<number | null>(null)
const accessoryQuantity = ref('')
const accessoryContainer = ref('')
const accessoryCondition = ref<'good' | 'scrap'>('good')
const accessoryKey = ref(0)
async function readAccessories() {
  if (!accessoryModel.value) return
  try {
    readings.value = await readCountAccessories(props.id, {
      location: location.value.trim(),
      accessory_model: accessoryModel.value,
      quantity: Number(accessoryQuantity.value) || 0,
      container: accessoryContainer.value.trim(),
      condition: accessoryCondition.value,
    })
    accessoryModel.value = null
    accessoryQuantity.value = ''
    accessoryContainer.value = ''
    accessoryKey.value += 1
    beep(true)
  } catch (error) {
    notifications.notify(errorText(error), 'error')
    beep(false)
  }
}

async function removeReading(reading: CountReading) {
  try {
    await deleteCountReading(props.id, reading.id)
    readings.value = readings.value.filter((r) => r.id !== reading.id)
  } catch (error) {
    notifications.notify(errorText(error), 'error')
  }
}

// --- Close / cancel ----------------------------------------------------------------------------

const closing = ref(false)
async function close() {
  closing.value = true
  try {
    await closeCount(props.id)
    notifications.notify(t('inventory.counts.closed'))
    await load()
  } catch (error) {
    notifications.notify(errorText(error), 'error')
  } finally {
    closing.value = false
  }
}

const cancelOpen = ref(false)
const cancelReason = ref('')
async function cancel() {
  try {
    await cancelCount(props.id, cancelReason.value)
    cancelOpen.value = false
    await load()
  } catch (error) {
    notifications.notify(errorText(error), 'error')
  }
}

// --- Adjustments (RN-26) ----------------------------------------------------------------------------

const decideOpen = ref(false)
const deciding = ref<CountDivergence | null>(null)
const approving = ref(true)
const reason = ref('')
function openDecide(divergence: CountDivergence, approve: boolean) {
  deciding.value = divergence
  approving.value = approve
  reason.value = ''
  decideOpen.value = true
}
async function decide() {
  if (!deciding.value) return
  try {
    divergences.value = await decideDivergence(
      props.id,
      deciding.value.id,
      approving.value,
      reason.value,
    )
    decideOpen.value = false
    count.value = await getCount(props.id)
  } catch (error) {
    notifications.notify(errorText(error), 'error')
  }
}

function divergenceTarget(item: CountDivergence) {
  return (
    item.asset_code ??
    `${item.model_label ?? ''}${item.container_code ? ` · ${item.container_code}` : ''}`
  )
}
function divergenceDetail(item: CountDivergence) {
  switch (item.kind) {
    case 'not_found':
      return t('inventory.counts.detail.notFound', { location: item.expected_location_code })
    case 'other_location':
      return t('inventory.counts.detail.otherLocation', {
        expected: item.expected_location_code,
        found: item.found_location_code,
      })
    case 'unexpected':
      return t('inventory.counts.detail.unexpected', { found: item.found_location_code })
    default:
      return t('inventory.counts.detail.balance', {
        location: item.found_location_code,
        expected: item.expected_quantity,
        counted: item.counted_quantity,
      })
  }
}
const ADJUSTMENT_COLORS = { pending: 'warning', approved: 'success', rejected: undefined }
</script>

<template>
  <v-container fluid class="module-page">
    <v-alert v-if="failed" type="error" variant="tonal">{{ $t('common.loadError') }}</v-alert>
    <template v-else-if="count">
      <div class="d-flex flex-wrap align-center ga-3 mb-1">
        <h1>{{ count.code }}</h1>
        <CountStatusChip :status="count.status" />
        <span class="text-medium-emphasis"
          >{{ $t(`inventory.counts.kinds.${count.kind}`) }} · {{ count.warehouse_code }}</span
        >
        <v-spacer />
        <v-btn
          v-if="counting && isSupervisor"
          variant="text"
          color="error"
          prepend-icon="mdi-close-circle-outline"
          @click="((cancelReason = ''), (cancelOpen = true))"
          >{{ $t('inventory.counts.cancel') }}</v-btn
        >
        <v-btn
          v-if="counting && canCount"
          color="primary"
          prepend-icon="mdi-lock-check-outline"
          :loading="closing"
          data-testid="count-close"
          @click="close"
          >{{ $t('inventory.counts.close') }}</v-btn
        >
      </div>

      <v-card class="pa-4 mb-4">
        <div class="text-caption text-medium-emphasis mb-1">
          {{ $t('inventory.counts.scope') }} ·
          {{ $t('inventory.counts.locations', { n: count.locations_count }) }}
        </div>
        <div class="d-flex flex-wrap ga-1 mb-2">
          <v-chip
            v-for="locationCode in count.location_codes.slice(0, 30)"
            :key="locationCode"
            size="x-small"
            label
            >{{ locationCode }}</v-chip
          >
          <span v-if="count.location_codes.length > 30" class="text-caption"
            >+{{ count.locations_count - 30 }}</span
          >
        </div>
        <div class="text-caption text-medium-emphasis">
          {{
            $t('inventory.counts.openedBy', {
              name: count.created_by_name,
              date: d(new Date(count.created_at), 'dateTime'),
            })
          }}
          <template v-if="count.closed_at">
            ·
            {{
              $t('inventory.counts.closedBy', {
                name: count.closed_by_name ?? '',
                date: d(new Date(count.closed_at), 'dateTime'),
              })
            }}
          </template>
          <template v-if="count.accuracy !== null">
            ·
            {{
              $t('inventory.counts.accuracyText', {
                matched: count.matched_assets,
                expected: count.expected_assets,
                percent: $n(Number(count.accuracy), 'percentValue'),
              })
            }}
          </template>
          <template v-if="count.cancel_reason"> · {{ count.cancel_reason }}</template>
        </div>
        <v-alert
          v-if="counting"
          type="info"
          variant="tonal"
          density="compact"
          class="mt-3"
          data-testid="count-frozen"
          >{{ $t('inventory.counts.frozen') }}</v-alert
        >
      </v-card>

      <v-tabs v-model="tab" class="mb-2">
        <v-tab v-if="counting && canCount" value="counting" data-testid="tab-counting">{{
          $t('inventory.counts.tabs.counting')
        }}</v-tab>
        <v-tab value="readings">{{
          $t('inventory.counts.tabs.readings', { n: readings.length })
        }}</v-tab>
        <v-tab v-if="!counting" value="divergences" data-testid="tab-divergences">
          {{ $t('inventory.counts.tabs.divergences') }}
          <v-badge
            v-if="count.pending_count"
            color="warning"
            :content="count.pending_count"
            inline
          />
        </v-tab>
      </v-tabs>

      <v-window v-model="tab">
        <v-window-item value="counting">
          <v-row>
            <v-col cols="12" md="6">
              <v-card class="pa-4">
                <v-text-field
                  v-model="location"
                  :label="$t('inventory.counts.readLocation')"
                  prepend-inner-icon="mdi-map-marker-outline"
                  class="mb-3"
                  autofocus
                  hide-details
                  data-testid="count-location"
                  @keydown.enter.prevent="locationRead"
                />
                <v-text-field
                  ref="codeField"
                  v-model="code"
                  :label="$t('inventory.counts.readAsset')"
                  prepend-inner-icon="mdi-barcode-scan"
                  :disabled="!location.trim()"
                  hide-details
                  data-testid="count-code"
                  @keydown.enter.prevent="readAsset"
                />
                <v-alert
                  v-if="feedback"
                  :type="feedback.ok ? 'success' : 'error'"
                  variant="tonal"
                  density="compact"
                  class="mt-3"
                  data-testid="count-feedback"
                  >{{ feedback.text }}</v-alert
                >
              </v-card>
            </v-col>
            <v-col cols="12" md="6">
              <v-card class="pa-4">
                <div class="text-subtitle-2 mb-2">{{ $t('inventory.counts.accessories') }}</div>
                <AssetModelPicker
                  :key="`model-${accessoryKey}`"
                  v-model="accessoryModel"
                  tracking="quantity"
                  :label="$t('inventory.fields.assetModel')"
                />
                <div class="d-flex flex-wrap ga-3">
                  <v-text-field
                    v-model="accessoryQuantity"
                    :label="$t('inventory.counts.quantity')"
                    inputmode="numeric"
                    style="max-width: 120px"
                  />
                  <v-text-field
                    v-model="accessoryContainer"
                    :label="$t('inventory.counts.containerOptional')"
                    style="min-width: 160px"
                  />
                  <v-select
                    v-model="accessoryCondition"
                    :items="
                      (['good', 'scrap'] as const).map((value) => ({
                        value,
                        title: $t(`inventory.accessories.conditions.${value}`),
                      }))
                    "
                    :label="$t('inventory.accessories.condition')"
                    style="max-width: 150px"
                  />
                </div>
                <v-btn
                  variant="tonal"
                  :disabled="!accessoryModel || !location.trim()"
                  @click="readAccessories"
                  >{{ $t('inventory.counts.addQuantity') }}</v-btn
                >
              </v-card>
            </v-col>
          </v-row>
        </v-window-item>

        <v-window-item value="readings">
          <v-card>
            <v-table density="compact" data-testid="count-readings">
              <thead>
                <tr>
                  <th>{{ $t('inventory.fields.location') }}</th>
                  <th>{{ $t('inventory.fields.asset') }}</th>
                  <th class="text-right">{{ $t('inventory.counts.quantity') }}</th>
                  <th>{{ $t('inventory.counts.countedBy') }}</th>
                  <th v-if="counting && canCount" />
                </tr>
              </thead>
              <tbody>
                <tr v-for="r in readings" :key="r.id" data-testid="count-reading">
                  <td>
                    {{ r.location_code }}{{ r.container_code ? ` · ${r.container_code}` : '' }}
                  </td>
                  <td>
                    <div class="font-weight-medium">{{ r.asset_code ?? r.asset_model_label }}</div>
                    <div v-if="r.asset_code" class="text-caption text-medium-emphasis">
                      {{ r.asset_model_label }}
                    </div>
                  </td>
                  <td class="text-right">{{ $n(r.quantity) }}</td>
                  <td>
                    {{ r.counted_by_name }} ·
                    <span class="text-caption">{{ d(new Date(r.counted_at), 'dateTime') }}</span>
                  </td>
                  <td v-if="counting && canCount">
                    <v-btn icon="mdi-close" size="small" variant="text" @click="removeReading(r)" />
                  </td>
                </tr>
                <tr v-if="!readings.length">
                  <td colspan="5" class="text-medium-emphasis">
                    {{ $t('inventory.counts.noReadings') }}
                  </td>
                </tr>
              </tbody>
            </v-table>
          </v-card>
        </v-window-item>

        <v-window-item value="divergences">
          <v-alert
            v-if="count.pending_count"
            type="info"
            variant="tonal"
            density="compact"
            class="mb-3"
            >{{ $t('inventory.counts.rn26') }}</v-alert
          >
          <v-card>
            <v-table density="comfortable" data-testid="count-divergences">
              <thead>
                <tr>
                  <th>{{ $t('inventory.counts.divergence') }}</th>
                  <th>{{ $t('inventory.fields.asset') }}</th>
                  <th>{{ $t('inventory.counts.details') }}</th>
                  <th>{{ $t('inventory.counts.adjustment') }}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in divergences" :key="item.id" data-testid="count-divergence">
                  <td>{{ $t(`inventory.counts.divergences.${item.kind}`) }}</td>
                  <td>
                    <div class="font-weight-medium">{{ divergenceTarget(item) }}</div>
                    <div v-if="item.asset_code" class="text-caption text-medium-emphasis">
                      {{ item.model_label }}
                    </div>
                  </td>
                  <td>{{ divergenceDetail(item) }}</td>
                  <td>
                    <v-chip
                      :color="ADJUSTMENT_COLORS[item.status]"
                      size="small"
                      variant="tonal"
                      label
                      >{{ $t(`inventory.counts.adjustments.${item.status}`) }}</v-chip
                    >
                    <div v-if="item.reason" class="text-caption">
                      {{ item.reason }} — {{ item.decided_by_name }}
                    </div>
                  </td>
                  <td class="text-right text-no-wrap">
                    <template v-if="item.status === 'pending' && isSupervisor">
                      <v-btn
                        size="small"
                        variant="tonal"
                        color="success"
                        class="mr-1"
                        data-testid="approve"
                        @click="openDecide(item, true)"
                        >{{ $t('inventory.counts.approve') }}</v-btn
                      >
                      <v-btn size="small" variant="tonal" @click="openDecide(item, false)">{{
                        $t('inventory.counts.reject')
                      }}</v-btn>
                    </template>
                  </td>
                </tr>
                <tr v-if="!divergences.length">
                  <td colspan="5" class="text-medium-emphasis">
                    {{ $t('inventory.counts.noDivergences') }}
                  </td>
                </tr>
              </tbody>
            </v-table>
          </v-card>
        </v-window-item>
      </v-window>

      <v-dialog v-model="decideOpen" max-width="520">
        <v-card :title="approving ? $t('inventory.counts.approve') : $t('inventory.counts.reject')">
          <v-card-text>
            <p v-if="deciding" class="text-body-2 mb-3">
              {{ $t(`inventory.counts.effects.${approving ? deciding.kind : 'rejected'}`) }}
            </p>
            <v-textarea
              v-model="reason"
              :label="$t('inventory.counts.reason')"
              rows="2"
              auto-grow
              data-testid="decide-reason"
            />
          </v-card-text>
          <v-card-actions>
            <v-spacer />
            <v-btn variant="text" @click="decideOpen = false">{{ $t('common.close') }}</v-btn>
            <v-btn
              :color="approving ? 'success' : 'primary'"
              variant="flat"
              :disabled="!reason.trim()"
              data-testid="decide-confirm"
              @click="decide"
              >{{
                approving ? $t('inventory.counts.approve') : $t('inventory.counts.reject')
              }}</v-btn
            >
          </v-card-actions>
        </v-card>
      </v-dialog>

      <v-dialog v-model="cancelOpen" max-width="480">
        <v-card :title="$t('inventory.counts.cancel')">
          <v-card-text>
            <v-textarea
              v-model="cancelReason"
              :label="$t('inventory.counts.reason')"
              rows="2"
              auto-grow
            />
          </v-card-text>
          <v-card-actions>
            <v-spacer />
            <v-btn variant="text" @click="cancelOpen = false">{{ $t('common.close') }}</v-btn>
            <v-btn color="error" variant="flat" :disabled="!cancelReason.trim()" @click="cancel">{{
              $t('inventory.counts.cancel')
            }}</v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>
    </template>
    <v-progress-linear v-else indeterminate />
  </v-container>
</template>
