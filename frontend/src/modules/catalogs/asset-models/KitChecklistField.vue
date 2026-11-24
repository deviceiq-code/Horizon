<script setup lang="ts">
/**
 * The kit checklist of an asset model: items expected with each unit, each marked essential
 * (missing → incomplete, "I") or accessory (missing → partial, "P"). Type an item and press
 * Enter; the star marks it essential.
 */
import { ref } from 'vue'
import type { KitItem } from './api'

const items = defineModel<KitItem[]>({ required: true })
defineProps<{ label: string; hint?: string; errorMessages?: string[] }>()

const draft = ref('')

function add() {
  const next = [...items.value]
  for (const part of draft.value.split(',')) {
    const text = part.split(/\s+/).filter(Boolean).join(' ')
    if (text && !next.some((entry) => entry.item.toLowerCase() === text.toLowerCase())) {
      next.push({ item: text, essential: false })
    }
  }
  items.value = next
  draft.value = ''
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' || event.key === ',') {
    event.preventDefault()
    add()
  }
}

function toggle(index: number) {
  items.value = items.value.map((entry, i) =>
    i === index ? { ...entry, essential: !entry.essential } : entry,
  )
}

function remove(index: number) {
  items.value = items.value.filter((_, i) => i !== index)
}
</script>

<template>
  <div data-testid="kit-checklist">
    <v-text-field
      v-model="draft"
      :label="label"
      :hint="hint"
      persistent-hint
      :error-messages="errorMessages"
      maxlength="200"
      data-testid="kit-input"
      @keydown="onKeydown"
      @blur="add"
    />
    <div class="d-flex flex-wrap ga-1 mt-2">
      <v-chip
        v-for="(entry, index) in items"
        :key="entry.item"
        :color="entry.essential ? 'primary' : undefined"
        :variant="entry.essential ? 'flat' : 'tonal'"
        size="small"
        closable
        data-testid="kit-item"
        @click:close="remove(index)"
      >
        <v-icon
          :icon="entry.essential ? 'mdi-star' : 'mdi-star-outline'"
          start
          size="16"
          :title="$t(entry.essential ? 'assetModels.kitEssential' : 'assetModels.kitAccessory')"
          data-testid="kit-essential"
          @click.stop="toggle(index)"
        />
        {{ entry.item }}
      </v-chip>
    </div>
  </div>
</template>
