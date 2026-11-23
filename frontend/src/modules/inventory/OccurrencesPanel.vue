<script setup lang="ts">
/**
 * A lot's occurrences: the reconciliation's (automatic) and those registered by hand
 * (transport damage, lost…). Receivers and supervisors resolve them; only supervisors accept a
 * divergence as it is. A lot closes only when none is open (RN-18).
 */
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import { useNotificationsStore } from '@/stores/notifications'
import {
  OCCURRENCE_KINDS,
  acceptOccurrence,
  createOccurrence,
  listOccurrences,
  resolveOccurrence,
  type Lot,
  type Occurrence,
  type OccurrenceKind,
} from './api'
import { useInventoryRoles } from './roles'

const props = defineProps<{ lot: Lot }>()
const emit = defineEmits<{ changed: [] }>()

const { t } = useI18n()
const notifications = useNotificationsStore()
const { canReceive, isSupervisor } = useInventoryRoles()

const items = ref<Occurrence[]>([])
const loading = ref(false)
const closed = computed(() => props.lot.status === 'closed')

async function load() {
  loading.value = true
  try {
    items.value = (
      await listOccurrences({ page: 1, pageSize: 200, filters: { lot: props.lot.id } })
    ).results
  } finally {
    loading.value = false
  }
}
onMounted(load)
defineExpose({ load })

const STATUS_COLORS = { open: 'warning', resolved: 'success', accepted: 'info' } as const

function details(o: Occurrence): string {
  const parts = [o.asset_model_label]
  if (o.expected_serial || o.received_serial) {
    parts.push(
      t('inventory.occurrences.serials', {
        expected: o.expected_serial || '—',
        received: o.received_serial || '—',
      }),
    )
  }
  if (o.asset_code) parts.push(o.asset_code)
  if (o.quantity > 1) parts.push(t('inventory.occurrences.quantity', { n: o.quantity }))
  return parts.filter(Boolean).join(' · ')
}

// --- New -------------------------------------------------------------------------------------

const newOpen = ref(false)
const kind = ref<OccurrenceKind>('transport_damage')
const quantity = ref('1')
const description = ref('')
const dueDate = ref('')
const kindOptions = computed(() =>
  OCCURRENCE_KINDS.map((value) => ({ value, title: t(`inventory.occurrences.kinds.${value}`) })),
)

async function create() {
  try {
    await createOccurrence({
      lot: props.lot.id,
      kind: kind.value,
      quantity: Number(quantity.value) || 1,
      description: description.value,
      due_date: dueDate.value || null,
    })
    newOpen.value = false
    description.value = ''
    await load()
    emit('changed')
  } catch (error) {
    notifications.notify(error instanceof ApiError ? error.message : t('common.saveError'), 'error')
  }
}

// --- Resolve / accept ------------------------------------------------------------------------

const decisionOpen = ref(false)
const decision = ref<'resolve' | 'accept'>('resolve')
const target = ref<Occurrence | null>(null)
const resolution = ref('')
const decisionError = ref('')

function decide(occurrence: Occurrence, how: 'resolve' | 'accept') {
  target.value = occurrence
  decision.value = how
  resolution.value = ''
  decisionError.value = ''
  decisionOpen.value = true
}

async function confirmDecision() {
  if (!target.value) return
  try {
    if (decision.value === 'resolve') await resolveOccurrence(target.value.id, resolution.value)
    else await acceptOccurrence(target.value.id, resolution.value)
    decisionOpen.value = false
    await load()
    emit('changed')
  } catch (error) {
    decisionError.value = error instanceof ApiError ? error.message : t('common.saveError')
  }
}
</script>

