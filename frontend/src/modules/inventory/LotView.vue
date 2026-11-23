<script setup lang="ts">
/**
 * A receiving lot: its header (customer, warehouse, appointment, dock, fiscal document) and
 * tabs — Triage (blind count), Received, Occurrences, Files and, for those who may see it, the
 * Expected List. "Reconcile" compares with the expected list; "Close" reconciles again and
 * closes when no occurrence is open (RN-18); the assets then await inspection.
 */
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import { useDateFormat } from '@/composables/useDateFormat'
import { useNotificationsStore } from '@/stores/notifications'
import ExpectedItemsEditor from './ExpectedItemsEditor.vue'
import LotAttachmentsPanel from './LotAttachmentsPanel.vue'
import LotStatusChip from './LotStatusChip.vue'
import OccurrencesPanel from './OccurrencesPanel.vue'
import StatusChip from './StatusChip.vue'
import TriagePanel from './TriagePanel.vue'
import {
  closeLot,
  getLot,
  lotExpected,
  lotReceived,
  reconcileLot,
  type Lot,
  type LotReceived,
} from './api'
import { toRows, type EditorRow } from './expectedRows'
import { useInventoryRoles } from './roles'

const props = defineProps<{ id: number }>()

const { t } = useI18n()
const { d } = useDateFormat()
const notifications = useNotificationsStore()
const { canReceive, canSeeExpected } = useInventoryRoles()

const lot = ref<Lot | null>(null)
const received = ref<LotReceived>({ units: [], accessories: [] })
const expected = ref<EditorRow[]>([])
const loadError = ref(false)
const tab = ref('triage')
const busy = ref(false)
const actionError = ref('')
const occurrences = ref<{ load: () => Promise<void> } | null>(null)

const isOpen = computed(() => lot.value && lot.value.status !== 'closed')

async function load() {
  try {
    lot.value = await getLot(props.id)
    received.value = await lotReceived(props.id)
    if (canSeeExpected.value && lot.value.appointment) {
      expected.value = toRows(await lotExpected(props.id))
    }
    if (lot.value.status === 'closed' && tab.value === 'triage') tab.value = 'received'
  } catch {
    loadError.value = true
  }
}
onMounted(load)

async function refreshLot() {
  lot.value = await getLot(props.id)
  received.value = await lotReceived(props.id)
}

async function run(action: 'reconcile' | 'close') {
  busy.value = true
  actionError.value = ''
  try {
    lot.value = action === 'reconcile' ? await reconcileLot(props.id) : await closeLot(props.id)
    notifications.notify(
      t(action === 'reconcile' ? 'inventory.lots.reconciled' : 'inventory.lots.closed'),
    )
    if (action === 'close') tab.value = 'received'
  } catch (error) {
    actionError.value = error instanceof ApiError ? error.message : t('common.saveError')
    tab.value = 'occurrences'
  } finally {
    busy.value = false
    await refreshLot()
    await occurrences.value?.load()
  }
}

function eventPlace(code: string | null, container: string | null) {
  return container ? `${code ?? ''} · ${container}` : (code ?? '—')
}
</script>

