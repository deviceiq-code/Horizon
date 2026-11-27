import { describe, expect, it } from 'vitest'

import { alertLook, alertTarget, alertText, groupByDay, relativeTime } from '@/alerts'
import { i18n, setLanguage } from '@/i18n'

const NOW = new Date(2026, 10, 26, 15, 0) // 26 Nov 2026, 15:00 local
const at = (day: number, hour = 9, minute = 0) =>
  new Date(2026, 10, day, hour, minute).toISOString()

describe('alerts', () => {
  it('groups by day: Today, Yesterday, Earlier (empty groups left out), keeping the order', () => {
    const alerts = [
      { id: 1, created_at: at(26, 14) },
      { id: 2, created_at: at(26, 0, 5) },
      { id: 3, created_at: at(25, 23) },
      { id: 4, created_at: at(20) },
    ]
    expect(groupByDay(alerts, NOW).map((g) => [g.group, g.alerts.map((a) => a.id)])).toEqual([
      ['today', [1, 2]],
      ['yesterday', [3]],
      ['earlier', [4]],
    ])
    expect(groupByDay([{ id: 4, created_at: at(1) }], NOW).map((g) => g.group)).toEqual(['earlier'])
    expect(groupByDay([], NOW)).toEqual([])
  })

  it('tells how long ago, in the UI language', () => {
    expect(relativeTime(at(26, 14, 59), 'en', NOW)).toBe('1 minute ago')
    expect(relativeTime(at(26, 14, 50), 'en', NOW)).toBe('10 minutes ago')
    expect(relativeTime(at(26, 13), 'en', NOW)).toBe('2 hours ago')
    expect(relativeTime(NOW, 'en', NOW)).toBe('this minute')
    // By calendar day: anything from yesterday is "yesterday"
    expect(relativeTime(at(25, 9), 'en', NOW)).toBe('yesterday')
    expect(relativeTime(at(21), 'en', NOW)).toBe('5 days ago')
    expect(relativeTime(at(21), 'pt-br', NOW)).toBe('há 5 dias')
    expect(relativeTime(new Date(2026, 7, 26).toISOString(), 'en', NOW)).toBe('3 months ago')
  })

  it('leads to the page each alert is about', () => {
    expect(alertTarget({ ref: 'block:12' })).toEqual({ name: 'inventory-blocks' })
    expect(alertTarget({ ref: 'dispute:3' })).toEqual({ name: 'inventory-disputes' })
    expect(alertTarget({ ref: 'asset:40' })).toEqual({ name: 'inventory-assets' })
    expect(alertTarget({ ref: 'occurrence:5' })).toEqual({ name: 'inventory-occurrences' })
    expect(alertTarget({ ref: 'transfer:7' })).toEqual({
      name: 'inventory-transfer',
      params: { id: '7' },
    })
    expect(alertTarget({ ref: 'user:4', params: { username: 'bia' } })).toEqual({
      name: 'users',
      query: { search: 'bia' },
    })
    expect(alertTarget({ ref: '' })).toBeNull()
  })

  it('four kinds of notification, each with its icon and color', () => {
    expect(alertLook('info')).toEqual({ icon: 'mdi-information-outline', color: 'info' })
    expect(alertLook('warning')).toEqual({ icon: 'mdi-alert-outline', color: 'warning' })
    expect(alertLook('error')).toEqual({ icon: 'mdi-alert-circle-outline', color: 'error' })
    expect(alertLook('success')).toEqual({ icon: 'mdi-check-circle-outline', color: 'success' })
    // Unknown (e.g. a newer server): information
    expect(alertLook('other')).toEqual(alertLook('info'))
  })

  it('sign-ins that failed: the environment named in the UI language', () => {
    setLanguage('en')
    const t = (key: string, params?: Record<string, unknown>) => i18n.global.t(key, params ?? {})
    expect(
      alertText(
        {
          kind: 'login_failed',
          params: { username: 'dora', environment: 'development', address: '10.0.0.7' },
        },
        t,
      ),
    ).toBe('Failed sign-in as dora in Development (Test) (from 10.0.0.7).')
  })
})
