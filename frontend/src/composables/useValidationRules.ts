import { useI18n } from 'vue-i18n'

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

  return { required, email, maxLength }
}
