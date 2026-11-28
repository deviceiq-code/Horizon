<script setup lang="ts">
/**
 * A disposal: its header, what still keeps it from shipping, and three tabs —
 * Items (assets read or typed — reserved —, accessories by quantity, value per unit),
 * Picking (read the shipping area, then each ID against the list — color + sound; accessories
 * read from their container or location) and Documents (shipping document; a discard's
 * destination certificate). Ship writes the assets off; Cancel gives everything back.
 */
import { computed, nextTick, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import MoneyField from '@/components/MoneyField.vue'
import { useDateFormat } from '@/composables/useDateFormat'
import AssetModelPicker from '@/modules/catalogs/asset-models/AssetModelPicker.vue'
import { useNotificationsStore } from '@/stores/notifications'
import { formatBytes } from '@/utils/bytes'
import { formatMoney, parseMoney, toInputMoney } from '@/utils/money'
import DisposalFormDialog from './DisposalFormDialog.vue'
import DisposalStatusChip from './DisposalStatusChip.vue'
import StatusChip from './StatusChip.vue'
import {
  addDisposalAccessory,
  addDisposalAssets,
  cancelDisposal,
  deleteDisposalFile,
  disposalFileUrl,
  getDisposal,
  pickDisposalAccessory,
  pickDisposalAsset,
  removeDisposalItem,
  setDisposalItemValue,
  shipDisposal,
  updateDisposal,
  uploadDisposalFile,
  type DisposalDetail,
  type DisposalFileKind,
  type DisposalItem,
} from './api'
import { beep } from './beep'
import { useInventoryRoles } from './roles'

const props = defineProps<{ id: number }>()

const { t, locale } = useI18n()
const { d } = useDateFormat()
const notifications = useNotificationsStore()
const { canDispose, canPick } = useInventoryRoles()

const disposal = ref<DisposalDetail | null>(null)
const failed = ref(false)
const tab = ref<'items' | 'picking' | 'files'>('items')

async function load() {
  try {
    disposal.value = await getDisposal(props.id)
    values.value = Object.fromEntries(
      disposal.value.items.map((i) => [
        i.id,
        i.unit_value ? toInputMoney(i.unit_value, locale.value) : '',
      ]),
    )
    documentNumber.value = disposal.value.document_number
  } catch {
    failed.value = true
  }
}
onMounted(load)

const isOpen = computed(
  () => !!disposal.value && ['reserved', 'picking'].includes(disposal.value.status),
)
const editable = computed(() => isOpen.value && canDispose.value)
const destination = computed(() => {
  const v = disposal.value
  if (!v) return ''
  return v.customer_name ?? v.buyer_name ?? v.discard_provider_name ?? '—'
})
const destinationLabel = computed(() => {
  switch (disposal.value?.kind) {
    case 'third_party_sale':
      return t('inventory.disposals.buyer')
    case 'discard':
      return t('inventory.disposals.discardProvider')
    case 'parts':
      return ''
    default:
      return t('inventory.appointments.customer')
  }
})
const money = (value: string | null) => (value ? formatMoney(value, 'BRL', locale.value) : '—')

function errorText(error: unknown) {
  return error instanceof ApiError ? error.message : t('common.saveError')
}

function apply(data: DisposalDetail) {
  disposal.value = data
  values.value = Object.fromEntries(
    data.items.map((i) => [i.id, i.unit_value ? toInputMoney(i.unit_value, locale.value) : '']),
  )
}

// --- Header -----------------------------------------------------------------------------------

const formOpen = ref(false)
const documentNumber = ref('')

async function saveDocumentNumber() {
  if (!disposal.value || documentNumber.value === disposal.value.document_number) return
  try {
    apply(await updateDisposal(disposal.value.id, { document_number: documentNumber.value }))
  } catch (error) {
    notifications.notify(errorText(error), 'error')
  }
}

const cancelOpen = ref(false)
const cancelReason = ref('')
async function cancel() {
  if (!disposal.value) return
  try {
    apply(await cancelDisposal(disposal.value.id, cancelReason.value))
    cancelOpen.value = false
    notifications.notify(t('inventory.disposals.cancelled'))
  } catch (error) {
    notifications.notify(errorText(error), 'error')
  }
}

const shipping = ref(false)
async function ship() {
  if (!disposal.value) return
  shipping.value = true
  try {
    apply(await shipDisposal(disposal.value.id))
    notifications.notify(t('inventory.disposals.shipped'))
  } catch (error) {
    notifications.notify(errorText(error), 'error')
  } finally {
    shipping.value = false
  }
}

// --- Items --------------------------------------------------------------------------------------

const assetCode = ref('')
const addValue = ref('')
const adding = ref(false)
const addFeedback = ref<{ ok: boolean; text: string } | null>(null)

async function addAsset() {
  const code = assetCode.value.trim()
  if (!disposal.value || !code || adding.value) return
  adding.value = true
  try {
    apply(
      await addDisposalAssets(disposal.value.id, [code], parseMoney(addValue.value, locale.value)),
    )
    addFeedback.value = { ok: true, text: t('inventory.disposals.added', { code }) }
    beep(true)
    assetCode.value = ''
  } catch (error) {
    addFeedback.value = { ok: false, text: errorText(error) }
    beep(false)
  } finally {
    adding.value = false
  }
}

const values = ref<Record<number, string>>({})
async function saveValue(item: DisposalItem) {
  if (!disposal.value) return
  const typed = values.value[item.id] ?? ''
  const value = typed.trim() ? parseMoney(typed, locale.value) : null
  if (typed.trim() && value === null) return
  if (value === item.unit_value || (value !== null && item.unit_value === value)) return
  try {
    apply(await setDisposalItemValue(disposal.value.id, item.id, value))
  } catch (error) {
    notifications.notify(errorText(error), 'error')
  }
}

async function removeItem(item: DisposalItem) {
  if (!disposal.value) return
  try {
    apply(await removeDisposalItem(disposal.value.id, item.id))
  } catch (error) {
    notifications.notify(errorText(error), 'error')
  }
}

const accessoryOpen = ref(false)
const accessoryModel = ref<number | null>(null)
const accessoryQuantity = ref('1')
const accessoryCondition = ref<'good' | 'scrap'>('good')
const accessoryValue = ref('')
const accessoryCount = ref(0)
function openAccessory() {
  accessoryModel.value = null
  accessoryQuantity.value = '1'
  accessoryCondition.value = 'good'
  accessoryValue.value = ''
  accessoryCount.value += 1
  accessoryOpen.value = true
}
async function addAccessory() {
  if (!disposal.value || !accessoryModel.value) return
  try {
    apply(
      await addDisposalAccessory(disposal.value.id, {
        accessory_model: accessoryModel.value,
        quantity: Number(accessoryQuantity.value) || 0,
        condition: accessoryCondition.value,
        unit_value: parseMoney(accessoryValue.value, locale.value),
      }),
    )
    accessoryOpen.value = false
  } catch (error) {
    notifications.notify(errorText(error), 'error')
  }
}

const itemTitle = (item: DisposalItem) =>
  item.asset_detail ? item.asset_detail.horizon_id : (item.accessory_model_label ?? '')
const itemSubtitle = (item: DisposalItem) =>
  item.asset_detail
    ? `${item.asset_detail.model} · ${item.asset_detail.asset_class}`
    : t(`inventory.accessories.conditions.${item.condition}`)

// --- Picking -------------------------------------------------------------------------------------

const shippingCode = ref('')
const pickCode = ref('')
const picking = ref(false)
const pickFeedback = ref<{ ok: boolean; text: string } | null>(null)
const pickField = ref<{ focus: () => void } | null>(null)

const pendingAssets = computed(
  () => disposal.value?.items.filter((i) => i.asset && !i.picked) ?? [],
)
const accessoryLines = computed(() => disposal.value?.items.filter((i) => !i.asset) ?? [])

async function pickAsset() {
  const code = pickCode.value.trim()
  if (!disposal.value || !code || picking.value) return
  picking.value = true
  try {
    apply(await pickDisposalAsset(disposal.value.id, code, shippingCode.value.trim()))
    pickFeedback.value = { ok: true, text: t('inventory.disposals.pickedOne', { code }) }
    beep(true)
  } catch (error) {
    pickFeedback.value = { ok: false, text: errorText(error) }
    beep(false)
  } finally {
    pickCode.value = ''
    picking.value = false
    await nextTick()
    pickField.value?.focus()
  }
}

function shippingRead() {
  if (shippingCode.value.trim()) pickField.value?.focus()
}

const accessoryPick = ref<Record<number, { code: string; quantity: string }>>({})
function pickInput(item: DisposalItem) {
  accessoryPick.value[item.id] ??= {
    code: '',
    quantity: String(item.quantity - item.picked_quantity),
  }
  return accessoryPick.value[item.id]!
}
async function pickAccessory(item: DisposalItem) {
  if (!disposal.value) return
  const input = pickInput(item)
  try {
    apply(
      await pickDisposalAccessory(
        disposal.value.id,
        item.id,
        input.code.trim(),
        Number(input.quantity) || 0,
      ),
    )
    delete accessoryPick.value[item.id]
    beep(true)
  } catch (error) {
    notifications.notify(errorText(error), 'error')
    beep(false)
  }
}

// --- Files ------------------------------------------------------------------------------------

const fileKind = ref<DisposalFileKind>('document')
const fileKinds = computed(() =>
  (['document', 'certificate', 'other'] as const)
    .filter((k) => k !== 'certificate' || disposal.value?.kind === 'discard')
    .map((value) => ({ value, title: t(`inventory.disposals.fileKinds.${value}`) })),
)
const uploading = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

async function upload(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!disposal.value || !file) return
  uploading.value = true
  try {
    await uploadDisposalFile(disposal.value.id, fileKind.value, file)
    await load()
  } catch (error) {
    notifications.notify(errorText(error), 'error')
  } finally {
    uploading.value = false
  }
}

