<script setup lang="ts">
/**
 * Movement by reading codes with a barcode gun (it types the code and Enter): read the asset or
 * container, then the destination (a location, or a container for an asset). One field, always
 * focused; every reading answers with a color and a sound. The check digit is verified here
 * and again by the server (RN-15); the server applies the area rules (RN-02).
 */
import { computed, nextTick, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import { useDateFormat } from '@/composables/useDateFormat'
import { parseCode } from '@/utils/inventoryCodes'
import AreaChip from './AreaChip.vue'
import StatusChip from './StatusChip.vue'
import {
  lookupCode,
  moveByCodes,
  myLatestMovements,
  type LookupResult,
  type MovementEvent,
} from './api'
import { beep } from './beep'

const { t } = useI18n()
const { d } = useDateFormat()

type Step = 'object' | 'destination'
type Feedback = { kind: 'success' | 'error' | 'info'; text: string } | null

const step = ref<Step>('object')
const reading = ref('')
const reason = ref('')
const busy = ref(false)
const target = ref<LookupResult | null>(null)
const feedback = ref<Feedback>(null)
const latest = ref<MovementEvent[]>([])
const scanField = ref<{ focus: () => void } | null>(null)

const prompt = computed(() =>
  step.value === 'object'
    ? t('inventory.movement.readObject')
    : t('inventory.movement.readDestination'),
)

function focusScan() {
  nextTick(() => scanField.value?.focus())
}

function fail(text: string) {
  feedback.value = { kind: 'error', text }
  beep(false)
}

function errorText(error: unknown): string {
  return error instanceof ApiError && error.message ? error.message : t('common.saveError')
}

async function readObject(text: string) {
  const parsed = parseCode(text)
  if (parsed.kind === 'location') return fail(t('inventory.movement.locationFirst'))
  if (parsed.kind === 'unknown')
    return fail(t('inventory.movement.unknownCode', { code: parsed.code }))
  if (!parsed.valid) return fail(t('inventory.movement.wrongDigit'))
  const found = await lookupCode(parsed.code)
  if (found.kind === 'location') return fail(t('inventory.movement.locationFirst'))
  target.value = found
  step.value = 'destination'
  feedback.value = { kind: 'info', text: t('inventory.movement.objectRead', { code: parsed.code }) }
  beep(true)
}

async function readDestination(text: string) {
  const parsed = parseCode(text)
  if (parsed.kind === 'unknown')
    return fail(t('inventory.movement.unknownCode', { code: parsed.code }))
  if (!parsed.valid) return fail(t('inventory.movement.wrongDigit'))
  const objectCode =
    target.value!.kind === 'asset' ? target.value!.item.horizon_id : target.value!.item.code
  const event = await moveByCodes(objectCode, parsed.code, reason.value)
  latest.value = [event, ...latest.value].slice(0, 10)
  feedback.value = {
    kind: 'success',
    text: t('inventory.movement.moved', { object: objectCode, destination: parsed.code }),
  }
  beep(true)
  reset(false)
}

async function onEnter() {
  const text = reading.value.trim()
  reading.value = ''
  if (!text || busy.value) return focusScan()
  busy.value = true
  try {
    if (step.value === 'object') await readObject(text)
    else await readDestination(text)
  } catch (error) {
    fail(errorText(error))
  } finally {
    busy.value = false
    focusScan()
  }
}

/** Back to reading an object (Esc or the Cancel button). */
function reset(clearFeedback = true) {
  step.value = 'object'
  target.value = null
  reason.value = ''
  reading.value = ''
  if (clearFeedback) feedback.value = null
  focusScan()
}

onMounted(async () => {
  focusScan()
  try {
    latest.value = (await myLatestMovements()).results
  } catch {
    latest.value = []
  }
})

function eventText(event: MovementEvent): string {
  const from = event.from_container_code ?? event.from_location_code ?? '—'
  const to = event.to_container_code ?? event.to_location_code ?? '—'
  return `${from} → ${to}`
}
</script>

<template>
  <v-container fluid class="module-page" style="max-width: 1100px">
    <h1 class="mb-1">{{ $t('inventory.movement.title') }}</h1>
    <p class="text-medium-emphasis mb-4">{{ $t('inventory.movement.subtitle') }}</p>

    <v-row>
      <v-col cols="12" md="7">
        <v-card class="pa-6" data-testid="scan-card">
          <div class="d-flex align-center ga-3 mb-4">
            <v-chip
              :color="step === 'object' ? 'primary' : undefined"
              :variant="step === 'object' ? 'flat' : 'tonal'"
              label
            >
              1 · {{ $t('inventory.movement.object') }}
            </v-chip>
            <v-icon icon="mdi-chevron-right" />
            <v-chip
              :color="step === 'destination' ? 'primary' : undefined"
              :variant="step === 'destination' ? 'flat' : 'tonal'"
              label
            >
              2 · {{ $t('inventory.movement.destination') }}
            </v-chip>
          </div>

          <v-text-field
            ref="scanField"
            v-model="reading"
            :label="prompt"
            prepend-inner-icon="mdi-barcode-scan"
            :loading="busy"
            autocomplete="off"
            autofocus
            hide-details
            class="scan-field"
            data-testid="scan"
            @keydown.enter.prevent="onEnter"
            @keydown.esc.prevent="reset()"
          />

          <v-alert
            v-if="feedback"
            :type="feedback.kind"
            variant="tonal"
            class="mt-4 feedback"
            data-testid="feedback"
          >
            {{ feedback.text }}
          </v-alert>

          <!-- What was read: the object to move -->
          <v-card v-if="target" variant="outlined" class="mt-4 pa-4" data-testid="target">
            <template v-if="target.kind === 'asset'">
              <div class="d-flex align-center flex-wrap ga-2">
                <span class="text-h6 font-weight-bold">{{ target.item.horizon_id }}</span>
                <StatusChip :status="target.item.status" :held="target.item.held_for_dispute" />
              </div>
              <div class="text-body-1">
                {{ target.item.asset_model_detail.manufacturer_name }}
                {{ target.item.asset_model_detail.name }}
                <span class="text-medium-emphasis">
                  · {{ target.item.asset_model_detail.asset_class_name }}
                </span>
              </div>
              <div class="text-body-2 text-medium-emphasis">
                {{ $t('inventory.fields.serial') }}: {{ target.item.serial || '—' }}
              </div>
              <div class="d-flex align-center ga-2 mt-2">
                <span class="text-body-2">{{ $t('inventory.movement.now') }}</span>
                <strong>{{ target.item.current_location_detail.code }}</strong>
                <AreaChip :area="target.item.current_location_detail.area_type" size="x-small" />
                <span v-if="target.item.current_container_detail" class="text-body-2">
                  · {{ target.item.current_container_detail.code }}
                </span>
              </div>
            </template>
            <template v-else-if="target.kind === 'container'">
              <div class="text-h6 font-weight-bold">{{ target.item.code }}</div>
              <div class="text-body-1">
                {{ $t(`inventory.containerKinds.${target.item.kind}`) }} ·
                {{ $t('inventory.containers.assetsInside', target.item.assets_count) }}
              </div>
              <div class="d-flex align-center ga-2 mt-2">
                <span class="text-body-2">{{ $t('inventory.movement.now') }}</span>
                <strong>{{ target.item.current_location_detail.code }}</strong>
                <AreaChip :area="target.item.current_location_detail.area_type" size="x-small" />
              </div>
            </template>
            <v-text-field
              v-model="reason"
              :label="$t('inventory.fields.reason')"
              density="compact"
              hide-details
              class="mt-4"
              maxlength="300"
              data-testid="reason"
              @keydown.enter.prevent="focusScan"
            />
            <div class="d-flex justify-end mt-3">
              <v-btn variant="text" prepend-icon="mdi-close" data-testid="cancel" @click="reset()">
                {{ $t('common.cancel') }} (Esc)
              </v-btn>
            </div>
          </v-card>
        </v-card>
      </v-col>

      <v-col cols="12" md="5">
        <v-card class="pa-4">
          <div class="text-subtitle-1 font-weight-medium mb-2">
            {{ $t('inventory.movement.latest') }}
          </div>
          <v-list v-if="latest.length" density="compact" data-testid="latest">
            <v-list-item v-for="event in latest" :key="event.id" class="px-0">
              <v-list-item-title class="font-weight-medium">
                {{ event.asset_code ?? event.container_code }}
              </v-list-item-title>
              <v-list-item-subtitle>{{ eventText(event) }}</v-list-item-subtitle>
              <template #append>
                <span class="text-caption text-medium-emphasis">{{
                  d(new Date(event.at), 'dateTime')
                }}</span>
              </template>
            </v-list-item>
          </v-list>
          <p v-else class="text-body-2 text-medium-emphasis">
            {{ $t('inventory.movement.noneYet') }}
          </p>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<style scoped>
.scan-field :deep(input) {
  font-size: 1.5rem;
  letter-spacing: 0.06em;
  min-height: 64px;
}
.feedback {
  font-size: 1.1rem;
}
</style>
