import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { i18n, setLanguage } from '@/i18n'
import * as journalApi from '@/journal'
import vuetify from '@/plugins/vuetify'
import { usePreferencesStore } from '@/stores/preferences'
import { settle } from '@/test-utils'
import HomeJournal from '../HomeJournal.vue'

vi.mock('@/journal', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/journal')>()),
  getJournal: vi.fn<typeof journalApi.getJournal>(),
}))
const api = vi.mocked(journalApi)

const JOURNAL: journalApi.Journal = {
  days: 7,
  since: '2026-11-21T10:00:00Z',
  events: [
    { key: 'business_entities.created', count: 3 },
    { key: 'efmv_analyses.created', count: 1 },
  ],
  version: '1.0.1',
  releases: [
    { version: '1.0.1', date: '2026-11-29', notes: ['Fixes.'] },
    { version: '1.0.0', date: '2026-11-28', notes: ['Business Entities.', 'Journal.'] },
  ],
}

function mountJournal() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:any(.*)*', component: { template: '<div />' }, name: 'any' }],
  })
  router.addRoute({
    path: '/entities',
    name: 'business-entities',
    component: { template: '<div />' },
  })
  router.addRoute({ path: '/efmv', name: 'efmv-analyses', component: { template: '<div />' } })
  return mount(HomeJournal, { global: { plugins: [vuetify, i18n, router] } })
}

describe('HomeJournal', () => {
  beforeEach(() => {
    setLanguage('en')
    setActivePinia(createPinia())
    api.getJournal.mockResolvedValue(JOURNAL)
  })
  afterEach(() => vi.clearAllMocks())

  it('the Data Journal first (counts, opening their modules), then the System Journal', async () => {
    const preferences = usePreferencesStore()
    preferences.uiState = { lastSeenRelease: '1.0.0' }
    const save = vi.spyOn(preferences, 'saveUiState').mockImplementation(() => {})
    const wrapper = mountJournal()
    await settle()
    const text = wrapper.text()
    expect(text.indexOf('Data Journal')).toBeLessThan(text.indexOf('System Journal'))
    expect(text).toContain('Last 7 days')
    const entities = wrapper.find('[data-testid="journal-event-business_entities.created"]')
    expect(entities.text()).toBe('3 new business entities')
    expect(entities.attributes('href')).toBe('/entities')
    expect(wrapper.find('[data-testid="journal-event-efmv_analyses.created"]').text()).toBe(
      'New eFMV analysis',
    )
    // Versions newer than the last one seen are "New"; the newest is now seen
    expect(wrapper.find('[data-testid="release-1.0.1"] [data-testid="release-new"]').exists()).toBe(
      true,
    )
    expect(wrapper.find('[data-testid="release-1.0.0"] [data-testid="release-new"]').exists()).toBe(
      false,
    )
    expect(save).toHaveBeenCalled()
    expect(save.mock.calls[0]![0]({})).toEqual({ lastSeenRelease: '1.0.1' })
    expect(wrapper.text()).toContain('Horizon 1.0.1')
    wrapper.unmount()
  })

  it('each part can be hidden; with both hidden nothing is asked for', async () => {
    const preferences = usePreferencesStore()
    preferences.showSystemJournal = false
    let wrapper = mountJournal()
    await settle()
    expect(wrapper.text()).toContain('Data Journal')
    expect(wrapper.text()).not.toContain('System Journal')
    wrapper.unmount()
    preferences.showDataJournal = false
    api.getJournal.mockClear()
    wrapper = mountJournal()
    await settle()
    expect(api.getJournal).not.toHaveBeenCalled()
    expect(wrapper.find('[data-testid="journal"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('the journals one under the other (default) or side by side', async () => {
    const preferences = usePreferencesStore()
    let wrapper = mountJournal()
    await settle()
    expect(wrapper.find('.journal--vertical').exists()).toBe(true)
    wrapper.unmount()
    preferences.journalLayout = 'horizontal'
    wrapper = mountJournal()
    await settle()
    expect(wrapper.find('.journal--horizontal').exists()).toBe(true)
    expect(wrapper.find('[data-testid="data-journal"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="system-journal"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('nothing in the period: says so', async () => {
    api.getJournal.mockResolvedValue({ ...JOURNAL, events: [], days: 1 })
    const wrapper = mountJournal()
    await settle()
    expect(wrapper.find('[data-testid="journal-empty"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Today')
    wrapper.unmount()
  })
})
