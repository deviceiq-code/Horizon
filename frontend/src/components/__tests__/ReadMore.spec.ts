import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'
import { h, nextTick } from 'vue'

import { i18n, setLanguage } from '@/i18n'
import vuetify from '@/plugins/vuetify'
import ReadMore from '../ReadMore.vue'

function withHeight(height: number) {
  Object.defineProperty(HTMLElement.prototype, 'scrollHeight', {
    configurable: true,
    get: () => height,
  })
}

describe('ReadMore', () => {
  afterEach(() => {
    delete (HTMLElement.prototype as { scrollHeight?: number }).scrollHeight
  })

  it('cuts what goes past the reading height; Read More unfolds it, Read Less folds it', async () => {
    setLanguage('en')
    withHeight(900)
    const wrapper = mount(ReadMore, {
      props: { maxHeight: 300 },
      slots: { default: () => h('p', 'long text') },
      global: { plugins: [vuetify, i18n] },
    })
    await nextTick()
    await nextTick()
    const content = wrapper.find('[data-testid="read-more-content"]')
    expect(content.attributes('style')).toContain('max-height: 300px')
    expect(content.classes()).toContain('read-more__content--cut')
    await wrapper.find('[data-testid="read-more"]').trigger('click')
    expect(content.attributes('style') ?? '').not.toContain('max-height')
    expect(wrapper.emitted('expand')).toHaveLength(1)
    expect(wrapper.find('[data-testid="read-more"]').text()).toBe('Read Less')
  })

  it('short content: no button', async () => {
    withHeight(100)
    const wrapper = mount(ReadMore, {
      slots: { default: () => h('p', 'short') },
      global: { plugins: [vuetify, i18n] },
    })
    await nextTick()
    await nextTick()
    expect(wrapper.find('[data-testid="read-more"]').exists()).toBe(false)
  })
})
