<script setup lang="ts">
/**
 * A list of short texts as removable chips plus an input: Enter, comma or leaving the input
 * adds what was typed (several at once, separated by commas). Letter case is kept; an item
 * already in the list (any case) is not added again. `fixed`: items that always count, shown
 * first and not removable (e.g. the dictionary's own spelling, in any case); typed again, they
 * are not added.
 */
import { ref } from 'vue'

const model = defineModel<string[]>({ required: true })
const props = withDefaults(
  defineProps<{
    label: string
    hint?: string
    errorMessages?: string[]
    maxLength?: number
    fixed?: string[]
    fixedTitle?: string
  }>(),
  {
    hint: undefined,
    errorMessages: undefined,
    maxLength: 100,
    fixed: () => [],
    fixedTitle: undefined,
  },
)

const draft = ref('')

function add() {
  const items = [...model.value]
  const taken = (text: string) =>
    [...items, ...props.fixed].some((item) => item.toLowerCase() === text.toLowerCase())
  for (const part of draft.value.split(',')) {
    const text = part.split(/\s+/).filter(Boolean).join(' ')
    if (text && !taken(text)) {
      items.push(text)
    }
  }
  model.value = items
  draft.value = ''
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' || event.key === ',') {
    event.preventDefault() // Enter would submit the form; the comma is a separator
    add()
  }
}

function removeAt(index: number) {
  model.value = model.value.filter((_, i) => i !== index)
}
</script>

<template>
  <div data-testid="list-items">
    <div v-if="model.length || fixed.length" class="d-flex flex-wrap ga-1 mb-2">
      <v-chip
        v-for="item in fixed"
        :key="`fixed-${item}`"
        size="small"
        variant="outlined"
        prepend-icon="mdi-format-letter-case"
        :title="fixedTitle"
        data-testid="list-item-fixed"
      >
        {{ item }}
      </v-chip>
      <v-chip
        v-for="(item, index) in model"
        :key="item"
        size="small"
        closable
        data-testid="list-item"
        @click:close="removeAt(index)"
      >
        {{ item }}
      </v-chip>
    </div>
    <v-text-field
      v-model="draft"
      :label="label"
      :hint="hint"
      :persistent-hint="!!hint"
      :error-messages="errorMessages"
      :maxlength="maxLength"
      density="compact"
      data-testid="list-input"
      @keydown="onKeydown"
      @blur="add"
    />
  </div>
</template>
