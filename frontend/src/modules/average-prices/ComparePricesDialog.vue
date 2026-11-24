<script setup lang="ts">
/**
 * Up to three average prices side by side as Battle Cards: photo, model, class, original value,
 * the eFMV at each term and the specifications. The cards are columns of one grid, so
 * every attribute sits on the same line in all of them (easy to read across). The best value
 * of each attribute gets a trophy (highest eFMV % at a term; most stars in a rating) and
 * each card shows how many attributes it wins (`compare.ts`; values come from the API).
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useDateFormat } from '@/composables/useDateFormat'
import { useNumberFormat } from '@/composables/useNumberFormat'
import { formatMoney } from '@/utils/money'
import { getAveragePrice, pricePhotoUrl, type AveragePriceDetail } from './api'
import { specRows, termRows, wins } from './compare'
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

const terms = computed(() => termRows(items.value))
const specs = computed(() => specRows(items.value))
const score = computed(() => wins(items.value))
const money = (value: string, currency: string) => formatMoney(value, currency, locale.value)
const spec = (value: Parameters<typeof specText>[0]) => specText(value, t, n)
const grid = computed(() => ({
  gridTemplateColumns: `repeat(${items.value.length}, minmax(220px, 1fr))`,
}))
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
        <div v-else class="battle-scroll">
          <!-- One grid: a column per card, a line per attribute (aligned across cards) -->
          <div class="battle" :style="grid">
            <!-- Header: the card's number, class and wins -->
            <div
              v-for="(item, index) in items"
              :key="`head-${item.id}`"
              class="cell head d-flex align-center ga-2"
              data-testid="compare-card"
              :data-card="index"
            >
              <span class="number">{{ index + 1 }}</span>
              <v-icon :icon="item.asset_class.icon" size="18" />
              <span class="text-truncate flex-grow-1">{{ item.asset_class.name }}</span>
              <v-chip
                size="small"
                variant="flat"
                color="surface"
                prepend-icon="mdi-trophy-outline"
                data-testid="compare-wins"
                :title="$t('averagePrices.compare.winsHint')"
                >{{ score[index] }}</v-chip
              >
            </div>

            <!-- Photo: the same small frame for every card -->
            <div v-for="item in items" :key="`photo-${item.id}`" class="cell photo">
              <v-img
                v-if="item.photo_id"
                :src="pricePhotoUrl(item.id, item.photo_id)"
                height="120"
                contain
              />
              <v-icon v-else :icon="item.asset_class.icon" size="48" class="photo-empty" />
            </div>

            <!-- Model and manufacturer -->
            <div
              v-for="item in items"
              :key="`model-${item.id}`"
              class="cell title"
              data-testid="compare-model"
            >
              <div class="text-subtitle-1 font-weight-bold">{{ item.model }}</div>
              <div class="text-body-2 text-medium-emphasis">
                {{ item.manufacturer.name }} · {{ item.sub_vertical.label }}
              </div>
            </div>

            <!-- Original value -->
            <div v-for="item in items" :key="`value-${item.id}`" class="cell row">
              <span class="label">{{ $t('averagePrices.fields.originalValue') }}</span>
              <strong>{{ money(item.original_value, item.currency) }}</strong>
            </div>

            <!-- eFMV at each term -->
            <div v-for="item in items" :key="`terms-${item.id}`" class="cell section">
              {{ $t('averagePrices.compare.efmv') }}
            </div>
            <template v-for="row in terms" :key="`term-${row.term}`">
              <div
                v-for="(item, index) in items"
                :key="`term-${row.term}-${item.id}`"
                class="cell row"
                :class="{ best: row.best[index] }"
                :data-card="index"
                data-testid="compare-term"
              >
                <span class="label">{{ $t('averagePrices.compare.months', { n: row.term }) }}</span>
                <span v-if="row.points[index]" class="text-right text-no-wrap">
                  <v-icon
                    v-if="row.best[index]"
                    icon="mdi-trophy"
                    size="x-small"
                    color="warning"
                    class="mr-1"
                  />
                  <strong>{{ n(Number(row.points[index]!.percent), 'percentValue') }}%</strong>
                  <span class="text-caption text-medium-emphasis ml-1">{{
                    money(row.points[index]!.value, item.currency)
                  }}</span>
                </span>
                <span v-else class="text-medium-emphasis">—</span>
              </div>
            </template>

            <!-- Specifications -->
            <template v-if="specs.length">
              <div v-for="item in items" :key="`specs-${item.id}`" class="cell section">
                {{ $t('averagePrices.compare.specs') }}
              </div>
              <template v-for="row in specs" :key="`spec-${row.key}`">
                <div
                  v-for="(item, index) in items"
                  :key="`spec-${row.key}-${item.id}`"
                  class="cell row"
                  :class="{ best: row.best[index] }"
                  :data-card="index"
                  data-testid="compare-spec"
                >
                  <span class="label">{{ row.label }}</span>
                  <span class="text-right">
                    <v-icon
                      v-if="row.best[index]"
                      icon="mdi-trophy"
                      size="x-small"
                      color="warning"
                      class="mr-1"
                    />{{ row.specs[index] ? spec(row.specs[index]!) : '—' }}
                  </span>
                </div>
              </template>
            </template>

            <!-- Footer -->
            <div
              v-for="item in items"
              :key="`foot-${item.id}`"
              class="cell foot text-caption text-medium-emphasis"
            >
              {{
                $t('averagePrices.compare.date', { date: d(new Date(item.created_at), 'short') })
              }}
            </div>
          </div>
        </div>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.battle-scroll {
  overflow-x: auto;
}
/* Cards are columns: a gap between them, each cell keeps the card's sides */
.battle {
  display: grid;
  column-gap: 16px;
}
.cell {
  border-left: 2px solid rgba(var(--v-border-color), 0.16);
  border-right: 2px solid rgba(var(--v-border-color), 0.16);
  padding: 6px 14px;
  min-width: 0;
}
.head {
  border: none;
  border-radius: 16px 16px 0 0;
  padding: 8px 14px;
  background: rgb(var(--v-theme-primary));
  color: rgb(var(--v-theme-on-primary));
  font-weight: 600;
}
.number {
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: rgba(var(--v-theme-on-primary), 0.2);
  font-size: 0.8rem;
}
.photo {
  display: grid;
  place-items: center;
  height: 136px;
  padding: 8px;
  background: rgba(var(--v-theme-on-surface), 0.04);
}
.photo .v-img {
  width: 100%;
}
.photo-empty {
  color: rgba(var(--v-theme-on-surface), 0.3);
}
.title {
  padding-top: 10px;
}
.section {
  padding-top: 14px;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: rgba(var(--v-theme-on-surface), 0.6);
}
.row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
  font-size: 0.875rem;
  border-top: 1px solid rgba(var(--v-border-color), 0.08);
}
.label {
  color: rgba(var(--v-theme-on-surface), 0.7);
}
.best {
  background: rgba(var(--v-theme-warning), 0.12);
}
.foot {
  border-bottom: 2px solid rgba(var(--v-border-color), 0.16);
  border-radius: 0 0 16px 16px;
  padding-top: 10px;
  padding-bottom: 10px;
}
</style>
