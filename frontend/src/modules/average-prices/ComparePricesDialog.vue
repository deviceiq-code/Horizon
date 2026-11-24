<script setup lang="ts">
/**
 * Up to three average prices side by side as Battle Cards (`components/BattleCards.vue`):
 * photo, model, class, original value, the eFMV at each term and, last, the specifications
 * (they may differ between items). The trophy marks the best value of each attribute — the
 * highest eFMV % at a term, the most stars in a rating (`compare.ts`; values from the API).
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import BattleCards, { type BattleCard, type BattleSection } from '@/components/BattleCards.vue'
import { useDateFormat } from '@/composables/useDateFormat'
import { useNumberFormat } from '@/composables/useNumberFormat'
import { formatMoney } from '@/utils/money'
import { getAveragePrice, pricePhotoUrl, type AveragePriceDetail } from './api'
import { specRows, termRows } from './compare'
import { specText } from './specText'

const props = defineProps<{ ids: number[] }>()
const open = defineModel<boolean>({ required: true })

const { t, locale } = useI18n()
const { n } = useNumberFormat()
const { d } = useDateFormat()

const items = ref<AveragePriceDetail[]>([])
const loading = ref(false)
const failed = ref(false)

watch(open, async (isOpen) => {
  if (!isOpen) return
  loading.value = true
  failed.value = false
  items.value = []
  try {
    items.value = await Promise.all(props.ids.map((id) => getAveragePrice(id)))
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
})

const money = (value: string, currency: string) => formatMoney(value, currency, locale.value)

const cards = computed<BattleCard[]>(() =>
  items.value.map((item) => ({
    id: item.id,
    header: item.asset_class.name,
    icon: item.asset_class.icon,
    image: item.photo_id ? pricePhotoUrl(item.id, item.photo_id) : null,
    title: item.model,
    subtitle: `${item.manufacturer.name} · ${item.sub_vertical.label}`,
  })),
)
const facts = computed(() => [
  {
    key: 'original',
    label: t('averagePrices.fields.originalValue'),
    cells: items.value.map((item) => ({ text: money(item.original_value, item.currency) })),
    best: items.value.map(() => false),
  },
])
const sections = computed<BattleSection[]>(() => [
  {
    key: 'term',
    title: t('averagePrices.compare.efmv'),
    rows: termRows(items.value).map((row) => ({
      key: String(row.term),
      label: t('averagePrices.compare.months', { n: row.term }),
      cells: row.points.map((point, index) =>
        point
          ? {
              text: `${n(Number(point.percent), 'percentValue')}%`,
              detail: money(point.value, items.value[index]!.currency),
            }
          : null,
      ),
      best: row.best,
    })),
  },
  {
    key: 'spec',
    title: t('averagePrices.compare.specs'),
    rows: specRows(items.value).map((row) => ({
      key: row.key,
      label: row.label,
      cells: row.specs.map((spec) => (spec ? { text: specText(spec, t, n) } : null)),
      best: row.best,
    })),
  },
])
const footers = computed(() =>
  items.value.map((item) =>
    t('averagePrices.compare.date', { date: d(new Date(item.created_at), 'short') }),
  ),
)
</script>

<template>
  <v-dialog v-model="open" max-width="1080" scrollable>
    <v-card data-testid="compare-dialog">
      <v-card-title class="d-flex align-center ga-2 pt-4 px-6">
        <v-icon icon="mdi-cards-outline" color="primary" />
        {{ $t('averagePrices.compare.title') }}
        <v-spacer />
        <v-btn icon="mdi-close" variant="text" size="small" @click="open = false" />
      </v-card-title>
      <v-card-subtitle class="px-6 text-wrap">{{
        $t('averagePrices.compare.subtitle')
      }}</v-card-subtitle>
      <v-card-text class="px-6 pb-6">
        <v-progress-linear v-if="loading" indeterminate class="mb-4" />
        <v-alert v-else-if="failed" type="error" variant="tonal">{{
          $t('common.loadError')
        }}</v-alert>
        <BattleCards
          v-else
          :cards="cards"
          :facts="facts"
          :sections="sections"
          :footers="footers"
          :wins-hint="$t('averagePrices.compare.winsHint')"
        />
      </v-card-text>
    </v-card>
  </v-dialog>
</template>
