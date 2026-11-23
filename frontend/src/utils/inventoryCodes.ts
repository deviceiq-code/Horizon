/**
 * Codes read by barcode guns (the backend's inventory/codes.py is the reference; the server
 * checks them again): the Horizon ID of an asset ("H" + 8 digits + Luhn check digit), a
 * container ("C" + 8 digits + check digit) and a location ("SP01-EST-03").
 */

export type CodeKind = 'asset' | 'container' | 'location' | 'unknown'

export interface ParsedCode {
  kind: CodeKind
  /** Without spaces, uppercase */
  code: string
  /** The check digit is right (assets and containers); locations are checked by the server */
  valid: boolean
}

const SEQUENCED = /^([HC])(\d{8})(\d)$/
const LOCATION = /^[A-Z0-9]+(-[A-Z0-9]+)+$/

export function luhnDigit(digits: string): string {
  let total = 0
  ;[...digits].reverse().forEach((char, position) => {
    let digit = Number(char)
    if (position % 2 === 0) {
      digit *= 2
      if (digit > 9) digit -= 9
    }
    total += digit
  })
  return String((10 - (total % 10)) % 10)
}

/** formatCode('H', 1234) → "H000012344". */
export function formatCode(prefix: 'H' | 'C', number: number): string {
  const digits = String(number).padStart(8, '0')
  return `${prefix}${digits}${luhnDigit(digits)}`
}

export function normalizeCode(text: string): string {
  return text.replace(/\s+/g, '').toUpperCase()
}

export function parseCode(text: string): ParsedCode {
  const code = normalizeCode(text)
  const match = SEQUENCED.exec(code)
  if (match) {
    return {
      kind: match[1] === 'H' ? 'asset' : 'container',
      code,
      valid: luhnDigit(match[2]!) === match[3],
    }
  }
  if (LOCATION.test(code)) return { kind: 'location', code, valid: true }
  return { kind: 'unknown', code, valid: false }
}
