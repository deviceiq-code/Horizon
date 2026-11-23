/**
 * A short sound after each reading: high for success, low for an error — the operator looks at
 * the item, not at the screen. Silent where the browser has no Web Audio (and in tests).
 */
let context: AudioContext | null = null

export function beep(ok: boolean): void {
  const Audio = (globalThis as { AudioContext?: typeof AudioContext }).AudioContext
  if (!Audio) return
  try {
    context ??= new Audio()
    const oscillator = context.createOscillator()
    const gain = context.createGain()
    oscillator.type = 'square'
    oscillator.frequency.value = ok ? 1320 : 220
    gain.gain.value = 0.08
    oscillator.connect(gain).connect(context.destination)
    const now = context.currentTime
    oscillator.start(now)
    oscillator.stop(now + (ok ? 0.08 : 0.35))
  } catch {
    // No sound is no problem
  }
}
