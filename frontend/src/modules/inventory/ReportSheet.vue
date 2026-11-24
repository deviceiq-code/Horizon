<script setup lang="ts">
/**
 * An inspection report as a document: identification, grade (with each domain's meaning),
 * kit, test script, findings with values, data erasure, photos and approvals. It is the
 * printable form too — the browser's "Print → Save as PDF" makes the PDF.
 */
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useDateFormat } from '@/composables/useDateFormat'
import { useNumberFormat } from '@/composables/useNumberFormat'
import { specText } from '@/modules/average-prices/specText'
import { formatMoney } from '@/utils/money'
import { listGradeLevels, reportPhotoUrl, type GradeLevel, type InspectionReport } from './api'

const props = defineProps<{ report: InspectionReport }>()

const { t, locale } = useI18n()
const { d } = useDateFormat()
const { n } = useNumberFormat()

const levels = ref<GradeLevel[]>([])
onMounted(async () => {
  try {
    levels.value = await listGradeLevels()
  } catch {
    levels.value = []
  }
})

function level(domain: string, code: string) {
  return levels.value.find((l) => l.domain === domain && l.code === code)
}

const asset = computed(() => props.report.asset_detail)
const findings = computed(() => props.report.findings.filter((f) => f.status !== 'cancelled'))
const total = computed(() =>
  findings.value.reduce((sum, f) => sum + (f.value ? Number(f.value) : 0), 0).toFixed(2),
)
const when = (value: string | null) => (value ? d(new Date(value), 'dateTime') : '—')
</script>

