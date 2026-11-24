<script setup lang="ts">
/** Data erasure tools (software or equipment): version, methods and the asset classes they
 * serve. Each lot uses one tool and method per asset class with data storage. */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import ActiveChip from '@/components/ActiveChip.vue'
import ServerCrudTable from '@/components/ServerCrudTable.vue'
import { useNotificationsStore } from '@/stores/notifications'
import ErasureToolFormDialog from './ErasureToolFormDialog.vue'
import { deleteErasureTool, listErasureTools, type ErasureTool } from './api'
import { useInventoryRoles } from './roles'

const { t } = useI18n()
const notifications = useNotificationsStore()
const { isSupervisor } = useInventoryRoles()

const table = ref<{ reload: () => Promise<void> } | null>(null)
const headers = computed(() => [
  { title: t('inventory.erasure.tool'), key: 'name' },
  { title: t('inventory.erasure.methods'), key: 'methods', sortable: false },
  { title: t('inventory.erasure.classes'), key: 'asset_classes', sortable: false },
  { title: t('customers.fields.status'), key: 'is_active', width: 150 },
])

const formOpen = ref(false)
const editing = ref<ErasureTool | null>(null)

function openForm(tool: ErasureTool | null) {
  editing.value = tool
  formOpen.value = true
}

function onSaved(_tool: ErasureTool, created: boolean) {
  notifications.notify(t(created ? 'inventory.erasure.created' : 'inventory.erasure.updated'))
  table.value?.reload()
}
</script>

<template>
  <ServerCrudTable
    ref="table"
    :fetch-page="listErasureTools"
    :delete-item="deleteErasureTool"
    :headers="headers"
    :sort-by="[{ key: 'name', order: 'asc' }]"
    :search-placeholder="$t('inventory.erasure.searchPlaceholder')"
    :empty-text="$t('inventory.erasure.empty')"
    :no-results-text="$t('inventory.erasure.noResults')"
    :delete-title="$t('inventory.erasure.deleteTitle')"
    :delete-message="
      (tool: ErasureTool) => $t('inventory.erasure.deleteConfirm', { name: tool.name })
    "
    :deleted-text="$t('inventory.erasure.deleted')"
    :hide-create="!isSupervisor"
    :can-edit="() => isSupervisor"
    :can-delete="() => isSupervisor"
    @create="openForm(null)"
    @edit="openForm"
  >
    <template #[`item.name`]="{ item }">
      <span class="font-weight-medium">{{ item.name }}</span>
      <span v-if="item.version" class="text-medium-emphasis"> {{ item.version }}</span>
    </template>
    <template #[`item.methods`]="{ item }">
      <div class="d-flex flex-wrap ga-1 py-1">
        <v-chip v-for="m in (item as ErasureTool).methods" :key="m" size="x-small" label>
          {{ $t(`inventory.erasure.methodNames.${m}`) }}
        </v-chip>
      </div>
    </template>
    <template #[`item.asset_classes`]="{ item }">
      {{ (item as ErasureTool).asset_classes_detail.map((c) => c.name).join(', ') || '—' }}
    </template>
    <template #[`item.is_active`]="{ item }"><ActiveChip :active="item.is_active" /></template>
  </ServerCrudTable>

  <ErasureToolFormDialog v-model="formOpen" :tool="editing" @saved="onSaved" />
</template>
