/** Display formatting for Brazilian documents. The backend stores and validates the raw values. */

export const BRAZILIAN_STATES = [
  'AC', 'AL', 'AM', 'AP', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MG', 'MS', 'MT', 'PA',
  'PB', 'PE', 'PI', 'PR', 'RJ', 'RN', 'RO', 'RR', 'RS', 'SC', 'SE', 'SP', 'TO',
] as const // prettier-ignore

/** "11222333000181" → "11.222.333/0001-81"; "11144477735" → "111.444.777-35" (Brazil only). */
export function formatTaxId(taxId: string, country: string): string {
  if (country !== 'BR') return taxId
  if (/^\d{11}$/.test(taxId)) return taxId.replace(/^(\d{3})(\d{3})(\d{3})(\d{2})$/, '$1.$2.$3-$4')
  // CNPJ, numeric or alphanumeric (first 12 characters may be letters)
  if (/^[0-9A-Z]{12}\d{2}$/.test(taxId)) {
    return taxId.replace(/^(.{2})(.{3})(.{3})(.{4})(.{2})$/, '$1.$2.$3/$4-$5')
  }
  return taxId
}

/** "13010100" → "13010-100" (Brazil only). */
export function formatPostalCode(postalCode: string, country: string): string {
  if (country === 'BR' && /^\d{8}$/.test(postalCode)) {
    return `${postalCode.slice(0, 5)}-${postalCode.slice(5)}`
  }
  return postalCode
}