<template>
  <div class="report-sheet" data-testid="report-sheet">
    <div class="d-flex flex-wrap align-start ga-4 mb-4">
      <div class="flex-grow-1">
        <div class="text-overline">{{ $t('inventory.reports.document') }}</div>
        <h2 class="text-h5 font-weight-bold">{{ asset.horizon_id }} · v{{ report.version }}</h2>
        <div class="text-body-1">
          {{ asset.asset_model_detail.manufacturer_name }} {{ asset.asset_model_detail.name }} ·
          {{ asset.asset_model_detail.asset_class_name }}
        </div>
        <div class="text-body-2 text-medium-emphasis">
          {{ $t('inventory.fields.serial') }}: {{ asset.serial || '—' }}
          <template v-if="report.customer_name">
            · {{ $t('inventory.appointments.customer') }}: {{ report.customer_name }}
          </template>
          <template v-if="report.lot_code"> · {{ report.lot_code }}</template>
        </div>
      </div>
      <div v-if="report.grade" class="grade-box text-center" data-testid="grade">
        <div class="text-caption">{{ $t('inventory.reports.grade') }}</div>
        <div class="text-h4 font-weight-bold">{{ report.grade }}</div>
      </div>
    </div>

    <v-table density="compact" class="mb-4">
      <tbody>
        <tr
          v-for="domain in ['conservation', 'functioning', 'completeness'] as const"
          :key="domain"
        >
          <th style="width: 30%">{{ $t(`inventory.grades.domains.${domain}`) }}</th>
          <td>
            <strong>{{ report[domain] || '—' }}</strong>
            <template v-if="level(domain, report[domain])">
              · {{ level(domain, report[domain])!.name }} —
              <span class="text-medium-emphasis">{{
                level(domain, report[domain])!.description
              }}</span>
            </template>
          </td>
        </tr>
        <tr v-if="report.failed_components">
          <th>{{ $t('inventory.reports.failedComponents') }}</th>
          <td>{{ report.failed_components }}</td>
        </tr>
        <tr>
          <th>{{ $t('inventory.reports.cleaning') }}</th>
          <td>{{ $t(`inventory.reports.cleanings.${report.cleaning}`) }}</td>
        </tr>
        <tr v-if="report.recommended_destination">
          <th>{{ $t('inventory.reports.destination') }}</th>
          <td>{{ $t(`inventory.reports.destinations.${report.recommended_destination}`) }}</td>
        </tr>
      </tbody>
    </v-table>

    <v-row>
      <v-col cols="12" md="6">
        <div class="text-subtitle-2 mb-1">{{ $t('inventory.reports.kit') }}</div>
        <ul class="text-body-2 ml-4">
          <li v-for="entry in report.kit_checklist" :key="entry.item">
            {{ entry.item }}
            <span v-if="entry.essential" class="text-caption"
              >({{ $t('assetModels.kitEssential') }})</span
            >
            —
            <strong :class="report.missing_items.includes(entry.item) ? 'text-error' : ''">
              {{
                report.missing_items.includes(entry.item)
                  ? $t('inventory.reports.missing')
                  : $t('inventory.reports.present')
              }}
            </strong>
          </li>
          <li v-if="!report.kit_checklist.length" class="text-medium-emphasis">—</li>
        </ul>
      </v-col>
      <v-col cols="12" md="6">
        <div class="text-subtitle-2 mb-1">{{ $t('inventory.reports.tests') }}</div>
        <ul class="text-body-2 ml-4">
          <li v-for="item in report.test_script" :key="item">
            {{ item }} —
            <strong :class="report.test_results[item] === 'fail' ? 'text-error' : ''">
              {{
                report.test_results[item]
                  ? $t(`inventory.reports.results.${report.test_results[item]}`)
                  : '—'
              }}
            </strong>
          </li>
          <li v-if="!report.test_script.length" class="text-medium-emphasis">—</li>
        </ul>
      </v-col>
    </v-row>

    <div v-if="asset.specs.length" class="mt-2">
      <div class="text-subtitle-2 mb-1">{{ $t('inventory.assets.specs') }}</div>
      <div class="text-body-2">
        <span v-for="spec in asset.specs" :key="spec.key" class="mr-4">
          <span class="text-medium-emphasis">{{ spec.label }}:</span> {{ specText(spec, t, n) }}
        </span>
      </div>
    </div>

    <div class="text-subtitle-2 mt-4 mb-1">{{ $t('inventory.reports.findings') }}</div>
    <v-table density="compact" data-testid="sheet-findings">
      <thead>
        <tr>
          <th>{{ $t('inventory.findings.kind') }}</th>
          <th>{{ $t('inventory.findings.description') }}</th>
          <th class="text-right">{{ $t('inventory.penalties.value') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="f in findings" :key="f.id">
          <td>
            {{ $t(`inventory.findings.kinds.${f.kind}`) }}
            <span v-if="f.block_type" class="text-caption">
              ({{ $t(`inventory.findings.blockTypes.${f.block_type}`) }})
            </span>
          </td>
          <td>{{ f.item || f.description }}</td>
          <td class="text-right">{{ f.value ? formatMoney(f.value, 'BRL', locale) : '—' }}</td>
        </tr>
        <tr v-if="!findings.length">
          <td colspan="3" class="text-medium-emphasis">{{ $t('inventory.reports.noFindings') }}</td>
        </tr>
        <tr v-else>
          <td colspan="2" class="font-weight-bold">{{ $t('inventory.reports.total') }}</td>
          <td class="text-right font-weight-bold">{{ formatMoney(total, 'BRL', locale) }}</td>
        </tr>
      </tbody>
    </v-table>

    <template v-if="report.has_storage">
      <div class="text-subtitle-2 mt-4 mb-1">{{ $t('inventory.reports.erasure') }}</div>
      <ul class="text-body-2 ml-4">
        <li v-for="c in report.erasures" :key="c.id">
          {{ c.tool_label }} · {{ $t(`inventory.erasure.methodNames.${c.method}`) }} ·
          {{ $t(`inventory.erasure.results.${c.result}`) }}
          <template v-if="c.disk_serial"> · {{ c.disk_serial }}</template>
          <template v-if="c.removed_disk_code">
            · {{ $t('inventory.erasure.diskRemoved', { code: c.removed_disk_code }) }}
          </template>
          · {{ when(c.at) }}
        </li>
        <li v-if="!report.erasures.length" class="text-medium-emphasis">—</li>
      </ul>
    </template>

    <div v-if="report.photos.length" class="mt-4">
      <div class="text-subtitle-2 mb-1">{{ $t('inventory.reports.photos') }}</div>
      <div class="photo-grid">
        <figure v-for="p in report.photos" :key="p.id">
          <img :src="reportPhotoUrl(report.id, p.id)" :alt="p.name" />
          <figcaption class="text-caption">
            {{ $t(`inventory.photoKinds.${p.kind}`)
            }}<template v-if="p.description"> · {{ p.description }}</template>
          </figcaption>
        </figure>
      </div>
    </div>

    <div v-if="report.notes" class="mt-4">
      <div class="text-subtitle-2 mb-1">{{ $t('customers.fields.notes') }}</div>
      <p class="text-body-2">{{ report.notes }}</p>
    </div>

    <v-divider class="my-4" />
    <div class="d-flex flex-wrap ga-6 text-body-2">
      <span>
        <strong>{{ $t('inventory.reports.technician') }}:</strong> {{ report.technician_name }} ·
        {{ when(report.finished_at) }}
      </span>
      <span>
        <strong>{{ $t('inventory.reports.approvedBy') }}:</strong>
        {{ report.approved_by_name ?? '—' }} · {{ when(report.approved_at) }}
      </span>
      <span v-if="report.sent_to_customer_at">
        <strong>{{ $t('inventory.reports.sentAt') }}:</strong>
        {{ when(report.sent_to_customer_at) }}
      </span>
    </div>
    <p v-if="report.new_version_reason" class="text-caption mt-2">
      {{ $t('inventory.reports.versionReason') }}: {{ report.new_version_reason }}
    </p>
  </div>
</template>

<style scoped>
.grade-box {
  border: 2px solid rgb(var(--v-theme-primary));
  border-radius: 12px;
  padding: 8px 20px;
  min-width: 120px;
}
.photo-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
}
.photo-grid img {
  width: 100%;
  height: 120px;
  object-fit: cover;
  border-radius: 8px;
}
.report-sheet th {
  font-weight: 500;
}
</style>
