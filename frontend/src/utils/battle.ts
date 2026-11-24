/**
 * Battle Cards (`components/BattleCards.vue`): how many records can be compared, and who wins
 * an attribute — the highest value; none when fewer than two cards have one, or all tie.
 */
export const MAX_COMPARED = 3

export function winners(values: (number | null)[]): boolean[] {
  const present = values.filter((v): v is number => v !== null && !Number.isNaN(v))
  if (present.length < 2) return values.map(() => false)
  const top = Math.max(...present)
  if (present.every((v) => v === top)) return values.map(() => false)
  return values.map((v) => v !== null && v === top)
}
