import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api'
import { setLanguage } from '@/i18n'
import { usePreferencesStore } from '@/stores/preferences'
import { inBody, mountWithPlugins, settle } from '@/test-utils'
import * as inventoryApi from '../api'
import MovementView from '../MovementView.vue'

vi.mock('../api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api')>()),
  lookupCode: vi.fn<typeof inventoryApi.lookupCode>(),
  moveByCodes: vi.fn<typeof inventoryApi.moveByCodes>(),
  myLatestMovements: vi.fn<typeof inventoryApi.myLatestMovements>(),
}))

const api = vi.mocked(inventoryApi)

const ASSET = {
  id: 1,
  horizon_id: 'H000012344',
  asset_model_detail: {
    id: 3,
    name: 'Latitude 5440',
    manufacturer_name: 'Dell',
    asset_class: 2,
    asset_class_name: 'Notebook',
    asset_class_icon: 'mdi-laptop',
    tracking: 'unit',
    has_storage: true,
  },
  serial: 'ABC1234',
  status: 'available',
  held_for_dispute: false,
  current_location_detail: { id: 9, code: 'SP01-EST', area_type: 'stock' },
  current_container_detail: null,
} as unknown as inventoryApi.Asset

/** A barcode gun types the code and presses Enter. */
async function scan(text: string) {
  const input = inBody('[data-testid="scan"] input') as HTMLInputElement
  input.value = text
  input.dispatchEvent(new Event('input'))
  await settle()
  input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
  await settle()
}

const feedback = () => inBody('[data-testid="feedback"]')?.textContent ?? ''

describe('MovementView', () => {
  beforeEach(() => {
    setLanguage('en')
    setActivePinia(createPinia())
    api.myLatestMovements.mockResolvedValue({ count: 0, next: null, previous: null, results: [] })
  })

  afterEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('reads the asset, then the destination, and moves it', async () => {
    api.lookupCode.mockResolvedValue({ kind: 'asset', item: ASSET })
    api.moveByCodes.mockResolvedValue({
      id: 7,
      kind: 'relocation',
      asset_code: 'H000012344',
      from_location_code: 'SP01-EST',
      to_location_code: 'SP01-EST-A1',
      from_container_code: null,
      to_container_code: null,
      at: '2026-11-23T10:00:00Z',
    } as inventoryApi.MovementEvent)
    const wrapper = mountWithPlugins(MovementView)
    await settle()

    await scan('h000012344')
    expect(api.lookupCode).toHaveBeenCalledWith('H000012344')
    expect(inBody('[data-testid="target"]')!.textContent).toContain('Dell Latitude 5440')
    expect(feedback()).toContain('Now read the destination')

    await scan('sp01-est-a1')
    expect(api.moveByCodes).toHaveBeenCalledWith('H000012344', 'SP01-EST-A1', '', '')
    expect(feedback()).toContain('H000012344 moved to SP01-EST-A1')
    // Ready for the next one; the move is listed
    expect(inBody('[data-testid="target"]')).toBeNull()
    expect(inBody('[data-testid="latest"]')!.textContent).toContain('SP01-EST → SP01-EST-A1')
    wrapper.unmount()
  })

  it('catches a wrong check digit before asking the server', async () => {
    const wrapper = mountWithPlugins(MovementView)
    await settle()
    await scan('H000012345')
    expect(api.lookupCode).not.toHaveBeenCalled()
    expect(feedback()).toContain('Wrong check digit')
    wrapper.unmount()
  })

  it('a location is not something to move', async () => {
    const wrapper = mountWithPlugins(MovementView)
    await settle()
    await scan('SP01-EST')
    expect(api.lookupCode).not.toHaveBeenCalled()
    expect(feedback()).toContain('read the asset or container first')
    wrapper.unmount()
  })

  it('shows the server refusal and keeps the asset to read another destination', async () => {
    api.lookupCode.mockResolvedValue({ kind: 'asset', item: ASSET })
    api.moveByCodes.mockRejectedValue(
      new ApiError(400, 'A Dock area does not take assets that are Available.', {
        detail: 'A Dock area does not take assets that are Available.',
        field: 'destination',
      }),
    )
    const wrapper = mountWithPlugins(MovementView)
    await settle()
    await scan('H000012344')
    await scan('SP01-DOC')
    expect(feedback()).toContain('does not take assets')
    expect(inBody('[data-testid="target"]')).not.toBeNull()
    wrapper.unmount()
  })

  it('with "Read Origin", a different recorded location is warned about (RN-19)', async () => {
    usePreferencesStore().uiState = { readOrigin: true }
    api.lookupCode.mockResolvedValue({ kind: 'asset', item: ASSET })
    api.moveByCodes.mockResolvedValue({
      id: 8,
      kind: 'relocation',
      asset_code: 'H000012344',
      from_location_code: 'SP01-EST',
      to_location_code: 'SP01-EST-A1',
      from_container_code: null,
      to_container_code: null,
      at: '2026-11-24T10:00:00Z',
      location_mismatch: 'H000012344 was read at SP01-DOC; the records said SP01-EST.',
    } as inventoryApi.MovementEvent & { location_mismatch: string })
    const wrapper = mountWithPlugins(MovementView)
    await settle()
    await scan('h000012344')
    expect(feedback()).toContain('Read the location where the object is first')
    await scan('sp01-doc')
    await scan('h000012344')
    await scan('sp01-est-a1')
    expect(api.moveByCodes).toHaveBeenCalledWith('H000012344', 'SP01-EST-A1', '', 'SP01-DOC')
    expect(feedback()).toContain('Location divergence registered')
    wrapper.unmount()
  })
})
