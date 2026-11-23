<script setup lang="ts">
/**
 * A money field as every value field in the system: the currency on the left — its symbol or
 * code, as the user chose (Settings → Numbers and Currency) — and the value on the right,
 * formatted in the user's number format once the field is left ("1234,5" → "1.234,50").
 * v-model: the text as typed/shown (parse it with `parseMoney`). Other attributes go to the
 * v-text-field (label, rules, error-messages…).
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { currencySymbol, parseMoney, toInputMoney } from '@/utils/money'

defineOptions({ inheritAttrs: false })
const model = defineModel<string>({ required: true })
const props = withDefaults(defineProps<{ currency?: string; places?: number }>(), {
  currency: 'BRL',
  places: 2,
})

const { locale } = useI18n()
const symbol = computed(() => currencySymbol(props.currency, locale.value))

function tidy() {
  const value = parseMoney(model.value, locale.value, props.places)
  if (value !== null) model.value = toInputMoney(value, locale.value, props.places)
}
</script>

<template>
  <v-text-field
    v-model="model"
    inputmode="decimal"
    class="money-field"
    v-bind="$attrs"
    @blur="tidy"
  >
    <!-- Always shown (a prefix only shows once there is a value) -->
    <template #prepend-inner
      ><span class="money-field__symbol" data-testid="money-symbol">{{ symbol }}</span></template
    >
  </v-text-field>
</template>

<style scoped>
.money-field :deep(input) {
  text-align: end;
  font-variant-numeric: tabular-nums;
}
.money-field__symbol {
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
  white-space: nowrap;
  margin-right: 4px;
}
</style>
