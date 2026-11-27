<script setup lang="ts">
/**
 * Print an eFMV analysis: choose its scenarios (all at first) and whether each one's list of
 * assets goes too; the report (`report.ts`) is previewed in a frame and that same frame is
 * printed (or saved as PDF by the browser). Made from the analysis as last saved and the
 * disclaimer of the Pricing settings, in the language chosen in the dialog (the user's at
 * first): its texts, scenario names, numbers and disclaimer — what the API writes (asset
 * classes, the scope written from the assets) stays in the user's language. Nothing is stored. While the
 * project is private, Print with Shift held prints it without the "Horizon" name (not shown
 * anywhere on screen; through a hidden frame, so the preview stays as it is).
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { formatDate } from '@/dateFormat'
import { LANGUAGES } from '@/i18n'
import { formatNumber, type NumberKey } from '@/numberFormat'
import { usePreferencesStore } from '@/stores/preferences'
import { specSummary } from '@/modules/average-prices/specText'
import { getPricingSettings } from '@/modules/pricing-settings/api'
import { printDocument } from '@/utils/html'
import { formatMoney } from '@/utils/money'
import { getEfmvAnalysis, type EfmvAnalysis } from './api'
import { scenarioTitle } from './draft'
import { colorThemeById } from '@/themes'
import { disclaimerFor, reportFileName, reportHtml, type ReportStyle } from './report'

const props = defineProps<{ analysisId: number }>()
const open = defineModel<boolean>({ required: true })

const { t, locale } = useI18n()
const preferences = usePreferencesStore()
/** The report's language: the user's at first, changeable in the dialog */
const language = ref<string>(locale.value)
const languageOptions = LANGUAGES.map((l) => ({ value: l.code, title: l.name }))

const analysis = ref<EfmvAnalysis | null>(null)
const disclaimers = ref<Record<string, string>>({})
const chosen = ref<number[]>([])
const withAssets = ref(false)
const loading = ref(false)
const failed = ref(false)
const printedAt = ref(new Date().toISOString())
const frame = ref<HTMLIFrameElement | null>(null)

// Also when it is created already open (the grid creates it on the first click)
watch(
  [open, () => props.analysisId],
  async ([isOpen]) => {
    if (isOpen) await load()
  },
  { immediate: true },
)

async function load() {
  loading.value = true
  failed.value = false
  printedAt.value = new Date().toISOString()
  language.value = locale.value
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
}

/** The font's @font-face rules as the page has them (their files served by Horizon) */
function fontFaces(fontName: string): string {
  const rules: string[] = []
  for (const sheet of Array.from(document.styleSheets)) {
    let list: CSSRuleList
    try {
      list = sheet.cssRules
    } catch {
      continue // another origin's sheet cannot be read
    }
    for (const rule of Array.from(list)) {
      if (
        rule instanceof CSSFontFaceRule &&
        rule.style.getPropertyValue('font-family').includes(fontName)
      ) {
        rules.push(rule.cssText)
      }
    }
  }
  return rules.join('\n')
}

/** The report in the user's theme — its light version (paper is white) and its font */
const style = computed<ReportStyle>(() => {
  const theme = colorThemeById(preferences.colorTheme)
  const colors = theme.light.colors ?? {}
  return {
    primary: String(colors.primary ?? '#00926F'),
    accent: String(colors.brand ?? colors.primary ?? '#00926F'),
    text: String(colors['on-surface'] ?? '#1C252E'),
    tint: String(colors['surface-light'] ?? '#F4F6F8'),
    fontFamily: theme.fontFamily,
    fontFaces: fontFaces(theme.fontName),
  }
})

function makeReport(unbranded: boolean): string {
  if (!analysis.value) return ''
  const lang = language.value
  const tr = (key: string, values?: Record<string, unknown>) =>
    t(key, values ?? {}, { locale: lang })
  const num = (value: number, key: NumberKey) => formatNumber(value, key, lang)
  return reportHtml(
    analysis.value,
    {
      scenarioIds: chosen.value,
      assets: withAssets.value,
      disclaimer: disclaimerFor(disclaimers.value, lang),
      printedAt: printedAt.value,
      unbranded,
      style: style.value,
    },
    {
      t: tr,
      money: (value, currency) => formatMoney(value, currency, lang),
      percent: (value) => `${num(Number(value), 'percentValue')}%`,
      date: (iso) =>
        formatDate(new Date(iso), 'short', lang, preferences.dateFormat, preferences.timeFormat),
      specs: (item) => specSummary(item.specs ?? [], tr, num),
      title: (scenario) =>
        scenarioTitle(
          String(scenario.term_months),
          scenario.name,
          (count) => t('efmv.scenario.termTitle', count, { locale: lang }),
          tr('efmv.scenario.untitled'),
        ),
    },
  )
}

const html = computed(() => makeReport(false))

/**
 * While printing, the page's own title is the report's file name too: browsers suggest the PDF's
 * name from a title — the frame's in some, the page's in others. Restored once printing is over
 * (print() returns then in most browsers; a timeout for the others).
 */
function withFileTitle(run: () => void) {
  if (!analysis.value) return
  const previous = document.title
  document.title = reportFileName(analysis.value)
  let restored = false
  const restore = () => {
    if (restored) return
    restored = true
    document.title = previous
  }
  window.addEventListener('afterprint', restore, { once: true })
  try {
    run()
  } finally {
    setTimeout(restore, 1000)
  }
}

function print(event?: MouseEvent | KeyboardEvent) {
  // Shift held: without the "Horizon" name
  if (event?.shiftKey) {
    withFileTitle(() => printDocument(makeReport(true)))
    return
  }
  const win = frame.value?.contentWindow
  if (!win) return
  withFileTitle(() => {
    win.focus()
    win.print()
  })
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
            <v-select
              v-model="language"
              :items="languageOptions"
              :label="$t('efmv.report.language')"
              prepend-inner-icon="mdi-translate"
              density="compact"
              hide-details
              class="mb-4"
              data-testid="report-language"
            />
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
          @click="print($event)"
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
