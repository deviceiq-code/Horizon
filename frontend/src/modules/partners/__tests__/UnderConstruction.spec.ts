import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { i18n, setLanguage } from '@/i18n'
import vuetify from '@/plugins/vuetify'
import UnderConstruction from '../UnderConstruction.vue'

describe('Services and Partnerships (skeleton)', () => {
  it('a page says what it is for and what is planned', () => {
    setLanguage('pt-br')
    const wrapper = mount(UnderConstruction, {
      props: { page: 'services', icon: 'mdi-toolbox-outline' },
      global: { plugins: [vuetify, i18n] },
    })
    expect(wrapper.find('h1').text()).toBe('Serviços')
    expect(wrapper.text()).toContain('Em Construção')
    expect(wrapper.findAll('[data-testid="planned"] .v-list-item')).toHaveLength(3)
    setLanguage('en')
  })
})
