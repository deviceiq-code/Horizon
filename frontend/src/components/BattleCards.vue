<script setup lang="ts">
/**
 * Battle Cards: up to three records side by side as columns of one grid, so every attribute
 * sits on the same line in all of them. Each card has a header (number, icon, name, trophies
 * won), a picture in a small fixed frame (or the icon), a title and a subtitle; then sections
 * of rows (label + one cell per card). The cells marked `best` get a trophy and a soft
 * highlight; the header counts them. Pages compute the rows (what competes and who wins).
 */
import { computed } from 'vue'

export interface BattleCard {
  id: number
  /** Header: the class or kind ("Excavators") and its icon */
  header: string
  icon: string
  image?: string | null
  title: string
  subtitle?: string
}

export interface BattleCell {
  text: string
  /** Smaller text beside it (e.g. a value) */
  detail?: string
}

export interface BattleRow {
  key: string
  label: string
  /** One per card; null = the card has nothing there ("—") */
  cells: (BattleCell | null)[]
  /** Per card: it wins this attribute */
  best: boolean[]
}

export interface BattleSection {
  key: string
  title: string
  rows: BattleRow[]
}

const props = defineProps<{
  cards: BattleCard[]
  sections: BattleSection[]
  /** Lines right under the title (e.g. an original value), not competing */
  facts?: BattleRow[]
  footers?: string[]
  winsHint: string
}>()

const wins = computed(() =>
  props.cards.map(
    (_, index) => props.sections.flatMap((s) => s.rows).filter((row) => row.best[index]).length,
  ),
)
const grid = computed(() => ({
  gridTemplateColumns: `repeat(${props.cards.length}, minmax(220px, 1fr))`,
}))
</script>

<template>
  <div class="battle-scroll">
    <div class="battle" :style="grid">
      <div
        v-for="(card, index) in cards"
        :key="`head-${card.id}`"
        class="cell head d-flex align-center ga-2"
        data-testid="compare-card"
        :data-card="index"
      >
        <span class="number">{{ index + 1 }}</span>
        <v-icon :icon="card.icon" size="18" />
        <span class="text-truncate flex-grow-1">{{ card.header }}</span>
        <v-chip
          size="small"
          variant="flat"
          color="surface"
          prepend-icon="mdi-trophy-outline"
          data-testid="compare-wins"
          :title="winsHint"
          >{{ wins[index] }}</v-chip
        >
      </div>

      <div v-for="card in cards" :key="`photo-${card.id}`" class="cell photo">
        <v-img v-if="card.image" :src="card.image" height="120" contain />
        <v-icon v-else :icon="card.icon" size="48" class="photo-empty" />
      </div>

      <div
        v-for="card in cards"
        :key="`title-${card.id}`"
        class="cell title"
        data-testid="compare-model"
      >
        <div class="text-subtitle-1 font-weight-bold">{{ card.title }}</div>
        <div v-if="card.subtitle" class="text-body-2 text-medium-emphasis">
          {{ card.subtitle }}
        </div>
      </div>

      <template v-for="row in facts ?? []" :key="`fact-${row.key}`">
        <div v-for="(card, index) in cards" :key="`fact-${row.key}-${card.id}`" class="cell row">
          <span class="label">{{ row.label }}</span>
          <strong v-if="row.cells[index]">{{ row.cells[index]!.text }}</strong>
          <span v-else class="text-medium-emphasis">—</span>
        </div>
      </template>

      <template v-for="section in sections" :key="`section-${section.key}`">
        <template v-if="section.rows.length">
          <div
            v-for="card in cards"
            :key="`section-${section.key}-${card.id}`"
            class="cell section"
          >
            {{ section.title }}
          </div>
          <template v-for="row in section.rows" :key="`row-${section.key}-${row.key}`">
            <div
              v-for="(card, index) in cards"
              :key="`row-${section.key}-${row.key}-${card.id}`"
              class="cell row"
              :class="{ best: row.best[index] }"
              :data-card="index"
              :data-testid="`compare-${section.key}`"
            >
              <span class="label text-truncate">{{ row.label }}</span>
              <span v-if="row.cells[index]" class="text-right text-no-wrap">
                <v-icon
                  v-if="row.best[index]"
                  icon="mdi-trophy"
                  size="x-small"
                  color="warning"
                  class="mr-1"
                />
                <strong>{{ row.cells[index]!.text }}</strong>
                <span
                  v-if="row.cells[index]!.detail"
                  class="text-caption text-medium-emphasis ml-1"
                  >{{ row.cells[index]!.detail }}</span
                >
              </span>
              <span v-else class="text-medium-emphasis">—</span>
            </div>
          </template>
        </template>
      </template>

      <div
        v-for="(card, index) in cards"
        :key="`foot-${card.id}`"
        class="cell foot text-caption text-medium-emphasis"
      >
        {{ footers?.[index] ?? ' ' }}
      </div>
    </div>
  </div>
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
