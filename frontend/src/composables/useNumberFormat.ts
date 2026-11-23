import { useI18n } from 'vue-i18n'
import { formatNumber, type NumberKey } from '@/numberFormat'

/** Numbers in the user's number format (Settings): `n(value, 'decimal')`, as vue-i18n's `n`. */
export function useNumberFormat() {
  const { locale } = useI18n()
  return { n: (value: number, key?: NumberKey) => formatNumber(value, key, locale.value) }
}
