/**
 * `d(value, 'short' | 'dateTime')` as vue-i18n's, but in the formats the user chose in
 * Settings (src/dateFormat.ts). Use it instead of vue-i18n's `d` / `$d` for dates.
 */
import { useI18n } from 'vue-i18n'
import { formatDate, type DateKind } from '@/dateFormat'
import { usePreferencesStore } from '@/stores/preferences'

export function useDateFormat() {
  const { locale } = useI18n()
  const preferences = usePreferencesStore()
  const d = (value: Date, kind: DateKind) =>
    formatDate(value, kind, locale.value, preferences.dateFormat, preferences.timeFormat)
  return { d }
}
