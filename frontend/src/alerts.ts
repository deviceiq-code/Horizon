/**
 * Alerts (the inventory's notifications): how each kind looks, where it leads, and how the
 * Notifications page groups them (Today / Yesterday / Earlier) and tells their time.
 */

import type { RouteLocationRaw } from 'vue-router'
import type { Alert } from '@/modules/inventory/api'

export interface AlertLook {
  icon: string
  /** A theme color */
  color: string
}

/** The four kinds of notification, each with its icon and color */
export type AlertSeverity = 'info' | 'warning' | 'error' | 'success'

const LOOKS: Record<AlertSeverity, AlertLook> = {
  // An event happened (nothing wrong): "i" in a circle
  info: { icon: 'mdi-information-outline', color: 'info' },
  // Calls for attention: "!" in a triangle
  warning: { icon: 'mdi-alert-outline', color: 'warning' },
  // Something went wrong: "!" in a circle
  error: { icon: 'mdi-alert-circle-outline', color: 'error' },
  // A task or process finished well: a check in a circle
  success: { icon: 'mdi-check-circle-outline', color: 'success' },
}

type Translate = (key: string, params?: Record<string, unknown>) => string

/** The alert's message, translated (its status named in the UI language). */
export function alertText(alert: Pick<Alert, 'kind' | 'params'>, t: Translate): string {
  const params: Record<string, unknown> = { ...alert.params }
  if (typeof params.status === 'string') params.status = t(`inventory.statuses.${params.status}`)
  if (typeof params.environment === 'string') {
    params.environment = t(`environments.${params.environment}`)
  }
  return t(`inventory.alerts.kinds.${alert.kind}`, params)
}

/** Its short title ("Access Block Expired"); the kind's message when it has none. */
export function alertTitle(alert: Pick<Alert, 'kind'>, t: Translate, te: (key: string) => boolean) {
  const key = `notifications.titles.${alert.kind}`
  return te(key) ? t(key) : t('notifications.titles.other')
}

/** Icon and color of a notification, by its severity (unknown: information). */
export const alertLook = (severity: string | undefined): AlertLook =>
  LOOKS[severity as AlertSeverity] ?? LOOKS.info

/** The page an alert is about (its `ref`: "block:12", "transfer:3"…), null when none. */
export function alertTarget(
  alert: Pick<Alert, 'ref'> & Partial<Pick<Alert, 'params'>>,
): RouteLocationRaw | null {
  const [kind, id] = alert.ref.split(':')
  switch (kind) {
    // A user (e.g. who tried an environment not theirs): the users' grid searching for them
    case 'user':
      return { name: 'users', query: { search: String(alert.params?.username ?? '') } }
    case 'block':
      return { name: 'inventory-blocks' }
    case 'dispute':
      return { name: 'inventory-disputes' }
    case 'asset':
      return { name: 'inventory-assets' }
    case 'occurrence':
      return { name: 'inventory-occurrences' }
    case 'transfer':
      return id ? { name: 'inventory-transfer', params: { id } } : { name: 'inventory-transfers' }
    default:
      return null
  }
}

export type AlertGroup = 'today' | 'yesterday' | 'earlier'

const dayStart = (date: Date) => new Date(date.getFullYear(), date.getMonth(), date.getDate())

/** Groups in the order shown, each keeping the alerts' order; empty groups left out. */
export function groupByDay<T extends Pick<Alert, 'created_at'>>(
  alerts: T[],
  now = new Date(),
): { group: AlertGroup; alerts: T[] }[] {
  const today = dayStart(now).getTime()
  const yesterday = today - 24 * 60 * 60 * 1000
  const groups: Record<AlertGroup, T[]> = { today: [], yesterday: [], earlier: [] }
  for (const alert of alerts) {
    const day = dayStart(new Date(alert.created_at)).getTime()
    groups[day >= today ? 'today' : day >= yesterday ? 'yesterday' : 'earlier'].push(alert)
  }
  return (['today', 'yesterday', 'earlier'] as const)
    .filter((group) => groups[group].length)
    .map((group) => ({ group, alerts: groups[group] }))
}

/** "10 minutes ago", "2 hours ago", "yesterday", "5 days ago" — in the UI language. */
export function relativeTime(value: string | Date, locale: string, now = new Date()): string {
  const format = new Intl.RelativeTimeFormat(locale, { numeric: 'auto' })
  const seconds = Math.round((new Date(value).getTime() - now.getTime()) / 1000)
  const minutes = Math.round(seconds / 60)
  if (Math.abs(minutes) < 1) return format.format(0, 'minute')
  if (Math.abs(minutes) < 60) return format.format(minutes, 'minute')
  const hours = Math.round(minutes / 60)
  if (Math.abs(hours) < 24) return format.format(hours, 'hour')
  // By calendar days: anything from yesterday is "yesterday"
  const days = Math.round(
    (dayStart(new Date(value)).getTime() - dayStart(now).getTime()) / (24 * 60 * 60 * 1000),
  )
  if (Math.abs(days) < 30) return format.format(days, 'day')
  const months = Math.round(days / 30)
  if (Math.abs(months) < 12) return format.format(months, 'month')
  return format.format(Math.round(days / 365), 'year')
}
