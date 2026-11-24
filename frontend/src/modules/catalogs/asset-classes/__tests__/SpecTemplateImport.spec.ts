import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { i18n, setLanguage } from '@/i18n'
import vuetify from '@/plugins/vuetify'
import { dropdownOptions, inBody, openDropdown, settle, typeInto } from '@/test-utils'
import * as assetClassesApi from '../api'
import SpecTemplateDialog from '../SpecTemplateDialog.vue'

vi.mock('../api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api')>()),
  getSpecTemplate: vi.fn<typeof assetClassesApi.getSpecTemplate>(),
  listAssetClasses: vi.fn<typeof assetClassesApi.listAssetClasses>(),
}))

const api = vi.mocked(assetClassesApi)

describe('importing a template from another asset class', () => {
  beforeEach(() => {
    setLanguage('en')
    setActivePinia(createPinia())
    api.getSpecTemplate.mockResolvedValue({ fields: [] } as never)
    api.listAssetClasses.mockResolvedValue({ count: 0, next: null, previous: null, results: [] })
  })
  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('looks in the same vertical first, or in any vertical', async () => {
    const wrapper = mount(SpecTemplateDialog, {
      props: { modelValue: false, assetClassId: 5, label: 'Excavators', verticalId: 2 },
      attachTo: document.body,
      global: { plugins: [vuetify, i18n] },
    })
    await wrapper.setProps({ modelValue: true })
    await settle()
    ;(inBody('[data-testid="spec-import"]') as HTMLButtonElement).click()
    await settle()
    expect(api.listAssetClasses).toHaveBeenLastCalledWith(
      expect.objectContaining({ filters: { vertical: 2 } }),
    )
    ;(inBody('[data-testid="import-scope-any"]') as HTMLButtonElement).click()
    await settle()
    expect(api.listAssetClasses).toHaveBeenLastCalledWith(expect.objectContaining({ filters: {} }))
    wrapper.unmount()
  })

  it('finds the asset class by typing its name or vertical', async () => {
    const make = (id: number, name: string, label: string) =>
      ({
        id,
        name,
        sub_vertical_detail: { label },
        spec_template: [
          { key: 'k', label: 'Weight', kind: 'number', unit: 'kg', required: false, options: [] },
        ],
      }) as unknown as assetClassesApi.AssetClass
    api.listAssetClasses.mockResolvedValue({
      count: 3,
      next: null,
      previous: null,
      results: [
        make(1, 'Excavators', 'Industry / Yellow line'),
        make(2, 'Notebooks', 'IT / General'),
        make(3, 'Forklifts', 'Industry / Logistics'),
      ],
    })
    const wrapper = mount(SpecTemplateDialog, {
      props: { modelValue: false, assetClassId: 9, label: 'Loaders', verticalId: 2 },
      attachTo: document.body,
      global: { plugins: [vuetify, i18n] },
    })
    await wrapper.setProps({ modelValue: true })
    await settle()
    ;(inBody('[data-testid="spec-import"]') as HTMLButtonElement).click()
    await settle()
    await openDropdown('import-source')
    await typeInto('import-source', 'note')
    expect(dropdownOptions()).toEqual(['Notebooks'])
    await typeInto('import-source', 'industry')
    expect(dropdownOptions()).toEqual(['Excavators', 'Forklifts'])
    wrapper.unmount()
  })
})
