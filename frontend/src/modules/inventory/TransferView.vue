<script setup lang="ts">
/**
 * A transfer: its header, what still keeps it from being sent, and tabs —
 * Items (assets or containers read or typed, accessories by quantity; while requested),
 * Picking at the origin (each ID or container against the list — RN-24; color + sound),
 * Receiving at the destination (read the location, then each ID or container: back to the
 * status it left in; damage noted as an occurrence), Occurrences and Documents (fiscal
 * document). Approve (supervisors), Send, Finish the receipt, Cancel before sending.
 */
import { computed, nextTick, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import { useDateFormat } from '@/composables/useDateFormat'
import AssetModelPicker from '@/modules/catalogs/asset-models/AssetModelPicker.vue'
import { useNotificationsStore } from '@/stores/notifications'
import { formatBytes } from '@/utils/bytes'
import StatusChip from './StatusChip.vue'
import TransferFormDialog from './TransferFormDialog.vue'
import TransferStatusChip from './TransferStatusChip.vue'
import {
  BEFORE_SENDING,
  RECEIVING,
  acceptOccurrence,
  addTransferAccessory,
  addTransferItem,
  approveTransfer,
  cancelTransfer,
  deleteTransferFile,
  finishTransfer,
  getTransfer,
  pickTransfer,
  pickTransferAccessory,
  receiveTransfer,
  receiveTransferAccessory,
  removeTransferItem,
  resolveOccurrence,
  sendTransfer,
  transferFileUrl,
  updateTransfer,
  uploadTransferFile,
  type Occurrence,
  type TransferDetail,
  type TransferFileKind,
  type TransferItem,
} from './api'
import { beep } from './beep'
import { useInventoryRoles } from './roles'

const props = defineProps<{ id: number }>()

const { t, locale } = useI18n()
const { d } = useDateFormat()
const notifications = useNotificationsStore()
const { canRequestTransfer, canHandleTransfer, isSupervisor, canReceive } = useInventoryRoles()

const transfer = ref<TransferDetail | null>(null)
const failed = ref(false)
const tab = ref<'items' | 'picking' | 'receiving' | 'occurrences' | 'files'>('items')

async function load() {
  try {
    apply(await getTransfer(props.id))
  } catch {
    failed.value = true
  }
}
onMounted(load)

function apply(data: TransferDetail) {
  transfer.value = data
  fiscalNumber.value = data.fiscal_document_number
}

function errorText(error: unknown) {
  return error instanceof ApiError ? error.message : t('common.saveError')
}

async function run(call: () => Promise<TransferDetail>, message?: string) {
  try {
    apply(await call())
    if (message) notifications.notify(t(message))
    return true
  } catch (error) {
    notifications.notify(errorText(error), 'error')
    return false
  }
}

const status = computed(() => transfer.value?.status)
const requested = computed(() => status.value === 'requested')
const beforeSending = computed(() => !!status.value && BEFORE_SENDING.includes(status.value))
const canPickNow = computed(
  () => canHandleTransfer.value && (status.value === 'approved' || status.value === 'picking'),
)
const canReceiveNow = computed(
  () => canHandleTransfer.value && !!status.value && RECEIVING.includes(status.value),
)
const editable = computed(() => requested.value && canRequestTransfer.value)

// --- Header -----------------------------------------------------------------------------------

const formOpen = ref(false)
const fiscalNumber = ref('')
async function saveFiscalNumber() {
  if (!transfer.value || fiscalNumber.value === transfer.value.fiscal_document_number) return
  await run(() =>
    updateTransfer(transfer.value!.id, { fiscal_document_number: fiscalNumber.value }),
  )
}

const cancelOpen = ref(false)
const cancelReason = ref('')
async function cancel() {
  if (
    await run(
      () => cancelTransfer(transfer.value!.id, cancelReason.value),
      'inventory.transfers.cancelled',
    )
  )
    cancelOpen.value = false
}

const approve = () => run(() => approveTransfer(transfer.value!.id), 'inventory.transfers.approved')
const send = () => run(() => sendTransfer(transfer.value!.id), 'inventory.transfers.sent')
const finish = () => run(() => finishTransfer(transfer.value!.id), 'inventory.transfers.finished')

// --- Items --------------------------------------------------------------------------------------

const addCode = ref('')
const addFeedback = ref<{ ok: boolean; text: string } | null>(null)
async function addItem() {
  const code = addCode.value.trim()
  if (!transfer.value || !code) return
  try {
    apply(await addTransferItem(transfer.value.id, code))
    addFeedback.value = { ok: true, text: t('inventory.transfers.added', { code }) }
    beep(true)
    addCode.value = ''
  } catch (error) {
    addFeedback.value = { ok: false, text: errorText(error) }
    beep(false)
  }
}
const removeItem = (item: TransferItem) =>
  run(() => removeTransferItem(transfer.value!.id, item.id))

const accessoryOpen = ref(false)
const accessoryModel = ref<number | null>(null)
const accessoryQuantity = ref('1')
const accessoryCondition = ref<'good' | 'scrap'>('good')
const accessoryCount = ref(0)
function openAccessory() {
  accessoryModel.value = null
  accessoryQuantity.value = '1'
  accessoryCondition.value = 'good'
  accessoryCount.value += 1
  accessoryOpen.value = true
}
async function addAccessory() {
  if (!accessoryModel.value) return
  const ok = await run(() =>
    addTransferAccessory(transfer.value!.id, {
      accessory_model: accessoryModel.value!,
      quantity: Number(accessoryQuantity.value) || 0,
      condition: accessoryCondition.value,
    }),
  )
  if (ok) accessoryOpen.value = false
}

const itemTitle = (item: TransferItem) =>
  item.asset_detail ? item.asset_detail.horizon_id : (item.accessory_model_label ?? '')
const itemSubtitle = (item: TransferItem) =>
  item.asset_detail
    ? `${item.asset_detail.model} · ${item.asset_detail.location}`
    : t(`inventory.accessories.conditions.${item.condition}`)

// --- Picking and receiving (scan) -----------------------------------------------------------------

const pickCode = ref('')
const pickFeedback = ref<{ ok: boolean; text: string } | null>(null)
const pickField = ref<{ focus: () => void } | null>(null)
async function pick() {
  const code = pickCode.value.trim()
  if (!transfer.value || !code) return
  try {
    apply(await pickTransfer(transfer.value.id, code))
    pickFeedback.value = { ok: true, text: t('inventory.transfers.pickedOne', { code }) }
    beep(true)
  } catch (error) {
    pickFeedback.value = { ok: false, text: errorText(error) }
    beep(false)
  } finally {
    pickCode.value = ''
    await nextTick()
    pickField.value?.focus()
  }
}

const receiveLocation = ref('')
const receiveCode = ref('')
const damaged = ref(false)
const damageNote = ref('')
const receiveFeedback = ref<{ ok: boolean; text: string } | null>(null)
const receiveField = ref<{ focus: () => void } | null>(null)
function locationRead() {
  if (receiveLocation.value.trim()) receiveField.value?.focus()
}
async function receive() {
  const code = receiveCode.value.trim()
  if (!transfer.value || !code) return
  try {
    apply(
      await receiveTransfer(transfer.value.id, {
        location: receiveLocation.value.trim(),
        code,
        damaged: damaged.value,
        note: damageNote.value,
      }),
    )
    receiveFeedback.value = { ok: true, text: t('inventory.transfers.receivedOne', { code }) }
    damaged.value = false
    damageNote.value = ''
    beep(true)
  } catch (error) {
    receiveFeedback.value = { ok: false, text: errorText(error) }
    beep(false)
    // A surplus is recorded even when refused
    try {
      apply(await getTransfer(transfer.value.id))
    } catch {
      // The page keeps what it had
    }
  } finally {
    receiveCode.value = ''
    await nextTick()
    receiveField.value?.focus()
  }
}

const accessoryInputs = ref<Record<number, { code: string; quantity: string }>>({})
function accessoryInput(item: TransferItem, left: number) {
  accessoryInputs.value[item.id] ??= { code: '', quantity: String(left) }
  return accessoryInputs.value[item.id]!
}
async function moveAccessory(item: TransferItem, receiving: boolean) {
  const left = receiving
    ? item.picked_quantity - item.received_quantity
    : item.quantity - item.picked_quantity
  const input = accessoryInput(item, left)
  const call = receiving ? receiveTransferAccessory : pickTransferAccessory
  if (
    await run(() =>
      call(transfer.value!.id, item.id, input.code.trim(), Number(input.quantity) || 0),
    )
  ) {
    delete accessoryInputs.value[item.id]
    beep(true)
  } else beep(false)
}

const assetItems = computed(() => transfer.value?.items.filter((i) => i.asset) ?? [])
const accessoryItems = computed(() => transfer.value?.items.filter((i) => !i.asset) ?? [])
const toPick = computed(() => assetItems.value.filter((i) => !i.picked))
const toReceive = computed(() => assetItems.value.filter((i) => !i.received))

// --- Occurrences --------------------------------------------------------------------------------

const occurrenceOpen = ref(false)
const occurrence = ref<Occurrence | null>(null)
const resolution = ref('')
const accepting = ref(false)
function openOccurrence(item: Occurrence, accept: boolean) {
  occurrence.value = item
  accepting.value = accept
  resolution.value = ''
  occurrenceOpen.value = true
}
async function closeOccurrence() {
  if (!occurrence.value) return
  try {
    await (accepting.value ? acceptOccurrence : resolveOccurrence)(
      occurrence.value.id,
      resolution.value,
    )
    occurrenceOpen.value = false
    await load()
  } catch (error) {
    notifications.notify(errorText(error), 'error')
  }
}
const occurrenceTarget = (o: Occurrence) =>
  o.asset_code ?? `${o.asset_model_label ?? ''} × ${o.quantity}`

// --- Files ----------------------------------------------------------------------------------------

const fileKind = ref<TransferFileKind>('fiscal_document')
const uploading = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
async function upload(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!transfer.value || !file) return
  uploading.value = true
  try {
    await uploadTransferFile(transfer.value.id, fileKind.value, file)
    await load()
  } catch (error) {
    notifications.notify(errorText(error), 'error')
  } finally {
    uploading.value = false
  }
}
async function removeFile(fileId: number) {
  try {
    await deleteTransferFile(transfer.value!.id, fileId)
    await load()
  } catch (error) {
    notifications.notify(errorText(error), 'error')
  }
}
const dateTime = (value: string | null) => (value ? d(new Date(value), 'dateTime') : '—')
</script>