<template>
  <div>
    <div class="d-flex align-center mb-3">
      <span class="text-body-2 text-medium-emphasis">{{ $t('inventory.occurrences.hint') }}</span>
      <v-spacer />
      <v-btn
        v-if="canReceive && !closed"
        variant="tonal"
        prepend-icon="mdi-plus"
        data-testid="new-occurrence"
        @click="newOpen = true"
      >
        {{ $t('inventory.occurrences.new') }}
      </v-btn>
    </div>

    <v-progress-linear v-if="loading" indeterminate class="mb-2" />
    <v-list v-if="items.length" lines="three" data-testid="occurrences">
      <v-list-item v-for="o in items" :key="o.id" class="px-0" data-testid="occurrence">
        <template #prepend>
          <v-icon
            :icon="o.automatic ? 'mdi-scale-balance' : 'mdi-alert-circle-outline'"
            class="mr-2"
          />
        </template>
        <v-list-item-title class="d-flex flex-wrap align-center ga-2">
          <strong>{{ $t(`inventory.occurrences.kinds.${o.kind}`) }}</strong>
          <v-chip :color="STATUS_COLORS[o.status]" size="x-small" variant="tonal" label>
            {{ $t(`inventory.occurrences.statuses.${o.status}`) }}
          </v-chip>
          <v-chip v-if="o.automatic" size="x-small" variant="outlined" label>
            {{ $t('inventory.occurrences.automatic') }}
          </v-chip>
        </v-list-item-title>
        <v-list-item-subtitle>{{ details(o) }}</v-list-item-subtitle>
        <div v-if="o.description" class="text-body-2">{{ o.description }}</div>
        <div v-if="o.resolution" class="text-body-2 text-medium-emphasis">
          {{ o.resolution }} — {{ o.resolved_by_name }}
        </div>
        <template v-if="o.status === 'open' && !closed" #append>
          <div class="d-flex ga-1">
            <v-btn
              v-if="canReceive"
              size="small"
              variant="tonal"
              data-testid="resolve"
              @click="decide(o, 'resolve')"
            >
              {{ $t('inventory.occurrences.resolve') }}
            </v-btn>
            <v-btn
              v-if="isSupervisor"
              size="small"
              variant="tonal"
              color="info"
              data-testid="accept"
              @click="decide(o, 'accept')"
            >
              {{ $t('inventory.occurrences.accept') }}
            </v-btn>
          </div>
        </template>
      </v-list-item>
    </v-list>
    <p v-else-if="!loading" class="text-body-2 text-medium-emphasis">
      {{ $t('inventory.occurrences.empty') }}
    </p>

    <v-dialog v-model="newOpen" max-width="560">
      <v-card :title="$t('inventory.occurrences.new')">
        <v-card-text>
          <v-select v-model="kind" :items="kindOptions" :label="$t('inventory.occurrences.kind')" />
          <v-text-field
            v-model="quantity"
            :label="$t('inventory.expected.quantity')"
            inputmode="numeric"
          />
          <v-textarea
            v-model="description"
            :label="$t('inventory.occurrences.description')"
            rows="3"
            auto-grow
          />
          <v-text-field
            v-model="dueDate"
            type="date"
            :label="$t('inventory.occurrences.dueDate')"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="newOpen = false">{{ $t('common.cancel') }}</v-btn>
          <v-btn color="primary" variant="flat" data-testid="occurrence-save" @click="create">
            {{ $t('common.save') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="decisionOpen" max-width="560">
      <v-card
        :title="
          decision === 'resolve'
            ? $t('inventory.occurrences.resolveTitle')
            : $t('inventory.occurrences.acceptTitle')
        "
      >
        <v-card-text>
          <v-textarea
            v-model="resolution"
            :label="
              decision === 'resolve'
                ? $t('inventory.occurrences.resolution')
                : $t('inventory.occurrences.acceptReason')
            "
            :error-messages="decisionError"
            rows="3"
            auto-grow
            autofocus
            data-testid="resolution"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="decisionOpen = false">{{ $t('common.cancel') }}</v-btn>
          <v-btn
            color="primary"
            variant="flat"
            data-testid="decision-save"
            @click="confirmDecision"
          >
            {{ $t('common.save') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>