<template>
  <v-container fluid class="module-page">
    <v-alert v-if="loadError" type="error" variant="tonal">{{ $t('common.loadError') }}</v-alert>
    <template v-if="lot">
      <div class="d-flex flex-wrap align-center ga-3 mb-1">
        <h1>{{ lot.code }}</h1>
        <LotStatusChip :status="lot.status" size="default" />
        <v-spacer />
        <template v-if="canReceive && isOpen">
          <v-btn
            variant="tonal"
            prepend-icon="mdi-scale-balance"
            :loading="busy"
            :disabled="!lot.is_scheduled"
            :title="lot.is_scheduled ? '' : $t('inventory.lots.nothingToReconcile')"
            data-testid="reconcile"
            @click="run('reconcile')"
          >
            {{ $t('inventory.lots.reconcile') }}
          </v-btn>
          <v-btn
            color="primary"
            prepend-icon="mdi-lock-check-outline"
            :loading="busy"
            data-testid="close-lot"
            @click="run('close')"
          >
            {{ $t('inventory.lots.close') }}
          </v-btn>
        </template>
      </div>
      <div class="d-flex flex-wrap ga-x-6 ga-y-1 text-body-2 mb-4" data-testid="lot-header">
        <span
          ><strong>{{ $t('inventory.appointments.customer') }}:</strong>
          {{ lot.customer_name }}</span
        >
        <span>
          <strong>{{ $t('inventory.fields.warehouse') }}:</strong>
          {{ lot.warehouse_detail.code }} · {{ lot.warehouse_detail.name }}
        </span>
        <span
          ><strong>{{ $t('inventory.lots.dock') }}:</strong> {{ lot.dock_detail.code }}</span
        >
        <span>
          <strong>{{ $t('inventory.lots.appointment') }}:</strong>
          {{ lot.appointment_detail?.code ?? $t('inventory.lots.unscheduled') }}
        </span>
        <span v-if="lot.fiscal_document_number">
          <strong>{{ $t('inventory.lots.fiscalNumber') }}:</strong> {{ lot.fiscal_document_number }}
        </span>
        <span>
          <strong>{{ $t('inventory.lots.openedAt') }}:</strong>
          {{ d(new Date(lot.opened_at), 'dateTime') }} · {{ lot.opened_by_name }}
        </span>
        <span v-if="lot.closed_at">
          <strong>{{ $t('inventory.lots.closedAt') }}:</strong>
          {{ d(new Date(lot.closed_at), 'dateTime') }} · {{ lot.closed_by_name }}
        </span>
      </div>

      <v-alert
        v-if="actionError"
        type="warning"
        variant="tonal"
        density="compact"
        class="mb-4"
        data-testid="lot-error"
      >
        {{ actionError }}
      </v-alert>

      <v-card>
        <v-tabs v-model="tab">
          <v-tab v-if="canReceive && isOpen" value="triage" data-testid="tab-triage">
            {{ $t('inventory.lots.tabs.triage') }}
          </v-tab>
          <v-tab value="received" data-testid="tab-received">
            {{ $t('inventory.lots.tabs.received') }}
            <v-chip size="x-small" class="ml-2">{{ lot.units_count }}</v-chip>
          </v-tab>
          <v-tab value="occurrences" data-testid="tab-occurrences">
            {{ $t('inventory.lots.tabs.occurrences') }}
            <v-chip v-if="lot.open_occurrences" size="x-small" color="warning" class="ml-2">
              {{ lot.open_occurrences }}
            </v-chip>
          </v-tab>
          <v-tab value="files">{{ $t('inventory.lots.tabs.files') }}</v-tab>
          <v-tab
            v-if="canSeeExpected && lot.appointment"
            value="expected"
            data-testid="tab-expected"
          >
            {{ $t('inventory.expected.title') }}
          </v-tab>
        </v-tabs>
        <v-divider />
        <v-card-text>
          <v-window v-model="tab">
            <v-window-item v-if="canReceive && isOpen" value="triage">
              <TriagePanel :lot="lot" @changed="refreshLot" />
            </v-window-item>
            <v-window-item value="received">
              <div class="text-subtitle-2 text-medium-emphasis mb-2">
                {{ $t('inventory.triage.units') }}
              </div>
              <v-table density="compact" class="mb-6" data-testid="received-units">
                <thead>
                  <tr>
                    <th>{{ $t('inventory.fields.horizonId') }}</th>
                    <th>{{ $t('inventory.fields.asset') }}</th>
                    <th>{{ $t('inventory.fields.serial') }}</th>
                    <th>{{ $t('inventory.fields.location') }}</th>
                    <th>{{ $t('inventory.fields.status') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="a in received.units" :key="a.id">
                    <td class="font-weight-medium">{{ a.horizon_id }}</td>
                    <td>
                      {{ a.asset_model_detail.manufacturer_name }} {{ a.asset_model_detail.name }}
                    </td>
                    <td>{{ a.serial || $t(`inventory.serialStatus.${a.serial_status}`) }}</td>
                    <td>
                      {{
                        eventPlace(
                          a.current_location_detail.code,
                          a.current_container_detail?.code ?? null,
                        )
                      }}
                    </td>
                    <td><StatusChip :status="a.status" size="x-small" /></td>
                  </tr>
                  <tr v-if="!received.units.length">
                    <td colspan="5" class="text-medium-emphasis">
                      {{ $t('inventory.lots.noUnits') }}
                    </td>
                  </tr>
                </tbody>
              </v-table>
              <div class="text-subtitle-2 text-medium-emphasis mb-2">
                {{ $t('inventory.triage.accessories') }}
              </div>
              <v-table density="compact" data-testid="received-accessories">
                <thead>
                  <tr>
                    <th>{{ $t('inventory.fields.assetModel') }}</th>
                    <th>{{ $t('inventory.expected.quantity') }}</th>
                    <th>{{ $t('inventory.accessories.condition') }}</th>
                    <th>{{ $t('inventory.fields.location') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="e in received.accessories" :key="e.id">
                    <td>{{ e.accessory_model_label }}</td>
                    <td>{{ e.quantity }}</td>
                    <td>
                      {{
                        $t(`inventory.accessories.conditions.${e.accessory_condition || 'good'}`)
                      }}
                    </td>
                    <td>{{ eventPlace(e.to_location_code, e.to_container_code) }}</td>
                  </tr>
                  <tr v-if="!received.accessories.length">
                    <td colspan="4" class="text-medium-emphasis">
                      {{ $t('inventory.lots.noAccessories') }}
                    </td>
                  </tr>
                </tbody>
              </v-table>
            </v-window-item>
            <v-window-item value="occurrences">
              <OccurrencesPanel ref="occurrences" :lot="lot" @changed="refreshLot" />
            </v-window-item>
            <v-window-item value="files">
              <LotAttachmentsPanel :lot="lot" />
            </v-window-item>
            <v-window-item v-if="canSeeExpected && lot.appointment" value="expected">
              <ExpectedItemsEditor v-model="expected" readonly />
            </v-window-item>
          </v-window>
        </v-card-text>
      </v-card>
    </template>
  </v-container>
</template>
