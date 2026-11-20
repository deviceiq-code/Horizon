import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { h, reactive } from 'vue'

import { i18n, setLanguage } from '@/i18n'
import type { SpecField } from '@/modules/catalogs/asset-classes/api'
import { inBody, mountWithPlugins, pickOption, settle } from '@/test-utils'
import SpecValuesInput from '../SpecValuesInput.vue'
import { specText } from '../specText'

const field = (key: string, kind: SpecField['kind'], extra: Partial<SpecField> = {}) => ({
  key,
  label: key,
  kind,
  unit: '',
  required: false,
  options: [],
  ...extra,
})

const TEMPLATE: SpecField[] = [
  field('cab', 'boolean'),
  field('fuel', 'choice', { options: ['Diesel', 'Electric'] }),
  field('condition', 'rating'),
]

function mountInput() {
  const values = reactive<Record<string, string>>({})
  const wrapper = mountWithPlugins({
    render: () =>
      h(SpecValuesInput, {
        modelValue: values,
        'onUpdate:modelValue': (v: Record<string, string>) => Object.assign(values, v),
        template: TEMPLATE,
        assetClassId: 5,
      }),
  })
  return { wrapper, values }
}

/** Star labels go 0, 0.5, 1 … 5 (index = stars × 2). */
async function rate(key: string, stars: number) {
  inBody(`[data-testid="spec-${key}"] [data-testid="stars"]`)!
    .querySelectorAll<HTMLElement>('label')
    [stars * 2]!.click()
  await settle()
}

describe('SpecValuesInput', () => {
  beforeEach(() => {
    setLanguage('en')
    setActivePinia(createPinia())
  })
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('answers yes/no, picks a list item and rates with stars', async () => {
    const { wrapper, values } = mountInput()
    await settle()

    inBody('[data-testid="spec-cab"] [data-testid="answer-yes"]')!.click()
    await settle()
    expect(values.cab).toBe('true')
    inBody('[data-testid="spec-cab"] [data-testid="answer-no"]')!.click()
    await settle()
    expect(values.cab).toBe('false')
    // Clicking the chosen answer again clears it
    inBody('[data-testid="spec-cab"] [data-testid="answer-no"]')!.click()
    await settle()
    expect(values.cab).toBe('')

    await pickOption('spec-fuel', 'Electric')
    expect(values.fuel).toBe('Electric')

    await rate('condition', 3.5)
    expect(values.condition).toBe('3.5')
    await rate('condition', 0)
    expect(values.condition).toBe('') // 0 stars = not rated
    wrapper.unmount()
  })
})

describe('specText', () => {
  const t = (key: string) => i18n.global.t(key)
  const n = (value: number, format: string) => i18n.global.n(value, format)

  it('shows each kind as people read it', () => {
    setLanguage('en')
    const spec = (kind: SpecField['kind'], value: string, unit = '') => ({
      ...field('x', kind, { unit }),
      value,
    })
    expect(specText(spec('boolean', 'true'), t, n)).toBe('Yes')
    expect(specText(spec('boolean', 'false'), t, n)).toBe('No')
    expect(specText(spec('rating', '3.5'), t, n)).toBe('★ 3.5 / 5')
    expect(specText(spec('number', '2500', 'h'), t, n)).toBe('2500 h')
    expect(specText(spec('choice', 'Diesel'), t, n)).toBe('Diesel')
    expect(specText(spec('text', ''), t, n)).toBe('—')
  })
})
