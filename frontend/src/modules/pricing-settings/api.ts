import { api } from '@/api'

/**
 * Pricing control panel. How a value typed in an analysis is placed against Average Prices
 * (percentages of its value; decimal strings): up to `compatible_percent` away = compatible;
 * `below_percent` / `above_percent` or more = below / above the historical value; in between =
 * slightly below / above. And how long an average price stays current.
 */
export interface PricingSettings {
  compatible_percent: string
  below_percent: string
  above_percent: string
  validity_months: number
  /** Expired average prices can still be added to analyses (they are flagged) */
  accept_expired: boolean
  /** The disclaimer closing an eFMV analysis's printed report, per language code; may use
   * {code}, {external_reference}, {customer}, {account_manager} and {date} */
  report_disclaimer: Record<string, string>
  /** The texts "Restore Default" brings back (read-only) */
  report_disclaimer_defaults: Record<string, string>
  updated_at: string
  updated_by_name: string | null
}

export type PricingSettingsInput = Omit<
  PricingSettings,
  'updated_at' | 'updated_by_name' | 'report_disclaimer_defaults'
>

const URL = '/pricing/settings/'

export function getPricingSettings() {
  return api<PricingSettings>(URL)
}

/** Administrators only. Errors per field, e.g. {"below_percent": [...]} */
export function updatePricingSettings(data: Partial<PricingSettingsInput>) {
  return api<PricingSettings>(URL, { method: 'PATCH', body: JSON.stringify(data) })
}
