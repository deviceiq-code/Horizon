import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { dropdownOptions, mountWithPlugins, pickOption, settle, typeInto } from '@/test-utils'
import * as pricesApi from '../api'
import SpecSuggestField from '../SpecSuggestField.vue'

vi.mock('../api', () => ({ getSpecSuggestions: vi.fn<typeof pricesApi.getSpecSuggestions>() }))
const api = vi.mocked(pricesApi)

const debounce = async () => {
  await new Promise((r) => setTimeout(r, 300))
  await settle()
}

function mountField() {
  const value = ref('')
  const Host = defineComponent(
    () => () =>
      h(SpecSuggestField, {
        modelValue: value.value,
        'onUpdate:modelValue': (v: string) => (value.value = v),
        assetClassId: 5,
        fieldKey: 'cpu',
        'data-testid': 'cpu',
      }),
  )
  return { wrapper: mountWithPlugins(Host), value }
}

describe('SpecSuggestField', () => {
  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('offers values already used while typing and fills in the one picked', async () => {
    api.getSpecSuggestions.mockResolvedValue(['Intel Core Ultra 7 155H', 'Intel Core Ultra 5'])
    const { wrapper, value } = mountField()
    await settle()

    await typeInto('cpu', 'ultra')
    await debounce()
    expect(api.getSpecSuggestions).toHaveBeenLastCalledWith(5, 'cpu', 'ultra')
    await pickOption('cpu', 'Intel Core Ultra 7 155H')
    expect(value.value).toBe('Intel Core Ultra 7 155H')
    wrapper.unmount()
  })

  it('keeps a new value typed (not among the suggestions)', async () => {
    api.getSpecSuggestions.mockResolvedValue([])
    const { wrapper, value } = mountField()
    await settle()

    await typeInto('cpu', 'Apple M4')
    await debounce()
    expect(value.value).toBe('Apple M4')
    expect(dropdownOptions()).toEqual([])
    wrapper.unmount()
  })
})
