/**
 * The value at a term as typed in a single field (the eFMV analyses' pattern): money in the
 * currency ("55.000,00" in pt-br) or a percentage of the original value ("70%", "62,5 %").
 * The API resolves it (never computed here); a percentage becomes its value once the field
 * is left.
 */
import { parseMoney } from '@/utils/money'
import type { AnchorMode } from './api'

export function parseTermInput(
  text: string,
  language: string,
): { mode: AnchorMode; amount: string } | null {
  const percent = /^(.*?)\s*%\s*$/.exec(text.trim())
  if (percent) {
    const amount = parseMoney(percent[1]!, language, 4)
    return amount === null ? null : { mode: 'percent', amount }
  }
  const amount = parseMoney(text, language, 2)
  return amount === null ? null : { mode: 'value', amount }
}
