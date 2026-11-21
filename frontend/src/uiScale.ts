/**
 * Size of the interface (text, spacing, fields — everything), applied as CSS `zoom` on the page
 * (App.vue). Vuetify sizes spacing and fields in px, so scaling only the font would leave large
 * boxes with small text.
 *
 * "auto" follows the width of the browser window (not the screen resolution: a wide screen with
 * a half-width window, or a notebook with 125% scaling, have less room):
 *   ≤ 1366 px → 0.88 · 1920 px → 1 · ≥ 2560 px → 1.1, in straight lines between them.
 * The other choices are fixed, whatever the window.
 */

export type UiScale = 'auto' | 'small' | 'normal' | 'large'

export const UI_SCALES: readonly UiScale[] = ['auto', 'small', 'normal', 'large']

/** Icons of the choices in Settings */
export const UI_SCALE_ICONS: Record<UiScale, string> = {
  auto: 'mdi-monitor-screenshot',
  small: 'mdi-format-font-size-decrease',
  normal: 'mdi-format-size',
  large: 'mdi-format-font-size-increase',
}

const FIXED: Record<Exclude<UiScale, 'auto'>, number> = { small: 0.88, normal: 1, large: 1.1 }

/** (window width in px, scale): "auto" is a straight line between consecutive points */
const AUTO_POINTS: readonly [number, number][] = [
  [1366, 0.88],
  [1920, 1],
  [2560, 1.1],
]

export function isUiScale(value: unknown): value is UiScale {
  return (UI_SCALES as readonly unknown[]).includes(value)
}

/** The automatic scale for a window `width` px wide (2 places, so small resizes change nothing). */
export function autoScale(width: number): number {
  const first = AUTO_POINTS[0]!
  const last = AUTO_POINTS[AUTO_POINTS.length - 1]!
  if (!(width > first[0])) return first[1]
  if (width >= last[0]) return last[1]
  for (let i = 1; i < AUTO_POINTS.length; i++) {
    const [x1, y1] = AUTO_POINTS[i]!
    if (width <= x1) {
      const [x0, y0] = AUTO_POINTS[i - 1]!
      return Math.round((y0 + ((y1 - y0) * (width - x0)) / (x1 - x0)) * 100) / 100
    }
  }
  return last[1]
}

/** The scale to apply: the user's choice, or the automatic one for the window's width. */
export function uiScaleFactor(choice: UiScale, width: number): number {
  return choice === 'auto' ? autoScale(width) : FIXED[choice]
}
