/**
 * State of the column filters of the Average Prices grid: what the user types (text kept as
 * typed, sent after a short pause) and the query parameters sent to the API.
 */
import { reactive, ref, watch } from 'vue'
import { parseMoney } from '@/utils/money'

export interface PriceFilters {
  asset_class: number | null
  /** Model or manufacturer contains */
  model: string
  original_value_min: string
  original_value_max: string
  /** YYYY-MM-DD, inclusive */
  created_from: string
  created_to: string
  [key: string]: string | number | null
}

const TYPING_DELAY_MS = 350

export function usePriceFilters(language: () => string) {
  const filters = reactive<PriceFilters>({
    asset_class: null,
    model: '',
    original_value_min: '',
    original_value_max: '',
    created_from: '',
    created_to: '',
  })

  // Typed text, applied after a pause; money in the UI language ("1.250.000,00")
  const typed = reactive({ model: '', min: '', max: '' })
  const invalid = reactive({ min: false, max: false })

  let timer: ReturnType<typeof setTimeout> | undefined
  watch(
    () => ({ ...typed }),
    (value) => {
      clearTimeout(timer)
      timer = setTimeout(() => {
        filters.model = value.model.trim()
        for (const [key, param] of [
          ['min', 'original_value_min'],
          ['max', 'original_value_max'],
        ] as const) {
          const text = value[key].trim()
          const parsed = text ? parseMoney(text, language()) : ''
          invalid[key] = parsed === null
          filters[param] = parsed ?? ''
        }
      }, TYPING_DELAY_MS)
    },
  )

  // Remounts the asset class picker when cleared
  const pickerKey = ref(0)

  function clear() {
    clearTimeout(timer)
    Object.assign(typed, { model: '', min: '', max: '' })
    Object.assign(invalid, { min: false, max: false })
    Object.assign(filters, {
      asset_class: null,
      model: '',
      original_value_min: '',
      original_value_max: '',
      created_from: '',
      created_to: '',
    })
    pickerKey.value += 1
  }

  return { filters, typed, invalid, pickerKey, clear }
}
