<script setup lang="ts">
/** The erasure tool and method of each asset class with data storage in the lot (RN-04):
 * supervisors define them; technicians see which one to use. */
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import { useNotificationsStore } from '@/stores/notifications'
import { lotErasureTools, setLotErasureTools, type Lot, type LotErasureToolRow } from './api'
import { useInventoryRoles } from './roles'

const props = defineProps<{ lot: Lot }>()

const { t } = useI18n()
const notifications = useNotificationsStore()
const { isSupervisor } = useInventoryRoles()

const rows = ref<LotErasureToolRow[]>([])
const choice = ref<Record<number, { tool: number | null; method: string | null }>>({})

async function load() {
  rows.value = await lotErasureTools(props.lot.id)
  choice.value = Object.fromEntries(
    rows.value.map((row) => [
      row.asset_class,
      { tool: row.definition?.tool ?? null, method: row.definition?.method ?? null },
    ]),
  )
}
onMounted(load)

function methodsOf(row: LotErasureToolRow) {
  const tool = row.tools.find((tl) => tl.id === choice.value[row.asset_class]?.tool)
  return (tool?.methods ?? []).map((m) => ({
    value: m,
    title: t(`inventory.erasure.methodNames.${m}`),
  }))
}

async function save(row: LotErasureToolRow) {
  const c = choice.value[row.asset_class]
  if (!c?.tool || !c.method) return
  try {
    rows.value = await setLotErasureTools(props.lot.id, [
      { asset_class: row.asset_class, tool: c.tool, method: c.method as never },
    ])
    notifications.notify(t('inventory.erasure.lotSaved'))
  } catch (error) {
    notifications.notify(error instanceof ApiError ? error.message : t('common.saveError'), 'error')
  }
}
</script>

<template>
  <div>
    <p class="text-body-2 text-medium-emphasis mb-3">{{ $t('inventory.erasure.lotHint') }}</p>
    <v-table v-if="rows.length" density="comfortable" data-testid="lot-tools">
      <thead>
        <tr>
          <th>{{ $t('inventory.fields.assetClass') }}</th>
          <th>{{ $t('inventory.erasure.tool') }}</th>
          <th>{{ $t('inventory.erasure.method') }}</th>
          <th v-if="isSupervisor" />
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.asset_class">
          <td class="font-weight-medium">{{ row.asset_class_name }}</td>
          <template v-if="isSupervisor">
            <td style="min-width: 240px">
              <v-select
                v-model="choice[row.asset_class]!.tool"
                :items="row.tools.map((tl) => ({ value: tl.id, title: tl.label }))"
                :no-data-text="$t('inventory.erasure.noTool')"
                density="compact"
                hide-details
              />
            </td>
            <td style="min-width: 200px">
              <v-select
                v-model="choice[row.asset_class]!.method"
                :items="methodsOf(row)"
                density="compact"
                hide-details
              />
            </td>
            <td>
              <v-btn size="small" variant="tonal" color="primary" @click="save(row)">
                {{ $t('common.save') }}
              </v-btn>
            </td>
          </template>
          <template v-else>
            <td>{{ row.definition?.tool_label ?? $t('inventory.erasure.notDefined') }}</td>
            <td>
              {{
                row.definition ? $t(`inventory.erasure.methodNames.${row.definition.method}`) : '—'
              }}
            </td>
          </template>
        </tr>
      </tbody>
    </v-table>
    <p v-else class="text-body-2 text-medium-emphasis">{{ $t('inventory.erasure.noStorage') }}</p>
  </div>
</template>
