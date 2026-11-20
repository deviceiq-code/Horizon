/**
 * Column filters of the Asset Classes grid: name or keyword (sent after a short pause), a
 * vertical or one of its sub-verticals (one picker), minimum remarketing average and status.
 */
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { listVerticals, type Vertical } from '../verticals/api'

export function useAssetClassFilters() {
  const { t } = useI18n()

  const filters = reactive<Record<string, string | number | null>>({
    name: '',
    vertical: null,
    sub_vertical: null,
    remarketing_min: null,
    is_enabled: null,
  })

  // Name typed: applied after a pause
  const typedName = ref('')
  let timer: ReturnType<typeof setTimeout> | undefined
  watch(typedName, (value) => {
    clearTimeout(timer)
    timer = setTimeout(() => (filters.name = (value ?? '').trim()), 350)
  })

  // Vertical or sub-vertical: "v:<id>" / "s:<id>"
  const scope = ref<string | null>(null)
  watch(scope, (value) => {
    const [kind, id] = (value ?? '').split(':')
    filters.vertical = kind === 'v' ? Number(id) : null
    filters.sub_vertical = kind === 's' ? Number(id) : null
  })

  const verticals = ref<Vertical[]>([])
  async function loadVerticals() {
    verticals.value = (await listVerticals({ page: 1, pageSize: 200, ordering: 'name' })).results
  }
  const scopeItems = computed(() =>
    verticals.value.flatMap((vertical) => [
      { value: `v:${vertical.id}`, title: vertical.name },
      ...vertical.sub_verticals
        .filter((sub) => sub.id !== undefined)
        .map((sub) => ({
          value: `s:${sub.id}`,
          title: `${vertical.name} / ${sub.is_general ? t('verticals.general') : sub.name}`,
        })),
    ]),
  )

  function clear() {
    clearTimeout(timer)
    typedName.value = ''
    scope.value = null
    Object.assign(filters, {
      name: '',
      vertical: null,
      sub_vertical: null,
      remarketing_min: null,
      is_enabled: null,
    })
  }

  return { filters, typedName, scope, scopeItems, loadVerticals, clear }
}
