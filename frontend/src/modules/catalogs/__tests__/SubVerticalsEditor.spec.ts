import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { defineComponent, h, ref } from 'vue'

import { setLanguage } from '@/i18n'
import { mountWithPlugins, settle } from '@/test-utils'
import type { SubVertical } from '../verticals/api'
import SubVerticalsEditor from '../verticals/SubVerticalsEditor.vue'

const GENERAL: SubVertical = {
  id: 1,
  name: '',
  is_general: true,
  risk: 'medium',
  allowed_terms: [12, 24, 36, 48, 60],
  recommended_term: 36,
}

function mountEditor(terms = GENERAL.allowed_terms, recommended = GENERAL.recommended_term) {
  const items = ref<SubVertical[]>([
    { ...GENERAL, allowed_terms: [...terms], recommended_term: recommended },
  ])
  const Host = defineComponent(
    () => () =>
      h(SubVerticalsEditor, {
        modelValue: items.value,
        'onUpdate:modelValue': (v: SubVertical[]) => (items.value = v),
        maxTerm: 360,
        rowErrors: {},
        listErrors: [],
      }),
  )
  const wrapper = mountWithPlugins(Host)
  const terms_ = () => items.value[0]!.allowed_terms
  const chips = () => wrapper.findAll('[data-testid="term-chip"]').map((c) => c.text())
  return { wrapper, items, terms: terms_, chips }
}

async function startAdding(wrapper: ReturnType<typeof mountWithPlugins>) {
  await wrapper.find('[data-testid="term-add"]').trigger('click')
  await settle()
  return wrapper.find('[data-testid="term-input"] input')
}

describe('SubVerticalsEditor — allowed terms', () => {
  beforeEach(() => setLanguage('en'))
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('shows every term as a chip, without any dropdown', async () => {
    const { wrapper, chips } = mountEditor()
    await settle()

    expect(chips()).toEqual(['12', '24', '36', '48', '60'])
    expect(wrapper.find('.v-combobox').exists()).toBe(false)
    expect(wrapper.find('[data-testid="term-input"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('removing one chip removes only that term', async () => {
    const { wrapper, terms, items } = mountEditor()
    await settle()

    await wrapper.findAll('[data-testid="term-chip"]')[1]!.find('.v-chip__close').trigger('click')
    await settle()

    expect(terms()).toEqual([12, 36, 48, 60])
    expect(items.value[0]!.recommended_term).toBe(36)
    wrapper.unmount()
  })

  it('"Add term" opens an input; Enter adds the typed months in order', async () => {
    const { wrapper, terms, chips } = mountEditor()
    await settle()

    const input = await startAdding(wrapper)
    expect(input.exists()).toBe(true)
    await input.setValue('18')
    await input.trigger('keydown', { key: 'Enter' })
    await settle()

    expect(terms()).toEqual([12, 18, 24, 36, 48, 60])
    expect(chips()).toContain('18')
    // The input closes and the button is back, ready for the next one
    expect(wrapper.find('[data-testid="term-input"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="term-add"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('leaving the input also adds the typed term', async () => {
    const { wrapper, terms } = mountEditor([12])
    await settle()

    const input = await startAdding(wrapper)
    await input.setValue('30')
    await input.trigger('blur')
    await settle()

    expect(terms()).toEqual([12, 30])
    wrapper.unmount()
  })

  it('Esc cancels without adding', async () => {
    const { wrapper, terms } = mountEditor()
    await settle()

    const input = await startAdding(wrapper)
    await input.setValue('18')
    await input.trigger('keydown', { key: 'Escape' })
    await settle()

    expect(terms()).toEqual([12, 24, 36, 48, 60])
    expect(wrapper.find('[data-testid="term-input"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it.each([
    ['24', 'This term is already in the list.'],
    ['0', 'Enter a whole number of months from 1 to 360.'],
    ['400', 'Enter a whole number of months from 1 to 360.'],
    ['12.5', 'Enter a whole number of months from 1 to 360.'],
  ])('typing %j shows a message and adds nothing', async (typed, message) => {
    const { wrapper, terms } = mountEditor()
    await settle()

    const input = await startAdding(wrapper)
    await input.setValue(typed)
    await input.trigger('keydown', { key: 'Enter' })
    await settle()

    expect(terms()).toEqual([12, 24, 36, 48, 60])
    expect(wrapper.text()).toContain(message)
    expect(wrapper.find('[data-testid="term-input"]').exists()).toBe(true) // still open to fix
    wrapper.unmount()
  })

  it('removing the recommended term clears it when several terms remain', async () => {
    const { wrapper, items } = mountEditor([12, 24, 36], 36)
    await settle()

    await wrapper.findAll('[data-testid="term-chip"]')[2]!.find('.v-chip__close').trigger('click')
    await settle()

    expect(items.value[0]!.allowed_terms).toEqual([12, 24])
    expect(items.value[0]!.recommended_term).toBeNull()
    wrapper.unmount()
  })
})