async function removeFile(fileId: number) {
  if (!disposal.value) return
  try {
    await deleteDisposalFile(disposal.value.id, fileId)
    await load()
  } catch (error) {
    notifications.notify(errorText(error), 'error')
  }
}
</script>

<template>
  <v-container fluid class="module-page">
    <v-alert v-if="failed" type="error" variant="tonal">{{ $t('common.loadError') }}</v-alert>
    <template v-else-if="disposal">
      <div class="d-flex flex-wrap align-center ga-3 mb-1">
        <h1>{{ disposal.code }}</h1>
        <DisposalStatusChip :status="disposal.status" />
        <span class="text-medium-emphasis">{{
          $t(`inventory.disposals.kinds.${disposal.kind}`)
        }}</span>
        <v-spacer />
        <template v-if="editable">
          <v-btn variant="text" prepend-icon="mdi-pencil-outline" @click="formOpen = true">{{
            $t('common.edit')
          }}</v-btn>
          <v-btn
            variant="text"
            color="error"
            prepend-icon="mdi-close-circle-outline"
            data-testid="disposal-cancel"
            @click="((cancelReason = ''), (cancelOpen = true))"
            >{{ $t('inventory.disposals.cancel') }}</v-btn
          >
        </template>
        <v-btn
          v-if="isOpen && canPick"
          color="primary"
          prepend-icon="mdi-truck-check-outline"
          :disabled="disposal.problems.length > 0"
          :loading="shipping"
          data-testid="disposal-ship"
          @click="ship"
          >{{ $t('inventory.disposals.ship') }}</v-btn
        >
      </div>

      <v-card class="pa-4 mb-4">
        <v-row dense>
          <v-col v-if="destinationLabel" cols="12" sm="6" md="3">
            <div class="text-caption text-medium-emphasis">{{ destinationLabel }}</div>
            <div class="font-weight-medium">{{ destination }}</div>
            <div v-if="disposal.contract" class="text-caption">
              {{ $t('inventory.disposals.contract') }}: {{ disposal.contract }}
            </div>
          </v-col>
          <v-col cols="6" sm="3" md="2">
            <div class="text-caption text-medium-emphasis">
              {{ $t('inventory.fields.warehouse') }}
            </div>
            <div :title="disposal.warehouse_name">{{ disposal.warehouse_code }}</div>
          </v-col>
          <v-col cols="6" sm="3" md="2">
            <div class="text-caption text-medium-emphasis">
              {{ $t('inventory.disposals.appointment') }}
            </div>
            <div>{{ disposal.appointment_code ?? '—' }}</div>
          </v-col>
          <v-col cols="12" sm="6" md="2">
            <v-text-field
              v-if="editable"
              v-model="documentNumber"
              :label="$t('inventory.disposals.documentNumber')"
              density="compact"
              hide-details
              data-testid="disposal-document-number"
              @blur="saveDocumentNumber"
              @keydown.enter.prevent="saveDocumentNumber"
            />
            <template v-else>
              <div class="text-caption text-medium-emphasis">
                {{ $t('inventory.disposals.documentNumber') }}
              </div>
              <div>{{ disposal.document_number || '—' }}</div>
            </template>
          </v-col>
          <v-col cols="12" sm="6" md="3" class="text-md-right">
            <div class="text-caption text-medium-emphasis">
              {{ $t('inventory.disposals.totalValue') }}
            </div>
            <div class="text-h6" data-testid="disposal-total">
              {{ money(disposal.totals.total_value) }}
            </div>
            <div class="text-caption text-medium-emphasis">
              {{
                $t('inventory.disposals.counts', {
                  assets: disposal.totals.assets,
                  accessories: disposal.totals.accessories,
                })
              }}
            </div>
          </v-col>
        </v-row>
        <div class="text-caption text-medium-emphasis mt-2">
          {{
            $t('inventory.disposals.createdBy', {
              name: disposal.created_by_name,
              date: d(new Date(disposal.created_at), 'dateTime'),
            })
          }}
          <template v-if="disposal.shipped_at">
            ·
            {{
              $t('inventory.disposals.shippedBy', {
                name: disposal.shipped_by_name ?? '',
                date: d(new Date(disposal.shipped_at), 'dateTime'),
              })
            }}
          </template>
          <template v-if="disposal.cancelled_at">
            ·
            {{
              $t('inventory.disposals.cancelledBy', {
                name: disposal.cancelled_by_name ?? '',
                date: d(new Date(disposal.cancelled_at), 'dateTime'),
              })
            }}
            — {{ disposal.cancel_reason }}
          </template>
        </div>
        <div v-if="disposal.notes" class="text-body-2 mt-2">{{ disposal.notes }}</div>
      </v-card>

      <v-alert
        v-if="isOpen && disposal.problems.length"
        type="info"
        variant="tonal"
        density="compact"
        class="mb-4"
        data-testid="disposal-problems"
      >
        <div class="font-weight-medium mb-1">{{ $t('inventory.disposals.toShip') }}</div>
        <ul class="ml-4">
          <li v-for="problem in disposal.problems" :key="problem">{{ problem }}</li>
        </ul>
      </v-alert>

      <v-tabs v-model="tab" class="mb-2">
        <v-tab value="items">{{ $t('inventory.disposals.tabs.items') }}</v-tab>
        <v-tab v-if="isOpen && canPick" value="picking" data-testid="tab-picking">{{
          $t('inventory.disposals.tabs.picking')
        }}</v-tab>
        <v-tab value="files">{{ $t('inventory.disposals.tabs.files') }}</v-tab>
      </v-tabs>

      <v-window v-model="tab">
        <!-- Items -->
        <v-window-item value="items">
          <div v-if="editable" class="d-flex flex-wrap align-start ga-3 mb-3">
            <v-text-field
              v-model="assetCode"
              :label="$t('inventory.disposals.readAsset')"
              prepend-inner-icon="mdi-barcode-scan"
              :loading="adding"
              density="compact"
              style="min-width: 260px; max-width: 360px"
              :messages="addFeedback?.text"
              :color="addFeedback ? (addFeedback.ok ? 'success' : 'error') : undefined"
              :class="addFeedback && !addFeedback.ok ? 'scan-error' : ''"
              autofocus
              data-testid="disposal-add-code"
              @keydown.enter.prevent="addAsset"
            />
            <MoneyField
              v-model="addValue"
              :label="$t('inventory.disposals.unitValueOptional')"
              density="compact"
              hide-details
              style="max-width: 200px"
            />
            <v-btn variant="tonal" prepend-icon="mdi-counter" @click="openAccessory">{{
              $t('inventory.disposals.addAccessory')
            }}</v-btn>
          </div>

          <v-card>
            <v-table density="comfortable" data-testid="disposal-items">
              <thead>
                <tr>
                  <th style="width: 48px">#</th>
                  <th>{{ $t('inventory.fields.asset') }}</th>
                  <th>{{ $t('inventory.fields.status') }}</th>
                  <th class="text-right" style="width: 90px">
                    {{ $t('inventory.disposals.quantity') }}
                  </th>
                  <th class="text-right" style="width: 200px">
                    {{ $t('inventory.disposals.unitValue') }}
                  </th>
                  <th class="text-right" style="width: 150px">
                    {{ $t('inventory.disposals.lineTotal') }}
                  </th>
                  <th style="width: 140px">{{ $t('inventory.disposals.picking') }}</th>
                  <th v-if="editable" style="width: 48px" />
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(item, index) in disposal.items"
                  :key="item.id"
                  data-testid="disposal-item"
                >
                  <td class="text-medium-emphasis">{{ index + 1 }}</td>
                  <td>
                    <div class="font-weight-medium">{{ itemTitle(item) }}</div>
                    <div class="text-caption text-medium-emphasis">
                      {{ itemSubtitle(item) }}
                      <v-chip
                        v-if="item.asset_detail?.grade"
                        size="x-small"
                        label
                        variant="outlined"
                        class="ml-1"
                        >{{ item.asset_detail.grade }}</v-chip
                      >
                    </div>
                  </td>
                  <td>
                    <StatusChip
                      v-if="item.asset_detail"
                      :status="item.asset_detail.status"
                      :held="item.asset_detail.held_for_dispute"
                    />
                  </td>
                  <td class="text-right">{{ $n(item.quantity) }}</td>
                  <td class="text-right">
                    <MoneyField
                      v-if="editable"
                      v-model="values[item.id]!"
                      density="compact"
                      hide-details
                      :data-testid="`item-value-${item.id}`"
                      @blur="saveValue(item)"
                      @keydown.enter.prevent="saveValue(item)"
                    />
                    <span v-else>{{ money(item.unit_value) }}</span>
                  </td>
                  <td class="text-right">{{ money(item.line_total) }}</td>
                  <td>
                    <v-chip
                      v-if="item.picked"
                      color="success"
                      size="small"
                      variant="tonal"
                      label
                      prepend-icon="mdi-check"
                      >{{ $t('inventory.disposals.picked') }}</v-chip
                    >
                    <span v-else-if="item.picked_quantity" class="text-caption">
                      {{ item.picked_quantity }} / {{ item.quantity }}
                    </span>
                    <span v-else class="text-medium-emphasis">—</span>
                  </td>
                  <td v-if="editable">
                    <v-btn
                      v-if="!item.picked_quantity"
                      icon="mdi-close"
                      size="small"
                      variant="text"
                      :title="$t('inventory.disposals.removeItem')"
                      data-testid="item-remove"
                      @click="removeItem(item)"
                    />
                  </td>
                </tr>
                <tr v-if="!disposal.items.length">
                  <td colspan="8" class="text-medium-emphasis">
                    {{ $t('inventory.disposals.noItems') }}
                  </td>
                </tr>
              </tbody>
            </v-table>
          </v-card>
        </v-window-item>

        <!-- Picking -->
        <v-window-item value="picking">
          <v-row>
            <v-col cols="12" md="6">
              <v-card class="pa-4">
                <v-text-field
                  v-model="shippingCode"
                  :label="$t('inventory.disposals.shippingArea')"
                  :hint="$t('inventory.disposals.shippingAreaHint')"
                  persistent-hint
                  prepend-inner-icon="mdi-map-marker-outline"
                  class="mb-3"
                  data-testid="pick-shipping"
                  @keydown.enter.prevent="shippingRead"
                />
                <v-text-field
                  ref="pickField"
                  v-model="pickCode"
                  :label="$t('inventory.disposals.readAsset')"
                  prepend-inner-icon="mdi-barcode-scan"
                  :loading="picking"
                  :disabled="!shippingCode.trim()"
                  data-testid="pick-code"
                  @keydown.enter.prevent="pickAsset"
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
                  {{ $t('inventory.disposals.toPick', pendingAssets.length) }}
                </div>
                <v-list density="compact" data-testid="pick-pending">
                  <v-list-item
                    v-for="item in pendingAssets"
                    :key="item.id"
                    :title="item.asset_detail?.horizon_id"
                    :subtitle="`${item.asset_detail?.model} · ${item.asset_detail?.location}`"
                    class="px-0"
                  />
                </v-list>
              </v-card>
            </v-col>
          </v-row>
          <v-card v-if="accessoryLines.length" class="pa-4 mt-4">
            <div class="text-subtitle-2 mb-2">{{ $t('inventory.disposals.accessories') }}</div>
            <div
              v-for="item in accessoryLines"
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
                  v-model="pickInput(item).code"
                  :placeholder="$t('inventory.disposals.readPlace')"
                  density="compact"
                  hide-details
                  style="max-width: 240px"
                />
                <v-text-field
                  v-model="pickInput(item).quantity"
                  inputmode="numeric"
                  density="compact"
                  hide-details
                  style="max-width: 90px"
                />
                <v-btn variant="tonal" @click="pickAccessory(item)">{{
                  $t('inventory.disposals.pick')
                }}</v-btn>
              </template>
              <v-icon v-else icon="mdi-check" color="success" />
            </div>
          </v-card>
        </v-window-item>

        <!-- Documents -->
        <v-window-item value="files">
          <v-card class="pa-4">
            <div
              v-if="disposal.status !== 'cancelled' && (canDispose || canPick)"
              class="d-flex flex-wrap align-center ga-3 mb-3"
            >
              <v-select
                v-model="fileKind"
                :items="fileKinds"
                density="compact"
                hide-details
                style="max-width: 260px"
              />
              <v-btn
                variant="tonal"
                prepend-icon="mdi-paperclip"
                :loading="uploading"
                @click="fileInput?.click()"
                >{{ $t('inventory.disposals.attach') }}</v-btn
              >
              <input ref="fileInput" type="file" hidden data-testid="file-input" @change="upload" />
            </div>
            <v-list density="compact" data-testid="disposal-files">
              <v-list-item
                v-for="file in disposal.files"
                :key="file.id"
                :href="disposalFileUrl(disposal.id, file.id)"
                target="_blank"
                prepend-icon="mdi-file-outline"
                class="px-0"
              >
                <v-list-item-title>{{ file.name }}</v-list-item-title>
                <v-list-item-subtitle>
                  {{ $t(`inventory.disposals.fileKinds.${file.kind}`) }} ·
                  {{ formatBytes(file.size, locale) }} · {{ file.uploaded_by_name }} ·
                  {{ d(new Date(file.uploaded_at), 'dateTime') }}
                </v-list-item-subtitle>
                <template v-if="isOpen && (canDispose || canPick)" #append>
                  <v-btn
                    icon="mdi-delete-outline"
                    size="small"
                    variant="text"
                    color="error"
                    @click.prevent.stop="removeFile(file.id)"
                  />
                </template>
              </v-list-item>
              <v-list-item v-if="!disposal.files.length" class="px-0 text-medium-emphasis">
                {{ $t('inventory.disposals.noFiles') }}
              </v-list-item>
            </v-list>
          </v-card>
        </v-window-item>
      </v-window>

      <DisposalFormDialog v-model="formOpen" :disposal="disposal" @saved="apply" />

      <v-dialog v-model="cancelOpen" max-width="480">
        <v-card :title="$t('inventory.disposals.cancel')">
          <v-card-text>
            <p class="text-body-2 text-medium-emphasis mb-3">
              {{ $t('inventory.disposals.cancelHint') }}
            </p>
            <v-textarea
              v-model="cancelReason"
              :label="$t('inventory.disposals.cancelReason')"
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
              >{{ $t('inventory.disposals.cancel') }}</v-btn
            >
          </v-card-actions>
        </v-card>
      </v-dialog>

      <v-dialog v-model="accessoryOpen" max-width="560">
        <v-card :title="$t('inventory.disposals.addAccessory')">
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
                :label="$t('inventory.disposals.quantity')"
                inputmode="numeric"
              />
              <v-select
                v-if="disposal.kind === 'discard'"
                v-model="accessoryCondition"
                :items="
                  (['good', 'scrap'] as const).map((value) => ({
                    value,
                    title: $t(`inventory.accessories.conditions.${value}`),
                  }))
                "
                :label="$t('inventory.disposals.condition')"
              />
              <MoneyField
                v-else
                v-model="accessoryValue"
                :label="$t('inventory.disposals.unitValueOptional')"
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
              >{{ $t('inventory.disposals.add') }}</v-btn
            >
          </v-card-actions>
        </v-card>
      </v-dialog>
    </template>
    <v-progress-linear v-else indeterminate />
  </v-container>
</template>
