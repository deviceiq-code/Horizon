<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import ServerCrudTable from '@/components/ServerCrudTable.vue'
import { deleteEfmvAnalysis, listEfmvAnalyses, type EfmvAnalysisRow } from './api'

const { t, d } = useI18n()
const router = useRouter()
const table = ref<{ reload: () => Promise<void> } | null>(null)

const headers = computed(() => [
  { title: t('efmv.fields.code'), key: 'code', width: 170 },
  { title: t('efmv.fields.customer'), key: 'customer', minWidth: '220px' },
  { title: t('efmv.fields.accountManager'), key: 'account_manager' },
  { title: t('efmv.scenarios'), key: 'scenario_names', sortable: false },
  { title: t('efmv.fields.createdAt'), key: 'created_at', width: 160 },
])

const open = (row: EfmvAnalysisRow) =>
  router.push({ name: 'efmv-analysis', params: { id: row.id } })
</script>

<template>
  <v-container fluid class="module-page">
    <h1 class="text-h5 mb-1">{{ $t('efmv.title') }}</h1>
    <p class="text-body-2 text-medium-emphasis mb-4">{{ $t('efmv.subtitle') }}</p>
    <ServerCrudTable
      ref="table"
      :fetch-page="listEfmvAnalyses"
      :delete-item="deleteEfmvAnalysis"
      :headers="headers"
      :sort-by="[{ key: 'created_at', order: 'desc' }]"
      :ordering-fields="{
        customer: 'customer__name',
        account_manager: 'account_manager__first_name',
      }"
      :search-placeholder="$t('efmv.searchPlaceholder')"
      :empty-text="$t('efmv.empty')"
      :no-results-text="$t('efmv.noResults')"
      :delete-title="$t('efmv.deleteTitle')"
      :delete-message="(row: EfmvAnalysisRow) => $t('efmv.deleteConfirm', { code: row.code })"
      :deleted-text="$t('efmv.deletedText')"
      edit-icon="mdi-open-in-app"
      :edit-title="$t('efmv.open')"
      @create="router.push({ name: 'efmv-analysis-new' })"
      @edit="open"
    >
      <template #[`item.code`]="{ item }">
        <router-link
          :to="{ name: 'efmv-analysis', params: { id: item.id } }"
          class="font-weight-medium text-primary text-no-wrap"
          data-testid="code"
        >
          {{ item.code }}
        </router-link>
      </template>
      <template #[`item.customer`]="{ item }">
        <div>{{ item.customer_detail.name }}</div>
        <div v-if="item.customer_detail.trade_name" class="text-caption text-medium-emphasis">
          {{ item.customer_detail.trade_name }}
        </div>
      </template>
      <template #[`item.account_manager`]="{ item }">
        {{ item.account_manager_detail.full_name }}
      </template>
      <template #[`item.scenario_names`]="{ item }">
        <div class="d-flex flex-wrap ga-1 py-1">
          <v-chip v-for="name in item.scenario_names" :key="name" size="small" variant="tonal">
            {{ name }}
          </v-chip>
        </div>
      </template>
      <template #[`item.created_at`]="{ item }">
        <div class="text-no-wrap">{{ d(new Date(item.created_at), 'short') }}</div>
        <div v-if="item.created_by_name" class="text-caption text-medium-emphasis">
          {{ item.created_by_name }}
        </div>
      </template>
    </ServerCrudTable>
  </v-container>
</template>
