<script setup lang="ts">
/**
 * Search the current average prices and pick one (emits `pick`, then clears itself).
 * Every asset is offered, also those already in the scenario (it may repeat). Options read "Model (specification values)", with
 * the manufacturer and asset class below.
 *
 * The asset may not be priced yet: "New Average Price", always at the end of the list, opens
 * the Average Prices form (the text typed as its model, asset classes of the scenario's
 * vertical / sub-vertical only); once saved, the new price is the one picked.
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useNumberFormat } from '@/composables/useNumberFormat'
import RemoteAutocomplete, { type RemoteOption } from '@/components/RemoteAutocomplete.vue'
import AveragePriceFormDialog from '@/modules/average-prices/AveragePriceFormDialog.vue'
import {
  listAveragePrices,
  type AveragePrice,
  type AveragePriceDetail,
} from '@/modules/average-prices/api'
import { specSummary } from '@/modules/average-prices/specText'
import { useNotificationsStore } from '@/stores/notifications'

defineOptions({ inheritAttrs: false })

const props = defineProps<{
  label: string
  /** Only assets of this vertical / sub-vertical (the scenario's) */
  vertical?: number | null
  subVertical?: number | null
}>()
const emit = defineEmits<{ pick: [id: number] }>()

const { t } = useI18n()
const { n } = useNumberFormat()
const notifications = useNotificationsStore()

/** "320 GC (2500 h, Steel, Cab: Yes)": the filled specifications, in template order. */
function optionTitle(row: AveragePrice): string {
  const specs = specSummary(row.specs, t, n)
  return specs ? `${row.model} (${specs})` : row.model
}

const selected = ref<number | null>(null)
// Remounted after each pick so the field starts empty again
const key = ref(0)
// The text last searched for: a new price's model
const typed = ref('')
const formOpen = ref(false)
const newModel = ref('')

async function search(term: string): Promise<RemoteOption[]> {
  typed.value = term
  const data = await listAveragePrices({
    page: 1,
    pageSize: 20,
    search: term,
    ordering: 'asset_class__name',
    filters: {
      ...(props.vertical ? { vertical: props.vertical } : {}),
      ...(props.subVertical ? { sub_vertical: props.subVertical } : {}),
    },
  })
  return data.results.map((row) => ({
    value: row.id,
    title: optionTitle(row),
    subtitle: `${row.manufacturer.name} · ${row.asset_class.name}`,
  }))
}

function onPick(value: number | number[] | null) {
  if (typeof value !== 'number') return
  emit('pick', value)
  selected.value = null
  key.value++
}

function createPrice() {
  newModel.value = typed.value
  formOpen.value = true
  // Closes the list (the typed text is kept for the form)
  key.value++
}

function onCreated(row: AveragePriceDetail | null) {
  if (!row) return
  notifications.notify(t('averagePrices.created'))
  if (row.increasing_terms.length) {
    notifications.notify(
      t('averagePrices.increasingWarning', { terms: row.increasing_terms.join(', ') }),
      'warning',
    )
  }
  emit('pick', row.id)
}
</script>

<template>
  <RemoteAutocomplete
    :key="key"
    v-bind="$attrs"
    :model-value="selected"
    :label="label"
    :search="search"
    :no-data-text="$t('efmv.scenario.noPriceFound')"
    @update:model-value="onPick"
  >
    <template #append-item>
      <v-divider />
      <v-list-item
        prepend-icon="mdi-plus"
        :title="$t('efmv.scenario.newPrice')"
        :subtitle="typed.trim() ? $t('efmv.scenario.newPriceFor', { model: typed.trim() }) : undefined"
        base-color="primary"
        data-testid="new-price"
        @click="createPrice"
      />
    </template>
  </RemoteAutocomplete>
  <AveragePriceFormDialog
    v-model="formOpen"
    :source="null"
    :initial-model="newModel"
    :scope-vertical="vertical"
    :scope-sub-vertical="subVertical"
    @saved="onCreated"
  />
</template>
