/** Global setup for Vitest (jsdom): browser APIs Vuetify needs that jsdom lacks. */

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver

// Used by Vuetify overlays (dialogs, menus) to position themselves
if (!('visualViewport' in globalThis)) {
  const viewport = Object.assign(new EventTarget(), {
    width: 1024,
    height: 768,
    offsetLeft: 0,
    offsetTop: 0,
    pageLeft: 0,
    pageTop: 0,
    scale: 1,
  })
  Object.defineProperty(globalThis, 'visualViewport', { value: viewport, configurable: true })
}
