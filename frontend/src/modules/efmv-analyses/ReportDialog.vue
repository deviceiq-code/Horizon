<script setup lang="ts">
/**
 * Print an eFMV analysis: choose its scenarios (all at first) and whether each one's list of
 * assets goes too; the report (`report.ts`) is previewed in a frame and that same frame is
 * printed (or saved as PDF by the browser). Made from the analysis as last saved and the
 * disclaimer of the Pricing settings in the user's language; nothing is stored.
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useDateFormat } from '@/composables/useDateFormat'
import { useNumberFormat } from '@/composables/useNumberFormat'
import { specSummary } from '@/modules/average-prices/specText'
import { getPricingSettings } from '@/modules/pricing-settings/api'
import { formatMoney } from '@/utils/money'
import { getEfmvAnalysis, type EfmvAnalysis } from './api'
import { disclaimerFor, reportHtml } from './report'

const props = defineProps<{ analysisId: number }>()
const open = defineModel<boolean>({ required: true })

const { t, locale } = useI18n()
const { n } = useNumberFormat()
const { d } = useDateFormat()

const analysis = ref<EfmvAnalysis | null>(null)
const disclaimers = ref<Record<string, string>>({})
const chosen = ref<number[]>([])
const withAssets = ref(false)
const loading = ref(false)
const failed = ref(false)
const printedAt = ref(new Date().toISOString())
const frame = ref<HTMLIFrameElement | null>(null)

watch(open, async (isOpen) => {
  if (!isOpen) return
  loading.value = true
  failed.value = false
  printedAt.value = new Date().toISOString()
  try {
    const [data, settings] = await Promise.all([
      getEfmvAnalysis(props.analysisId),
      getPricingSettings(),
    ])
    analysis.value = data
    disclaimers.value = settings.report_disclaimer
    chosen.value = data.scenarios.map((s) => s.id)
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
})

const html = computed(() => {
  if (!analysis.value) return ''
  return reportHtml(
    analysis.value,
    {
      scenarioIds: chosen.value,
      assets: withAssets.value,
      disclaimer: disclaimerFor(disclaimers.value, locale.value),
      printedAt: printedAt.value,
    },
    {
      t: (key, values) => (values ? t(key, values) : t(key)),
      money: (value, currency) => formatMoney(value, currency, locale.value),
      percent: (value) => `${n(Number(value), 'percentValue')}%`,
      date: (iso) => d(new Date(iso), 'short'),
      specs: (item) => specSummary(item.specs ?? [], t, n),
    },
  )
})

function print() {
  const win = frame.value?.contentWindow
  if (!win) return
  win.focus()
  win.print()
}
</script>

<template>
  <v-dialog v-model="open" max-width="1280" scrollable>
    <v-card data-testid="report-dialog">
      <v-card-title class="d-flex align-center ga-2 pt-4 px-6">
        <v-icon icon="mdi-printer-outline" color="primary" />
        {{ $t('efmv.report.dialogTitle') }}
        <span v-if="analysis" class="text-medium-emphasis text-body-1">· {{ analysis.code }}</span>
        <v-spacer />
        <v-btn icon="mdi-close" variant="text" size="small" @click="open = false" />
      </v-card-title>
      <v-card-text class="px-6 pb-2">
        <v-progress-linear v-if="loading" indeterminate class="mb-4" />
        <v-alert v-else-if="failed" type="error" variant="tonal">{{
          $t('common.loadError')
        }}</v-alert>
        <div v-else-if="analysis" class="report-layout">
          <!-- What goes in it -->
          <div class="options">
            <div class="text-subtitle-2 mb-1">{{ $t('efmv.report.scenarios') }}</div>
            <v-checkbox
              v-for="scenario in analysis.scenarios"
              :key="scenario.id"
              v-model="chosen"
              :value="scenario.id"
              :label="scenario.title"
              density="compact"
              hide-details
              :data-testid="`report-scenario-${scenario.id}`"
            />
            <v-divider class="my-3" />
            <v-switch
              v-model="withAssets"
              :label="$t('efmv.report.includeAssets')"
              color="primary"
              inset
              density="compact"
              hide-details
              data-testid="report-assets"
            />
            <p class="text-caption text-medium-emphasis mt-3">
              {{ $t('efmv.report.savedHint') }}
            </p>
          </div>
          <!-- The preview: the very document that is printed -->
          <iframe
            ref="frame"
            class="preview"
            :srcdoc="html"
            :title="$t('efmv.report.preview')"
            data-testid="report-preview"
          />
        </div>
      </v-card-text>
      <v-card-actions class="px-6 pb-4">
        <v-spacer />
        <v-btn variant="text" @click="open = false">{{ $t('common.close') }}</v-btn>
        <v-btn
          color="primary"
          variant="flat"
          prepend-icon="mdi-printer-outline"
          :disabled="!analysis || !chosen.length"
          data-testid="report-print"
          @click="print"
          >{{ $t('efmv.report.print') }}</v-btn
        >
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.report-layout {
  display: grid;
  grid-template-columns: 240px 1fr;
  gap: 16px;
  min-height: 0;
}
@media (max-width: 959.98px) {
  .report-layout {
    grid-template-columns: 1fr;
  }
}
.preview {
  width: 100%;
  height: calc(72dvh / var(--ui-zoom, 1));
  border: thin solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 8px;
  background: #fff;
}
</style>
