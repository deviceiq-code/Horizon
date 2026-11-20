import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, ref } from 'vue'

import { ApiError } from '@/api'
import { setLanguage } from '@/i18n'
import { click, inBody, mountWithPlugins, settle } from '@/test-utils'
import * as assetClassesApi from '../asset-classes/api'
import SpecTemplateDialog from '../asset-classes/SpecTemplateDialog.vue'

vi.mock('../asset-classes/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../asset-classes/api')>()),
  getSpecTemplate: vi.fn<typeof assetClassesApi.getSpecTemplate>(),
  saveSpecTemplate: vi.fn<typeof assetClassesApi.saveSpecTemplate>(),
}))

const api = vi.mocked(assetClassesApi)

const HOURS: assetClassesApi.SpecField = {
  key: 'hours',
  label: 'Operating hours',
  kind: 'number',
  unit: 'h',
  required: true,
  options: [],
}

function mountDialog() {
  const open = ref(false)
  const Host = defineComponent(
    () => () =>
      h(SpecTemplateDialog, {
        modelValue: open.value,
        'onUpdate:modelValue': (v: boolean) => (open.value = v),
        assetClassId: 11,
        label: 'Excavators — Industry / Yellow line',
      }),
  )
  const wrapper = mountWithPlugins(Host)
  return { wrapper, open }
}

async function setField(row: number, testId: string, value: string) {
  const input = inBody(
    `[data-testid="spec-field-${row}"] [data-testid="${testId}"] input`,
  ) as HTMLInputElement
  input.value = value
  input.dispatchEvent(new Event('input'))
  await settle()
}

describe('SpecTemplateDialog', () => {
  beforeEach(() => {
    setLanguage('en')
    setActivePinia(createPinia())
    api.getSpecTemplate.mockResolvedValue({ fields: [HOURS] })
  })

  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('loads the template and saves it with a new field', async () => {
    api.saveSpecTemplate.mockResolvedValue({ fields: [] })
    const { wrapper, open } = mountDialog()
    open.value = true
    await settle()

    expect(api.getSpecTemplate).toHaveBeenCalledWith(11)
    await click('spec-add')
    await setField(1, 'spec-label', 'Undercarriage')
    await click('save')

    expect(api.saveSpecTemplate).toHaveBeenCalledWith(11, [
      HOURS,
      { key: '', label: 'Undercarriage', kind: 'text', unit: '', required: false, options: [] },
    ])
    expect(open.value).toBe(false)
    wrapper.unmount()
  })

  it('a field can be a number and removed', async () => {
    api.saveSpecTemplate.mockResolvedValue({ fields: [] })
    const { wrapper, open } = mountDialog()
    open.value = true
    await settle()

    await click('spec-add')
    await setField(1, 'spec-label', 'Weight')
    // Choose "Number" in the new row's type select
    inBody('[data-testid="spec-field-1"] [data-testid="spec-kind"] .v-field')!.dispatchEvent(
      new MouseEvent('mousedown', { bubbles: true }),
    )
    await settle()
    const number = [
      ...document.body.querySelectorAll<HTMLElement>('.v-overlay--active .v-list-item'),
    ].find((el) => el.textContent?.trim() === 'Number')!
    number.click()
    await settle()
    // The unit shows for numbers only
    await setField(1, 'spec-unit', 'kg')
    // Remove the first field
    inBody('[data-testid="spec-field-0"] [data-testid="spec-remove"]')!.click()
    await settle()
    await click('save')

    expect(api.saveSpecTemplate).toHaveBeenCalledWith(11, [
      { key: '', label: 'Weight', kind: 'number', unit: 'kg', required: false, options: [] },
    ])
    wrapper.unmount()
  })

  it('requires a name for every field', async () => {
    const { wrapper, open } = mountDialog()
    open.value = true
    await settle()

    await click('spec-add')
    await click('save')

    expect(api.saveSpecTemplate).not.toHaveBeenCalled()
    expect(inBody('[data-testid="spec-field-1"]')!.textContent).toContain('This field is required.')
    wrapper.unmount()
  })

  it('shows server errors on the row that failed', async () => {
    api.saveSpecTemplate.mockRejectedValue(
      new ApiError(400, 'Bad Request', {
        fields: { '1': ['Field names must be unique within the template.'] },
      }),
    )
    const { wrapper, open } = mountDialog()
    open.value = true
    await settle()

    await click('spec-add')
    await setField(1, 'spec-label', 'operating hours')
    await click('save')

    expect(inBody('[data-testid="spec-field-1"]')!.textContent).toContain(
      'Field names must be unique within the template.',
    )
    wrapper.unmount()
  })

  it('a list field gets its items (case kept, no repeats); only numbers have a unit', async () => {
    api.saveSpecTemplate.mockResolvedValue({ fields: [] })
    const { wrapper, open } = mountDialog()
    open.value = true
    await settle()

    await click('spec-add')
    await setField(1, 'spec-label', 'Fuel')
    inBody('[data-testid="spec-field-1"] [data-testid="spec-kind"] .v-field')!.dispatchEvent(
      new MouseEvent('mousedown', { bubbles: true }),
    )
    await settle()
    const kinds = [
      ...document.body.querySelectorAll<HTMLElement>('.v-overlay--active .v-list-item'),
    ]
    expect(kinds.map((el) => el.textContent?.trim())).toEqual([
      'Text',
      'Number',
      'Yes / No',
      'List',
      'Rating (stars)',
    ])
    kinds.find((el) => el.textContent?.trim() === 'List')!.click()
    await settle()
    expect(inBody('[data-testid="spec-field-1"] [data-testid="spec-unit"]')).toBeNull()

    const input = inBody(
      '[data-testid="spec-field-1"] [data-testid="list-input"] input',
    ) as HTMLInputElement
    input.value = 'Diesel, Electric'
    input.dispatchEvent(new Event('input'))
    await settle()
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
    await settle()
    input.value = 'diesel'
    input.dispatchEvent(new Event('input'))
    await settle()
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
    await settle()
    await click('save')

    expect(api.saveSpecTemplate).toHaveBeenCalledWith(11, [
      HOURS,
      {
        key: '',
        label: 'Fuel',
        kind: 'choice',
        unit: '',
        required: false,
        options: ['Diesel', 'Electric'],
      },
    ])
    wrapper.unmount()
  })
})
