<script setup lang="ts">
/**
 * Which assets a scenario admits: a vertical (all its sub-verticals) or one sub-vertical of it.
 * One list, each vertical followed by its sub-verticals (indented); enabled verticals only and,
 * with `verticals`, only those (e.g. the ones the account manager works in).
 * v-model: { vertical, sub_vertical } (sub_vertical null = the whole vertical).
 */
import { computed, onMounted, ref } from 'vue'
import { listSubVerticals, type SubVerticalOption } from '@/modules/catalogs/verticals/api'

export interface VerticalScope {
  vertical: number | null
  sub_vertical: number | null
}

interface ScopeOption {
  /** "v:<vertical id>" or "s:<sub-vertical id>" */
  value: string
  title: string
  vertical: number
  sub_vertical: number | null
}

const model = defineModel<VerticalScope>({ required: true })
const props = defineProps<{
  label: string
  /** Shown while the list loads, and when the current choice is no longer offered */
  currentLabel?: string | null
  rules?: ((value: unknown) => true | string)[]
  errorMessages?: string[]
  /** Only these verticals (ids) are offered; absent: every enabled one */
  verticals?: number[] | null
}>()

const subs = ref<SubVerticalOption[]>([])
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    const data = await listSubVerticals({ page: 1, pageSize: 200, filters: { is_enabled: true } })
    subs.value = data.results
  } catch {
    /* only the current choice is offered */
  } finally {
    loading.value = false
  }
})

const options = computed<ScopeOption[]>(() => {
  const list: ScopeOption[] = []
  const seen = new Set<number>()
  for (const sub of subs.value) {
    if (props.verticals && !props.verticals.includes(sub.vertical.id)) continue
    if (!seen.has(sub.vertical.id)) {
      seen.add(sub.vertical.id)
      list.push({
        value: `v:${sub.vertical.id}`,
        title: sub.vertical.name,
        vertical: sub.vertical.id,
        sub_vertical: null,
      })
    }
    list.push({
      value: `s:${sub.id}`,
      title: sub.label,
      vertical: sub.vertical.id,
      sub_vertical: sub.id,
    })
  }
  // The current choice, if it is not offered (e.g. its vertical was disabled since)
  const current = selected.value
  if (current && !list.some((o) => o.value === current)) {
    const { vertical, sub_vertical } = model.value
    list.unshift({
      value: current,
      title: props.currentLabel ?? '—',
      vertical: vertical!,
      sub_vertical,
    })
  }
  return list
})

const selected = computed(() => {
  const { vertical, sub_vertical } = model.value
  if (vertical === null) return null
  return sub_vertical === null ? `v:${vertical}` : `s:${sub_vertical}`
})

function onSelect(value: string | null) {
  const option = options.value.find((o) => o.value === value)
  model.value = option
    ? { vertical: option.vertical, sub_vertical: option.sub_vertical }
    : { vertical: null, sub_vertical: null }
}
</script>

<template>
  <v-autocomplete
    :model-value="selected"
    :items="options"
    item-title="title"
    item-value="value"
    :label="label"
    :loading="loading"
    :rules="rules"
    :error-messages="errorMessages"
    clearable
    @update:model-value="onSelect"
  >
    <template #item="{ props: itemProps, item }">
      <v-list-item
        v-bind="itemProps"
        :class="{ 'pl-10': item.sub_vertical !== null }"
        :title="
          item.sub_vertical === null ? item.title : item.title.split(' / ').slice(1).join(' / ')
        "
        :prepend-icon="item.sub_vertical === null ? 'mdi-domain' : 'mdi-subdirectory-arrow-right'"
      />
    </template>
  </v-autocomplete>
</template>
