import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { i18n, setLanguage } from '@/i18n'
import vuetify from '@/plugins/vuetify'
import { inBody, settle } from '@/test-utils'
import * as efmvApi from '../api'
import EfmvAnalysesView from '../EfmvAnalysesView.vue'

vi.mock('../api', () => ({
  listEfmvAnalyses: vi.fn<typeof efmvApi.listEfmvAnalyses>(),
  deleteEfmvAnalysis: vi.fn<typeof efmvApi.deleteEfmvAnalysis>(),
  getEfmvAnalysis: vi.fn<typeof efmvApi.getEfmvAnalysis>(),
}))
const efmv = vi.mocked(efmvApi)

const ROW: efmvApi.EfmvAnalysisRow = {
  id: 3,
  code: 'EFMV-2026-0003',
  external_reference: 'OPP-661',
  account_manager_detail: { id: 10, full_name: 'Ana Lima' },
  customer_detail: { id: 20, name: 'Acme Ltda', trade_name: '', tax_id: '' },
  scenario_names: ['36 Months'],
  created_at: '2026-11-20T10:00:00Z',
  created_by_name: 'Fernando Almeida',
  updated_at: '2026-11-22T15:30:00Z',
  updated_by_name: 'Bruno Reis',
}

describe('EfmvAnalysesView', () => {
  beforeEach(() => setLanguage('en'))
  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('lists the latest updated first, with when and who updated them', async () => {
    efmv.listEfmvAnalyses.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [ROW],
    })
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', name: 'efmv-analyses-list', component: EfmvAnalysesView },
        { path: '/new', name: 'efmv-analysis-new', component: { render: () => null } },
        { path: '/:id', name: 'efmv-analysis', component: { render: () => null } },
      ],
    })
    await router.push('/')
    const wrapper = mount(EfmvAnalysesView, {
      attachTo: document.body,
      global: { plugins: [vuetify, i18n, pinia, router] },
    })
    await settle()
    expect(efmv.listEfmvAnalyses).toHaveBeenCalledWith(
      expect.objectContaining({ ordering: '-updated_at' }),
    )
    const titles = [...document.querySelectorAll('thead th')].map((th) => th.textContent!.trim())
    expect(titles).toContain('Last Update')
    expect(titles.some((title) => title.startsWith('Created'))).toBe(false)
    const cell = inBody('[data-testid="updated-at"]')!
    expect(cell.textContent).toMatch(/11\/22\/2026/)
    expect(cell.closest('td')!.textContent).toContain('Bruno Reis')
    expect(cell.getAttribute('title')).toMatch(/Created on 11\/20\/2026/)
    // The external reference under the code
    expect(inBody('[data-testid="external-reference"]')!.textContent).toContain('OPP-661')
    // The external reference under the code
    expect(inBody('[data-testid="external-reference"]')!.textContent).toContain('OPP-661')
    // Actions: the report of the row's analysis
    efmv.getEfmvAnalysis.mockReturnValue(new Promise(() => {}))
    ;(inBody('[data-testid="print"]') as HTMLButtonElement).click()
    await settle()
    expect(inBody('[data-testid="report-dialog"]')).not.toBeNull()
    expect(efmv.getEfmvAnalysis).toHaveBeenCalledWith(3)
    wrapper.unmount()
  })
})