<template>
  <v-container fluid class="module-page">
    <v-alert v-if="failed" type="error" variant="tonal">{{ $t('common.loadError') }}</v-alert>
    <template v-else-if="transfer">
      <div class="d-flex flex-wrap align-center ga-3 mb-1">
        <h1>{{ transfer.code }}</h1>
        <TransferStatusChip :status="transfer.status" :days-late="transfer.days_late" />
        <span class="text-medium-emphasis"
          >{{ transfer.origin_code }} → {{ transfer.destination_code }}</span
        >
        <v-spacer />
        <template v-if="beforeSending && canRequestTransfer">
          <v-btn
            v-if="requested"
            variant="text"
            prepend-icon="mdi-pencil-outline"
            @click="formOpen = true"
            >{{ $t('common.edit') }}</v-btn
          >
          <v-btn
            variant="text"
            color="error"
            prepend-icon="mdi-close-circle-outline"
            data-testid="transfer-cancel"
            @click="((cancelReason = ''), (cancelOpen = true))"
            >{{ $t('inventory.transfers.cancel') }}</v-btn
          >
        </template>
        <v-btn
          v-if="requested && isSupervisor"
          color="primary"
          prepend-icon="mdi-check-decagram-outline"
          :disabled="!transfer.items.length"
          data-testid="transfer-approve"
          @click="approve"
          >{{ $t('inventory.transfers.approve') }}</v-btn
        >
        <v-btn
          v-if="canPickNow"
          color="primary"
          prepend-icon="mdi-truck-fast-outline"
          :disabled="transfer.problems.length > 0"
          data-testid="transfer-send"
          @click="send"
          >{{ $t('inventory.transfers.send') }}</v-btn
        >
        <v-btn
          v-if="canHandleTransfer && transfer.status === 'in_transit'"
          color="primary"
          prepend-icon="mdi-check-all"
          data-testid="transfer-finish"
          @click="finish"
          >{{ $t('inventory.transfers.finish') }}</v-btn
        >
      </div>

      <v-card class="pa-4 mb-4">
        <v-row dense>
          <v-col cols="12" md="4">
            <div class="text-caption text-medium-emphasis">
              {{ $t('inventory.transfers.reason') }}
            </div>
            <div>{{ transfer.reason }}</div>
          </v-col>
          <v-col cols="6" md="2">
            <div class="text-caption text-medium-emphasis">
              {{ $t('inventory.transfers.origin') }}
            </div>
            <div>{{ transfer.origin_code }} · {{ transfer.origin_name }}</div>
          </v-col>
          <v-col cols="6" md="2">
            <div class="text-caption text-medium-emphasis">
              {{ $t('inventory.transfers.destination') }}
            </div>
            <div>{{ transfer.destination_code }} · {{ transfer.destination_name }}</div>
          </v-col>
          <v-col cols="6" md="2">
            <div class="text-caption text-medium-emphasis">
              {{ $t('inventory.transfers.transitDays') }}
            </div>
            <div>{{ transfer.transit_days }}</div>
          </v-col>
          <v-col cols="12" sm="6" md="2">
            <v-text-field
              v-if="beforeSending && (canRequestTransfer || canHandleTransfer)"
              v-model="fiscalNumber"
              :label="$t('inventory.transfers.fiscalNumber')"
              density="compact"
              hide-details
              data-testid="transfer-fiscal-number"
              @blur="saveFiscalNumber"
              @keydown.enter.prevent="saveFiscalNumber"
            />
            <template v-else>
              <div class="text-caption text-medium-emphasis">
                {{ $t('inventory.transfers.fiscalNumber') }}
              </div>
              <div>{{ transfer.fiscal_document_number || '—' }}</div>
            </template>
          </v-col>
        </v-row>
        <div class="text-caption text-medium-emphasis mt-2" data-testid="transfer-timeline">
          {{
            $t('inventory.transfers.requestedBy', {
              name: transfer.requested_by_name,
              date: dateTime(transfer.requested_at),
            })
          }}
          <template v-if="transfer.approved_at">
            ·
            {{
              $t('inventory.transfers.approvedBy', {
                name: transfer.approved_by_name ?? '',
                date: dateTime(transfer.approved_at),
              })
            }}
          </template>
          <template v-if="transfer.sent_at">
            ·
            {{
              $t('inventory.transfers.sentBy', {
                name: transfer.sent_by_name ?? '',
                date: dateTime(transfer.sent_at),
              })
            }}
          </template>
          <template v-if="transfer.received_at">
            ·
            {{
              $t('inventory.transfers.receivedBy', {
                name: transfer.received_by_name ?? '',
                date: dateTime(transfer.received_at),
              })
            }}
          </template>
          <template v-if="transfer.cancelled_at">
            ·
            {{
              $t('inventory.transfers.cancelledBy', {
                name: transfer.cancelled_by_name ?? '',
                date: dateTime(transfer.cancelled_at),
              })
            }}
            — {{ transfer.cancel_reason }}
          </template>
        </div>
        <div v-if="transfer.notes" class="text-body-2 mt-2">{{ transfer.notes }}</div>
      </v-card>

      <v-alert
        v-if="beforeSending && transfer.problems.length"
        type="info"
        variant="tonal"
        density="compact"
        class="mb-4"
        data-testid="transfer-problems"
      >
        <div class="font-weight-medium mb-1">{{ $t('inventory.transfers.toSend') }}</div>
        <ul class="ml-4">
          <li v-for="problem in transfer.problems" :key="problem">{{ problem }}</li>
        </ul>
      </v-alert>

      <v-tabs v-model="tab" class="mb-2">
        <v-tab value="items">{{ $t('inventory.transfers.tabs.items') }}</v-tab>
        <v-tab v-if="canPickNow" value="picking" data-testid="tab-picking">{{
          $t('inventory.transfers.tabs.picking')
        }}</v-tab>
        <v-tab v-if="canReceiveNow" value="receiving" data-testid="tab-receiving">{{
          $t('inventory.transfers.tabs.receiving')
        }}</v-tab>
        <v-tab value="occurrences" data-testid="tab-occurrences">
          {{ $t('inventory.transfers.tabs.occurrences') }}
          <v-badge
            v-if="transfer.occurrences.some((o) => o.status === 'open')"
            color="error"
            dot
            inline
          />
        </v-tab>
        <v-tab value="files">{{ $t('inventory.transfers.tabs.files') }}</v-tab>
      </v-tabs>

      <v-window v-model="tab">
        <!-- Items -->
        <v-window-item value="items">
          <div v-if="editable" class="d-flex flex-wrap align-start ga-3 mb-3">
            <v-text-field
              v-model="addCode"
              :label="$t('inventory.transfers.readItem')"
              prepend-inner-icon="mdi-barcode-scan"
              density="compact"
              style="min-width: 280px; max-width: 380px"
              :messages="addFeedback?.text"
              :color="addFeedback ? (addFeedback.ok ? 'success' : 'error') : undefined"
              autofocus
              data-testid="transfer-add-code"
              @keydown.enter.prevent="addItem"
            />
            <v-btn variant="tonal" prepend-icon="mdi-counter" @click="openAccessory">{{
              $t('inventory.transfers.addAccessory')
            }}</v-btn>
          </div>
          <v-card>
            <v-table density="comfortable" data-testid="transfer-items">
              <thead>
                <tr>
                  <th style="width: 48px">#</th>
                  <th>{{ $t('inventory.fields.asset') }}</th>
                  <th>{{ $t('inventory.fields.status') }}</th>
                  <th class="text-right" style="width: 80px">
                    {{ $t('inventory.transfers.quantity') }}
                  </th>
                  <th style="width: 150px">{{ $t('inventory.transfers.container') }}</th>
                  <th style="width: 130px">{{ $t('inventory.transfers.picking') }}</th>
                  <th style="width: 170px">{{ $t('inventory.transfers.receipt') }}</th>
                  <th v-if="editable" style="width: 48px" />
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(item, index) in transfer.items"
                  :key="item.id"
                  data-testid="transfer-item"
                >
                  <td class="text-medium-emphasis">{{ index + 1 }}</td>
                  <td>
                    <div class="font-weight-medium">{{ itemTitle(item) }}</div>
                    <div class="text-caption text-medium-emphasis">{{ itemSubtitle(item) }}</div>
                  </td>
                  <td>
                    <StatusChip
                      v-if="item.asset_detail"
                      :status="item.asset_detail.status"
                      :held="item.asset_detail.held_for_dispute"
                    />
                  </td>
                  <td class="text-right">{{ $n(item.quantity) }}</td>
                  <td>{{ item.container_code ?? item.asset_detail?.container ?? '—' }}</td>
                  <td>
                    <v-chip
                      v-if="item.picked"
                      color="success"
                      size="small"
                      variant="tonal"
                      label
                      prepend-icon="mdi-check"
                      >{{ $t('inventory.transfers.picked') }}</v-chip
                    >
                    <span v-else-if="item.picked_quantity" class="text-caption"
                      >{{ item.picked_quantity }} / {{ item.quantity }}</span
                    >
                    <span v-else class="text-medium-emphasis">—</span>
                  </td>
                  <td>
                    <template v-if="item.received">
                      <v-chip
                        color="success"
                        size="small"
                        variant="tonal"
                        label
                        prepend-icon="mdi-check"
                        >{{ $t('inventory.transfers.received') }}</v-chip
                      >
                      <div class="text-caption">{{ item.received_location_code }}</div>
                    </template>
                    <span v-else-if="item.received_quantity" class="text-caption"
                      >{{ item.received_quantity }} / {{ item.quantity }}</span
                    >
                    <span v-else class="text-medium-emphasis">—</span>
                  </td>
                  <td v-if="editable">
                    <v-btn
                      icon="mdi-close"
                      size="small"
                      variant="text"
                      :title="$t('inventory.transfers.removeItem')"
                      @click="removeItem(item)"
                    />
                  </td>
                </tr>
                <tr v-if="!transfer.items.length">
                  <td colspan="8" class="text-medium-emphasis">
                    {{ $t('inventory.transfers.noItems') }}
                  </td>
                </tr>
              </tbody>
            </v-table>
          </v-card>
        </v-window-item>

        <!-- Picking at the origin -->
        <v-window-item value="picking">
          <v-row>
            <v-col cols="12" md="6">
              <v-card class="pa-4">
                <v-text-field
                  ref="pickField"
                  v-model="pickCode"
                  :label="$t('inventory.transfers.readItem')"
                  prepend-inner-icon="mdi-barcode-scan"
                  autofocus
                  data-testid="pick-code"
                  @keydown.enter.prevent="pick"
                />
                <v-alert
                  v-if="pickFeedback"
                  :type="pickFeedback.ok ? 'success' : 'error'"
                  variant="tonal"
                  density="compact"
                  data-testid="pick-feedback"
                  >{{ pickFeedback.text }}</v-alert
                >
              </v-card>
            </v-col>
            <v-col cols="12" md="6">
              <v-card class="pa-4">
                <div class="text-subtitle-2 mb-2">
                  {{ $t('inventory.transfers.toPick', toPick.length) }}
                </div>
                <v-list density="compact">
                  <v-list-item
                    v-for="item in toPick"
                    :key="item.id"
                    :title="item.asset_detail?.horizon_id"
                    :subtitle="itemSubtitle(item)"
                    class="px-0"
                  />
                </v-list>
              </v-card>
            </v-col>
          </v-row>
          <v-card v-if="accessoryItems.length" class="pa-4 mt-4">
            <div class="text-subtitle-2 mb-2">{{ $t('inventory.transfers.accessories') }}</div>
            <div
              v-for="item in accessoryItems"
              :key="item.id"
              class="d-flex flex-wrap align-center ga-3 mb-2"
            >
              <div class="flex-grow-1">
                <div class="font-weight-medium">{{ item.accessory_model_label }}</div>
                <div class="text-caption text-medium-emphasis">
                  {{ item.picked_quantity }} / {{ item.quantity }}
                </div>
              </div>
              <template v-if="!item.picked">
                <v-text-field
                  v-model="accessoryInput(item, item.quantity - item.picked_quantity).code"
                  :placeholder="$t('inventory.transfers.readPlace')"
                  density="compact"
                  hide-details
                  style="max-width: 240px"
                />
                <v-text-field
                  v-model="accessoryInput(item, item.quantity - item.picked_quantity).quantity"
                  inputmode="numeric"
                  density="compact"
                  hide-details
                  style="max-width: 90px"
                />
                <v-btn variant="tonal" @click="moveAccessory(item, false)">{{
                  $t('inventory.transfers.pick')
                }}</v-btn>
              </template>
              <v-icon v-else icon="mdi-check" color="success" />
            </div>
          </v-card>
        </v-window-item>

        <!-- Receiving at the destination -->
        <v-window-item value="receiving">
          <v-row>
            <v-col cols="12" md="6">
              <v-card class="pa-4">
                <v-text-field
                  v-model="receiveLocation"
                  :label="$t('inventory.transfers.receiveLocation')"
                  :hint="$t('inventory.transfers.receiveLocationHint')"
                  persistent-hint
                  prepend-inner-icon="mdi-map-marker-outline"
                  class="mb-3"
                  data-testid="receive-location"
                  @keydown.enter.prevent="locationRead"
                />
                <v-text-field
                  ref="receiveField"
                  v-model="receiveCode"
                  :label="$t('inventory.transfers.readItem')"
                  prepend-inner-icon="mdi-barcode-scan"
                  :disabled="!receiveLocation.trim()"
                  data-testid="receive-code"
                  @keydown.enter.prevent="receive"
                />
                <v-checkbox
                  v-model="damaged"
                  :label="$t('inventory.transfers.damaged')"
                  density="compact"
                  hide-details
                  data-testid="receive-damaged"
                />
                <v-text-field
                  v-if="damaged"
                  v-model="damageNote"
                  :label="$t('inventory.transfers.damageNote')"
                  density="compact"
                  class="mt-2"
                />
                <v-alert
                  v-if="receiveFeedback"
                  :type="receiveFeedback.ok ? 'success' : 'error'"
                  variant="tonal"
                  density="compact"
                  class="mt-2"
                  data-testid="receive-feedback"
                  >{{ receiveFeedback.text }}</v-alert
                >
              </v-card>
            </v-col>
            <v-col cols="12" md="6">
              <v-card class="pa-4">
                <div class="text-subtitle-2 mb-2">
                  {{ $t('inventory.transfers.toReceive', toReceive.length) }}
                </div>
                <v-list density="compact">
                  <v-list-item
                    v-for="item in toReceive"
                    :key="item.id"
                    :title="item.asset_detail?.horizon_id"
                    :subtitle="`${item.asset_detail?.model}${item.container_code ? ` · ${item.container_code}` : ''}`"
                    class="px-0"
                  />
                </v-list>
              </v-card>
            </v-col>
          </v-row>
          <v-card v-if="accessoryItems.length" class="pa-4 mt-4">
            <div class="text-subtitle-2 mb-2">{{ $t('inventory.transfers.accessories') }}</div>
            <div
              v-for="item in accessoryItems"
              :key="item.id"
              class="d-flex flex-wrap align-center ga-3 mb-2"
            >
              <div class="flex-grow-1">
                <div class="font-weight-medium">{{ item.accessory_model_label }}</div>
                <div class="text-caption text-medium-emphasis">
                  {{ item.received_quantity }} / {{ item.picked_quantity }}
                </div>
              </div>
              <template v-if="item.received_quantity < item.picked_quantity">
                <v-text-field
                  v-model="accessoryInput(item, item.picked_quantity - item.received_quantity).code"
                  :placeholder="$t('inventory.transfers.readPlace')"
                  density="compact"
                  hide-details
                  style="max-width: 240px"
                />
                <v-text-field
                  v-model="
                    accessoryInput(item, item.picked_quantity - item.received_quantity).quantity
                  "
                  inputmode="numeric"
                  density="compact"
                  hide-details
                  style="max-width: 90px"
                />
                <v-btn variant="tonal" @click="moveAccessory(item, true)">{{
                  $t('inventory.transfers.receive')
                }}</v-btn>
              </template>
              <v-icon v-else icon="mdi-check" color="success" />
            </div>
          </v-card>
        </v-window-item>

        <!-- Occurrences -->
        <v-window-item value="occurrences">
          <v-card>
            <v-table density="comfortable" data-testid="transfer-occurrences">
              <thead>
                <tr>
                  <th>{{ $t('inventory.occurrences.kind') }}</th>
                  <th>{{ $t('inventory.fields.asset') }}</th>
                  <th>{{ $t('inventory.occurrences.description') }}</th>
                  <th>{{ $t('inventory.fields.status') }}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                <tr v-for="o in transfer.occurrences" :key="o.id" data-testid="transfer-occurrence">
                  <td>{{ $t(`inventory.occurrences.kinds.${o.kind}`) }}</td>
                  <td>{{ occurrenceTarget(o) }}</td>
                  <td>
                    {{ o.description || '—' }}
                    <div v-if="o.resolution" class="text-caption text-medium-emphasis">
                      {{ o.resolution }}
                    </div>
                  </td>
                  <td>{{ $t(`inventory.occurrences.statuses.${o.status}`) }}</td>
                  <td class="text-right text-no-wrap">
                    <template v-if="o.status === 'open'">
                      <v-btn
                        v-if="canReceive"
                        size="small"
                        variant="tonal"
                        class="mr-1"
                        @click="openOccurrence(o, false)"
                        >{{ $t('inventory.occurrences.resolve') }}</v-btn
                      >
                      <v-btn
                        v-if="isSupervisor"
                        size="small"
                        variant="tonal"
                        @click="openOccurrence(o, true)"
                        >{{ $t('inventory.occurrences.accept') }}</v-btn
                      >
                    </template>
                  </td>
                </tr>
                <tr v-if="!transfer.occurrences.length">
                  <td colspan="5" class="text-medium-emphasis">
                    {{ $t('inventory.transfers.noOccurrences') }}
                  </td>
                </tr>
              </tbody>
            </v-table>
          </v-card>
        </v-window-item>

        <!-- Documents -->
        <v-window-item value="files">
          <v-card class="pa-4">
            <div
              v-if="transfer.status !== 'cancelled' && (canRequestTransfer || canHandleTransfer)"
              class="d-flex flex-wrap align-center ga-3 mb-3"
            >
              <v-select
                v-model="fileKind"
                :items="
                  (['fiscal_document', 'other'] as const).map((value) => ({
                    value,
                    title: $t(`inventory.transfers.fileKinds.${value}`),
                  }))
                "
                density="compact"
                hide-details
                style="max-width: 260px"
              />
              <v-btn
                variant="tonal"
                prepend-icon="mdi-paperclip"
                :loading="uploading"
                @click="fileInput?.click()"
                >{{ $t('inventory.transfers.attach') }}</v-btn
              >
              <input ref="fileInput" type="file" hidden @change="upload" />
            </div>
            <v-list density="compact" data-testid="transfer-files">
              <v-list-item
                v-for="file in transfer.files"
                :key="file.id"
                :href="transferFileUrl(transfer.id, file.id)"
                target="_blank"
                prepend-icon="mdi-file-outline"
                class="px-0"
              >
                <v-list-item-title>{{ file.name }}</v-list-item-title>
                <v-list-item-subtitle>
                  {{ $t(`inventory.transfers.fileKinds.${file.kind}`) }} ·
                  {{ formatBytes(file.size, locale) }} · {{ file.uploaded_by_name }} ·
                  {{ dateTime(file.uploaded_at) }}
                </v-list-item-subtitle>
                <template v-if="beforeSending && (canRequestTransfer || canHandleTransfer)" #append>
                  <v-btn
                    icon="mdi-delete-outline"
                    size="small"
                    variant="text"
                    color="error"
                    @click.prevent.stop="removeFile(file.id)"
                  />
                </template>
              </v-list-item>
              <v-list-item v-if="!transfer.files.length" class="px-0 text-medium-emphasis">
                {{ $t('inventory.transfers.noFiles') }}
              </v-list-item>
            </v-list>
          </v-card>
        </v-window-item>
      </v-window>

      <TransferFormDialog v-model="formOpen" :transfer="transfer" @saved="apply" />

      <v-dialog v-model="cancelOpen" max-width="480">
        <v-card :title="$t('inventory.transfers.cancel')">
          <v-card-text>
            <v-textarea
              v-model="cancelReason"
              :label="$t('inventory.transfers.cancelReason')"
              rows="2"
              auto-grow
              data-testid="cancel-reason"
            />
          </v-card-text>
          <v-card-actions>
            <v-spacer />
            <v-btn variant="text" @click="cancelOpen = false">{{ $t('common.close') }}</v-btn>
            <v-btn
              color="error"
              variant="flat"
              :disabled="!cancelReason.trim()"
              data-testid="cancel-confirm"
              @click="cancel"
              >{{ $t('inventory.transfers.cancel') }}</v-btn
            >
          </v-card-actions>
        </v-card>
      </v-dialog>

      <v-dialog v-model="accessoryOpen" max-width="520">
        <v-card :title="$t('inventory.transfers.addAccessory')">
          <v-card-text>
            <AssetModelPicker
              :key="`accessory-${accessoryCount}`"
              v-model="accessoryModel"
              tracking="quantity"
              :label="$t('inventory.fields.assetModel')"
            />
            <div class="d-flex ga-3">
              <v-text-field
                v-model="accessoryQuantity"
                :label="$t('inventory.transfers.quantity')"
                inputmode="numeric"
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
              />
            </div>
          </v-card-text>
          <v-card-actions>
            <v-spacer />
            <v-btn variant="text" @click="accessoryOpen = false">{{ $t('common.cancel') }}</v-btn>
            <v-btn
              color="primary"
              variant="flat"
              :disabled="!accessoryModel"
              @click="addAccessory"
              >{{ $t('inventory.transfers.add') }}</v-btn
            >
          </v-card-actions>
        </v-card>
      </v-dialog>

      <v-dialog v-model="occurrenceOpen" max-width="480">
        <v-card
          :title="
            accepting ? $t('inventory.occurrences.accept') : $t('inventory.occurrences.resolve')
          "
        >
          <v-card-text>
            <v-textarea
              v-model="resolution"
              :label="$t('inventory.transfers.resolution')"
              rows="2"
              auto-grow
            />
          </v-card-text>
          <v-card-actions>
            <v-spacer />
            <v-btn variant="text" @click="occurrenceOpen = false">{{ $t('common.close') }}</v-btn>
            <v-btn
              color="primary"
              variant="flat"
              :disabled="!resolution.trim()"
              @click="closeOccurrence"
              >{{ $t('common.save') }}</v-btn
            >
          </v-card-actions>
        </v-card>
      </v-dialog>
    </template>
    <v-progress-linear v-else indeterminate />
  </v-container>
</template>
