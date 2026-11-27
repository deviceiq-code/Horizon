import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'

import { i18n, setLanguage } from '@/i18n'
import * as pricesApi from '@/modules/average-prices/api'
import { useNotificationsStore } from '@/stores/notifications'
import { dropdownOptions, inBody, mountWithPlugins, openDropdown, settle } from '@/test-utils'
import AveragePricePicker from '../AveragePricePicker.vue'

vi.mock('@/modules/average-prices/api', () => ({
  listAveragePrices: vi.fn<typeof pricesApi.listAveragePrices>(),
}))
// The form itself is tested with Average Prices: here only what it is given and what it saves
vi.mock('@/modules/average-prices/AveragePriceFormDialog.vue', () => ({
  default: defineComponent({
    name: 'AveragePriceFormDialog',
    props: ['modelValue', 'source', 'initialModel', 'scopeVertical', 'scopeSubVertical'],
    emits: ['update:modelValue', 'saved'],
    setup: (props) => () =>
      props.modelValue ? h('div', { 'data-testid': 'price-form' }, props.initialModel) : null,
  }),
}))

const prices = vi.mocked(pricesApi)
const page = <T>(results: T[]) => ({ count: results.length, next: null, previous: null, results })

beforeEach(() => {
  setActivePinia(createPinia())
  setLanguage('en')
  prices.listAveragePrices.mockResolvedValue(page([]))
})

afterEach(() => {
  document.body.innerHTML = ''
  vi.clearAllMocks()
})

describe('AveragePricePicker', () => {
  it('creates the asset not priced yet and picks the new price', async () => {
    const wrapper = mountWithPlugins({
      components: { AveragePricePicker },
      template:
        '<AveragePricePicker label="" :vertical="1" :sub-vertical="11" data-testid="picker" @pick="$emit(\'pick\', $event)" />',
    })
    await settle()
    const input = inBody('[data-testid="picker"] input:not([type="hidden"])') as HTMLInputElement
    input.value = 'P9999'
    input.dispatchEvent(new Event('input'))
    await new Promise((r) => setTimeout(r, 350))
    await settle()
    await openDropdown('picker')
    expect(prices.listAveragePrices).toHaveBeenLastCalledWith(
      expect.objectContaining({ search: 'P9999' }),
    )
    // Nothing found: "New Average Price" is offered (always, at the end of the list)
    expect(dropdownOptions()).toEqual(['No average prices found.', 'New Average Price'])
    expect(inBody('[data-testid="new-price"]')!.textContent).toContain('Price “P9999” now')

    inBody('[data-testid="new-price"]')!.click()
    await settle()
    const form = wrapper.findComponent({ name: 'AveragePriceFormDialog' })
    expect(form.props()).toMatchObject({
      modelValue: true,
      source: null,
      initialModel: 'P9999',
      scopeVertical: 1,
      scopeSubVertical: 11,
    })

    form.vm.$emit('saved', { id: 42, increasing_terms: [] }, 'created')
    await settle()
    const picker = wrapper.findComponent(AveragePricePicker)
    expect(picker.emitted('pick')).toEqual([[42]])
    expect(useNotificationsStore().text).toBe(i18n.global.t('averagePrices.created'))
  })
})
