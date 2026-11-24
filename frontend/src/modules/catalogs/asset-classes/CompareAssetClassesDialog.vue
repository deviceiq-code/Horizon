<script setup lang="ts">
/**
 * Up to three asset classes side by side as Battle Cards (the same as Average Prices'):
 * icon, name, vertical / sub-vertical, the Remarketing ratings and their average — the most
 * stars win a trophy — and, last, the specification template (it differs between classes;
 * fields matched by name, nothing competes there). Values come from the API.
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import BattleCards, { type BattleCard, type BattleSection } from '@/components/BattleCards.vue'
import { useDateFormat } from '@/composables/useDateFormat'
import { useNumberFormat } from '@/composables/useNumberFormat'
import { winners } from '@/utils/battle'
import { getAssetClass, REMARKETING_RATINGS, type AssetClass } from './api'

const props = defineProps<{ ids: number[] }>()
const open = defineModel<boolean>({ required: true })

const { t } = useI18n()
const { n } = useNumberFormat()
const { d } = useDateFormat()

const items = ref<AssetClass[]>([])
const loading = ref(false)
const failed = ref(false)

watch(open, async (isOpen) => {
  if (!isOpen) return
  loading.value = true
  failed.value = false
  items.value = []
  try {
    items.value = await Promise.all(props.ids.map((id) => getAssetClass(id)))
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
})

const stars = (value: string) => `★ ${n(Number(value), 'rating')}`

const cards = computed<BattleCard[]>(() =>
  items.value.map((item) => ({
    id: item.id,
    header: item.sub_vertical_detail.vertical.name,
    icon: item.icon,
    title: item.name,
    subtitle: item.sub_vertical_detail.label,
  })),
)

const sections = computed<BattleSection[]>(() => {
  const ratingRows = [...REMARKETING_RATINGS, 'remarketing_average' as const].map((key) => {
    const values = items.value.map((item) => item[key])
    return {
      key,
      label:
        key === 'remarketing_average'
          ? t('assetClasses.compare.average')
          : t(`assetClasses.remarketing.${key}.label`),
      cells: values.map((value) => ({ text: stars(value) })),
      best: winners(values.map((value) => Number(value))),
    }
  })
  // The template: every field of any class, by name, in the first class's order
  const fields = new Map<string, { label: string; cells: ({ text: string } | null)[] }>()
  items.value.forEach((item, index) => {
    for (const field of item.spec_template) {
      const key = field.label.trim().toLowerCase()
      let row = fields.get(key)
      if (!row) {
        row = { label: field.label, cells: items.value.map(() => null) }
        fields.set(key, row)
      }
      const kind = t(`specTemplate.kinds.${field.kind}`)
      row.cells[index] = {
        text: `${kind}${field.unit ? ` (${field.unit})` : ''}${field.required ? ' *' : ''}`,
      }
    }
  })
  return [
    { key: 'rating', title: t('assetClasses.remarketing.title'), rows: ratingRows },
    {
      key: 'spec',
      title: t('assetClasses.compare.template'),
      rows: [...fields.entries()].map(([key, row]) => ({
        key,
        label: row.label,
        cells: row.cells,
        best: row.cells.map(() => false),
      })),
    },
  ]
})

const facts = computed(() => [
  {
    key: 'fields',
    label: t('assetClasses.compare.fields'),
    cells: items.value.map((item) => ({ text: String(item.spec_template.length) })),
    best: items.value.map(() => false),
  },
])
const footers = computed(() =>
  items.value.map((item) =>
    item.updated_at
      ? t('assetClasses.compare.date', { date: d(new Date(item.updated_at), 'short') })
      : '',
  ),
)
</script>

<template>
  <v-dialog v-model="open" max-width="1080" scrollable>
    <v-card data-testid="compare-dialog">
      <v-card-title class="d-flex align-center ga-2 pt-4 px-6">
        <v-icon icon="mdi-cards-outline" color="primary" />
        {{ $t('assetClasses.compare.title') }}
        <v-spacer />
        <v-btn icon="mdi-close" variant="text" size="small" @click="open = false" />
      </v-card-title>
      <v-card-subtitle class="px-6 text-wrap">{{
        $t('assetClasses.compare.subtitle')
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
          :wins-hint="$t('assetClasses.compare.winsHint')"
        />
      </v-card-text>
    </v-card>
  </v-dialog>
</template>
