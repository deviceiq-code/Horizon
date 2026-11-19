import { useI18n } from 'vue-i18n'
import { isDecimalInRange } from '@/utils/decimal'

type Rule = (value: string | null | undefined) => true | string

/**
 * Translated validation rules for Vuetify fields (:rules="[rules.required, rules.email]").
 * They only guide the user; the backend validates everything again.
 */
export function useValidationRules() {
  const { t } = useI18n()

  const required: Rule = (v) => !!v?.trim() || t('validation.required')

  /** Empty is accepted — combine with `required` when the field is mandatory. */
  const email: Rule = (v) =>
    !v?.trim() || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.trim()) || t('validation.email')

  const maxLength =
    (max: number): Rule =>
    (v) =>
      (v ?? '').length <= max || t('validation.maxLength', { max })

  /** Number from min to max with at most `places` decimals. Empty is accepted (use required). */
  const decimalRange =
    (min: number, max: number, places: number): Rule =>
    (v) =>
      !String(v ?? '').trim() ||
      isDecimalInRange(String(v), min, max, places) ||
      t('validation.decimalRange', { min, max, places })

  return { required, email, maxLength, decimalRange }
}
