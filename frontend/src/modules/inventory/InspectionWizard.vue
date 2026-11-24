<script setup lang="ts">
/**
 * The inspection of an asset at the bench, step by step; every change is saved in the draft
 * at once. Steps: identification (pending serial, specifications), photos (the class's
 * required kinds), kit, tests (functioning), blocks and customizations, cleaning, data erasure
 * (models with storage) and classification — the grade "B1C" (suggested from the tests and
 * the kit), the recommended destination and what is still missing before submitting.
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import SpecValuesInput from '@/modules/average-prices/SpecValuesInput.vue'
import AssetModelPicker from '@/modules/catalogs/asset-models/AssetModelPicker.vue'
import { useNotificationsStore } from '@/stores/notifications'
import { formatMoney, parseMoney } from '@/utils/money'
import {
  BLOCK_TYPES,
  GRADE_CODES,
  PHOTO_KINDS,
  addCertificate,
  addFinding,
  certificateUrl,
  completeSerial,
  deleteFinding,
  deleteReportPhoto,
  getReport,
  reportPhotoUrl,
  setReportSpecs,
  submitReport,
  updateFinding,
  updateReport,
  uploadReportPhoto,
  type BlockType,
  type FindingKind,
  type InspectionReport,
  type PhotoKind,
  type ReportDraft,
} from './api'

const report = defineModel<InspectionReport>({ required: true })
const emit = defineEmits<{ submitted: [] }>()

const { t, locale } = useI18n()
const notifications = useNotificationsStore()

const step = ref('identification')
const saving = ref(false)
const error = ref('')

const steps = computed(() => [
  {
    key: 'identification',
    icon: 'mdi-card-account-details-outline',
    done: identificationDone.value,
  },
  { key: 'photos', icon: 'mdi-camera-outline', done: missingPhotoKinds.value.length === 0 },
  {
    key: 'kit',
    icon: 'mdi-format-list-checks',
    done: report.value.checklist_done || !report.value.kit_checklist.length,
  },
  { key: 'tests', icon: 'mdi-test-tube', done: testsDone.value },
  { key: 'blocks', icon: 'mdi-lock-alert-outline', done: true },
  { key: 'cleaning', icon: 'mdi-spray-bottle', done: true },
  ...(report.value.has_storage
    ? [{ key: 'erasure', icon: 'mdi-harddisk-remove', done: report.value.erasures.length > 0 }]
    : []),
  { key: 'classification', icon: 'mdi-medal-outline', done: !!report.value.grade },
])

function fail(e: unknown) {
  error.value = e instanceof ApiError && e.message ? e.message : t('common.saveError')
}

async function run(call: () => Promise<InspectionReport | unknown>) {
  saving.value = true
  error.value = ''
  try {
    const result = await call()
    report.value =
      result && typeof result === 'object' && 'asset_detail' in result
        ? (result as InspectionReport)
        : await getReport(report.value.id)
  } catch (e) {
    fail(e)
  } finally {
    saving.value = false
  }
}

const save = (data: ReportDraft) => run(() => updateReport(report.value.id, data))

// --- 1. Identification ---------------------------------------------------------------------------

const serial = ref('')
const specs = ref<Record<string, string>>({})
watch(
  () => report.value.asset_detail.specs,
  (values) => {
    specs.value = Object.fromEntries(values.map((spec) => [spec.key, spec.value]))
  },
  { immediate: true },
)
const template = computed(() => report.value.asset_detail.specs)
const identificationDone = computed(
  () =>
    report.value.asset_detail.serial_status !== 'pending' &&
    template.value.every((f) => !f.required || f.value),
)
const saveSerial = () => run(() => completeSerial(report.value.id, serial.value))
function canonicalSpecs() {
  return Object.fromEntries(
    template.value.map((field) => {
      const text = specs.value[field.key] ?? ''
      return [
        field.key,
        field.kind === 'number' && text.trim() ? (parseMoney(text, locale.value, 6) ?? text) : text,
      ]
    }),
  )
}
const saveSpecs = () => run(() => setReportSpecs(report.value.id, canonicalSpecs()))

// --- 2. Photos -------------------------------------------------------------------------------

const photoKind = ref<PhotoKind>('front')
const photoFile = ref<File | null>(null)
const photoDescription = ref('')
const photoKindOptions = computed(() =>
  PHOTO_KINDS.map((value) => ({ value, title: t(`inventory.photoKinds.${value}`) })),
)
const missingPhotoKinds = computed(() =>
  report.value.required_photo_kinds.filter((k) => !report.value.photos.some((p) => p.kind === k)),
)
async function uploadPhoto() {
  if (!photoFile.value) return
  await run(() =>
    uploadReportPhoto(report.value.id, photoKind.value, photoFile.value!, photoDescription.value),
  )
  photoFile.value = null
  photoDescription.value = ''
  const next = missingPhotoKinds.value[0]
  if (next) photoKind.value = next
}
const removePhoto = (id: number) => run(() => deleteReportPhoto(report.value.id, id))

// --- 3. Kit ----------------------------------------------------------------------------------

function toggleMissing(item: string) {
  const missing = new Set(report.value.missing_items)
  if (missing.has(item)) missing.delete(item)
  else missing.add(item)
  save({ missing_items: [...missing], checklist_done: true })
}

// --- 4. Tests ------------------------------------------------------------------------------

const testsDone = computed(
  () =>
    report.value.test_script.every((item) => report.value.test_results[item]) &&
    !!report.value.functioning,
)
async function setResult(item: string, result: 'pass' | 'fail' | 'na') {
  await save({ test_results: { ...report.value.test_results, [item]: result } })
  // Every check answered: the suggested functioning is taken (the technician may change it)
  const suggestion = report.value.suggestions.functioning
  if (suggestion && !report.value.functioning) await save({ functioning: suggestion })
}

const levelOptions = (domain: 'conservation' | 'functioning' | 'completeness') =>
  GRADE_CODES[domain].map((code) => ({
    value: code,
    title: `${code} · ${t(`inventory.grades.levels.${domain}.${code}`)}`,
  }))

// --- 5. Blocks and customizations ------------------------------------------------------------

const newKind = ref<FindingKind>('access_block')
const newBlockType = ref<BlockType | ''>('')
const newDescription = ref('')
const manualKinds = computed(() =>
  (['access_block', 'customization', 'damage'] as const).map((value) => ({
    value,
    title: t(`inventory.findings.kinds.${value}`),
  })),
)
const blockOptions = computed(() =>
  BLOCK_TYPES.map((value) => ({ value, title: t(`inventory.findings.blockTypes.${value}`) })),
)
async function addManualFinding() {
  await run(() =>
    addFinding(report.value.id, {
      kind: newKind.value,
      block_type: newKind.value === 'access_block' ? newBlockType.value : '',
      description: newDescription.value,
    }),
  )
  newDescription.value = ''
  newBlockType.value = ''
}
const removeFinding = (id: number) => run(() => deleteFinding(report.value.id, id))
const setBlockType = (id: number, blockType: BlockType) =>
  run(() => updateFinding(report.value.id, id, { block_type: blockType }))

// --- 7. Data erasure -------------------------------------------------------------------------

const certResult = ref<'success' | 'failure'>('success')
const certSerial = ref('')
const certFile = ref<File | null>(null)
const diskModel = ref<number | null>(null)
async function saveCertificate() {
  await run(() =>
    addCertificate(report.value.id, {
      result: certResult.value,
      disk_serial: certSerial.value,
      file: certFile.value,
      disk_model: diskModel.value,
    }),
  )
  if (!error.value) {
    certSerial.value = ''
    certFile.value = null
    diskModel.value = null
  }
}

// --- 8. Classification and submitting ----------------------------------------------------------

async function submit() {
  await run(() => submitReport(report.value.id))
  if (!error.value && report.value.status === 'awaiting_approval') {
    notifications.notify(t('inventory.reports.submitted'))
    emit('submitted')
  } else if (!error.value) {
    step.value = 'classification'
  }
}

const money = (value: string | null) => (value ? formatMoney(value, 'BRL', locale.value) : '—')
</script>

<template>
  <div>
    <v-alert
      v-if="report.review_notes"
      type="warning"
      variant="tonal"
      density="compact"
      class="mb-4"
      :title="$t('inventory.reports.returned')"
      data-testid="review-notes"
    >
      {{ report.review_notes }}
    </v-alert>
    <v-alert
      v-if="error"
      type="error"
      variant="tonal"
      density="compact"
      class="mb-4"
      closable
      data-testid="wizard-error"
      @click:close="error = ''"
    >
      {{ error }}
    </v-alert>

    <v-row>
      <v-col cols="12" md="3">
        <v-list density="compact" nav class="pa-0" data-testid="steps">
          <v-list-item
            v-for="(s, index) in steps"
            :key="s.key"
            :active="step === s.key"
            :prepend-icon="s.icon"
            color="primary"
            rounded="lg"
            :data-testid="`step-${s.key}`"
            @click="step = s.key"
          >
            <v-list-item-title
              >{{ index + 1 }}. {{ $t(`inventory.wizard.steps.${s.key}`) }}</v-list-item-title
            >
            <template #append>
              <v-icon
                :icon="s.done ? 'mdi-check-circle' : 'mdi-circle-outline'"
                :color="s.done ? 'success' : undefined"
                size="18"
              />
            </template>
          </v-list-item>
        </v-list>
        <v-progress-linear v-if="saving" indeterminate class="mt-2" />
      </v-col>

      <v-col cols="12" md="9">
        <v-card class="pa-4">
          <!-- 1. Identification -->
          <template v-if="step === 'identification'">
            <div class="text-subtitle-1 font-weight-medium mb-3">
              {{ $t('inventory.wizard.steps.identification') }}
            </div>
            <div v-if="report.asset_detail.serial_status === 'pending'" class="d-flex ga-3 mb-4">
              <v-text-field
                v-model="serial"
                :label="$t('inventory.wizard.pendingSerial')"
                prepend-inner-icon="mdi-barcode-scan"
                autocomplete="off"
                hide-details
                data-testid="wizard-serial"
                @keydown.enter.prevent="saveSerial"
              />
              <v-btn color="primary" @click="saveSerial">{{ $t('common.save') }}</v-btn>
            </div>
            <p v-else class="text-body-2 mb-4">
              {{ $t('inventory.fields.serial') }}:
              <strong>{{ report.asset_detail.serial || $t('inventory.serialStatus.none') }}</strong>
            </p>
            <template v-if="template.length">
              <p class="text-caption text-medium-emphasis mb-2">
                {{ $t('inventory.wizard.specsHint') }}
              </p>
              <SpecValuesInput
                v-model="specs"
                :template="template"
                :asset-class-id="report.asset_detail.asset_model_detail.asset_class"
              />
              <v-btn
                variant="tonal"
                color="primary"
                class="mt-2"
                data-testid="save-specs"
                @click="saveSpecs"
              >
                {{ $t('inventory.wizard.saveSpecs') }}
              </v-btn>
            </template>
          </template>

          <!-- 2. Photos -->
          <template v-else-if="step === 'photos'">
            <div class="text-subtitle-1 font-weight-medium mb-1">
              {{ $t('inventory.wizard.steps.photos') }}
            </div>
            <p class="text-body-2 text-medium-emphasis mb-3">
              {{
                report.required_photo_kinds.length
                  ? $t('inventory.wizard.requiredPhotos', {
                      kinds: report.required_photo_kinds
                        .map((k) => $t(`inventory.photoKinds.${k}`))
                        .join(', '),
                    })
                  : $t('inventory.wizard.noRequiredPhotos')
              }}
            </p>
            <div class="d-flex flex-wrap ga-3 align-start mb-4">
              <v-select
                v-model="photoKind"
                :items="photoKindOptions"
                :label="$t('inventory.wizard.photoKind')"
                density="compact"
                style="max-width: 200px"
              />
              <v-file-input
                v-model="photoFile"
                accept="image/*"
                :label="$t('inventory.triage.photo')"
                prepend-icon=""
                prepend-inner-icon="mdi-camera-outline"
                density="compact"
                style="min-width: 240px"
                data-testid="photo-file"
              />
              <v-text-field
                v-model="photoDescription"
                :label="$t('inventory.findings.description')"
                density="compact"
                style="min-width: 200px"
              />
              <v-btn
                color="primary"
                :disabled="!photoFile"
                data-testid="photo-upload"
                @click="uploadPhoto"
              >
                {{ $t('inventory.attachments.upload') }}
              </v-btn>
            </div>
            <div class="photo-grid">
              <div v-for="p in report.photos" :key="p.id" class="photo">
                <img :src="reportPhotoUrl(report.id, p.id)" :alt="p.name" />
                <div class="d-flex align-center text-caption">
                  <span class="flex-grow-1">{{ $t(`inventory.photoKinds.${p.kind}`) }}</span>
                  <v-btn
                    icon="mdi-delete-outline"
                    size="x-small"
                    variant="text"
                    color="error"
                    @click="removePhoto(p.id)"
                  />
                </div>
              </div>
            </div>
          </template>

          <!-- 3. Kit -->
          <template v-else-if="step === 'kit'">
            <div class="text-subtitle-1 font-weight-medium mb-1">
              {{ $t('inventory.wizard.steps.kit') }}
            </div>
            <p class="text-body-2 text-medium-emphasis mb-3">
              {{ $t('inventory.wizard.kitHint') }}
            </p>
            <v-list v-if="report.kit_checklist.length" density="compact" data-testid="kit-list">
              <v-list-item v-for="entry in report.kit_checklist" :key="entry.item" class="px-0">
                <template #prepend>
                  <v-icon
                    v-if="entry.essential"
                    icon="mdi-star"
                    color="primary"
                    size="16"
                    class="mr-2"
                    :title="$t('assetModels.kitEssential')"
                  />
                </template>
                <v-list-item-title>{{ entry.item }}</v-list-item-title>
                <template #append>
                  <v-btn-toggle
                    :model-value="
                      report.missing_items.includes(entry.item)
                        ? 'missing'
                        : report.checklist_done
                          ? 'present'
                          : null
                    "
                    density="compact"
                    variant="outlined"
                    divided
                  >
                    <v-btn
                      value="present"
                      color="success"
                      size="small"
                      @click="
                        report.missing_items.includes(entry.item)
                          ? toggleMissing(entry.item)
                          : save({ checklist_done: true })
                      "
                    >
                      {{ $t('inventory.reports.present') }}
                    </v-btn>
                    <v-btn
                      value="missing"
                      color="error"
                      size="small"
                      :data-testid="`missing-${entry.item}`"
                      @click="
                        !report.missing_items.includes(entry.item) && toggleMissing(entry.item)
                      "
                    >
                      {{ $t('inventory.reports.missing') }}
                    </v-btn>
                  </v-btn-toggle>
                </template>
              </v-list-item>
            </v-list>
            <p v-else class="text-body-2 text-medium-emphasis">
              {{ $t('inventory.wizard.noKit') }}
            </p>
            <p v-if="report.suggestions.completeness" class="text-body-2 mt-3">
              {{ $t('inventory.wizard.suggested') }}:
              <strong
                >{{ report.suggestions.completeness }} ·
                {{
                  $t(`inventory.grades.levels.completeness.${report.suggestions.completeness}`)
                }}</strong
              >
            </p>
          </template>

          <!-- 4. Tests -->
          <template v-else-if="step === 'tests'">
            <div class="text-subtitle-1 font-weight-medium mb-3">
              {{ $t('inventory.wizard.steps.tests') }}
            </div>
            <v-list v-if="report.test_script.length" density="compact" data-testid="test-list">
              <v-list-item v-for="item in report.test_script" :key="item" class="px-0">
                <v-list-item-title>{{ item }}</v-list-item-title>
                <template #append>
                  <v-btn-toggle
                    :model-value="report.test_results[item] ?? null"
                    density="compact"
                    variant="outlined"
                    divided
                  >
                    <v-btn
                      value="pass"
                      color="success"
                      size="small"
                      @click="setResult(item, 'pass')"
                      >{{ $t('inventory.reports.results.pass') }}</v-btn
                    >
                    <v-btn
                      value="fail"
                      color="error"
                      size="small"
                      @click="setResult(item, 'fail')"
                      >{{ $t('inventory.reports.results.fail') }}</v-btn
                    >
                    <v-btn value="na" size="small" @click="setResult(item, 'na')">{{
                      $t('inventory.reports.results.na')
                    }}</v-btn>
                  </v-btn-toggle>
                </template>
              </v-list-item>
            </v-list>
            <p v-else class="text-body-2 text-medium-emphasis mb-3">
              {{ $t('inventory.wizard.noScript') }}
            </p>
            <v-row dense class="mt-2">
              <v-col cols="12" md="6">
                <v-select
                  :model-value="report.functioning || null"
                  :items="levelOptions('functioning')"
                  :label="$t('inventory.grades.domains.functioning')"
                  :hint="
                    report.suggestions.functioning
                      ? `${$t('inventory.wizard.suggested')}: ${report.suggestions.functioning}`
                      : ''
                  "
                  persistent-hint
                  data-testid="functioning"
                  @update:model-value="save({ functioning: $event })"
                />
              </v-col>
              <v-col cols="12" md="6" class="d-flex align-center">
                <v-checkbox
                  :model-value="report.irreparable"
                  :label="$t('inventory.reports.irreparable')"
                  :disabled="report.functioning !== '3'"
                  hide-details
                  @update:model-value="save({ irreparable: !!$event })"
                />
              </v-col>
              <v-col cols="12">
                <v-textarea
                  :model-value="report.failed_components"
                  :label="$t('inventory.reports.failedComponents')"
                  rows="2"
                  auto-grow
                  @change="
                    save({ failed_components: ($event.target as HTMLTextAreaElement).value })
                  "
                />
              </v-col>
            </v-row>
          </template>

          <!-- 5. Blocks and customizations -->
          <template v-else-if="step === 'blocks'">
            <div class="text-subtitle-1 font-weight-medium mb-1">
              {{ $t('inventory.wizard.steps.blocks') }}
            </div>
            <p class="text-body-2 text-medium-emphasis mb-3">
              {{ $t('inventory.wizard.findingsHint') }}
            </p>
            <div class="d-flex flex-wrap ga-3 align-start mb-4">
              <v-select
                v-model="newKind"
                :items="manualKinds"
                :label="$t('inventory.findings.kind')"
                density="compact"
                style="max-width: 240px"
                data-testid="finding-kind"
              />
              <v-select
                v-if="newKind === 'access_block'"
                v-model="newBlockType"
                :items="blockOptions"
                :label="$t('inventory.findings.blockType')"
                density="compact"
                style="max-width: 240px"
                data-testid="finding-block-type"
              />
              <v-text-field
                v-model="newDescription"
                :label="$t('inventory.findings.description')"
                density="compact"
                style="min-width: 240px"
              />
              <v-btn color="primary" data-testid="finding-add" @click="addManualFinding">{{
                $t('inventory.findings.add')
              }}</v-btn>
            </div>
            <v-table density="compact" data-testid="findings">
              <thead>
                <tr>
                  <th>{{ $t('inventory.findings.kind') }}</th>
                  <th>{{ $t('inventory.findings.description') }}</th>
                  <th class="text-right">{{ $t('inventory.penalties.value') }}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                <tr v-for="f in report.findings" :key="f.id">
                  <td>
                    {{ $t(`inventory.findings.kinds.${f.kind}`) }}
                    <v-select
                      v-if="f.kind === 'access_block'"
                      :model-value="f.block_type || null"
                      :items="blockOptions"
                      :placeholder="$t('inventory.findings.blockType')"
                      density="compact"
                      hide-details
                      @update:model-value="setBlockType(f.id, $event)"
                    />
                  </td>
                  <td>{{ f.item || f.description }}</td>
                  <td class="text-right">{{ money(f.value) }}</td>
                  <td class="text-right">
                    <v-btn
                      v-if="!f.automatic"
                      icon="mdi-delete-outline"
                      size="x-small"
                      variant="text"
                      color="error"
                      @click="removeFinding(f.id)"
                    />
                    <v-chip v-else size="x-small" label>{{
                      $t('inventory.findings.automatic')
                    }}</v-chip>
                  </td>
                </tr>
                <tr v-if="!report.findings.length">
                  <td colspan="4" class="text-medium-emphasis">
                    {{ $t('inventory.reports.noFindings') }}
                  </td>
                </tr>
              </tbody>
            </v-table>
          </template>

          <!-- 6. Cleaning -->
          <template v-else-if="step === 'cleaning'">
            <div class="text-subtitle-1 font-weight-medium mb-3">
              {{ $t('inventory.wizard.steps.cleaning') }}
            </div>
            <v-btn-toggle
              :model-value="report.cleaning"
              mandatory
              color="primary"
              variant="outlined"
              divided
              data-testid="cleaning"
              @update:model-value="save({ cleaning: $event })"
            >
              <v-btn value="standard">{{ $t('inventory.reports.cleanings.standard') }}</v-btn>
              <v-btn value="heavy">{{ $t('inventory.reports.cleanings.heavy') }}</v-btn>
            </v-btn-toggle>
            <p class="text-body-2 text-medium-emphasis mt-3">
              {{ $t('inventory.wizard.cleaningHint') }}
            </p>
          </template>

          <!-- 7. Data erasure -->
          <template v-else-if="step === 'erasure'">
            <div class="text-subtitle-1 font-weight-medium mb-2">
              {{ $t('inventory.wizard.steps.erasure') }}
            </div>
            <v-alert
              v-if="!report.lot_tool"
              type="warning"
              variant="tonal"
              density="compact"
              class="mb-3"
            >
              {{ $t('inventory.wizard.noLotTool') }}
            </v-alert>
            <p v-else class="text-body-2 mb-3" data-testid="lot-tool">
              {{
                $t('inventory.wizard.useTool', {
                  tool: report.lot_tool.tool_label,
                  method: $t(`inventory.erasure.methodNames.${report.lot_tool.method}`),
                })
              }}
            </p>
            <div v-if="report.lot_tool" class="d-flex flex-wrap ga-3 align-start mb-4">
              <v-btn-toggle
                v-model="certResult"
                mandatory
                density="compact"
                variant="outlined"
                divided
              >
                <v-btn value="success" color="success">{{
                  $t('inventory.erasure.results.success')
                }}</v-btn>
                <v-btn value="failure" color="error">{{
                  $t('inventory.erasure.results.failure')
                }}</v-btn>
              </v-btn-toggle>
              <v-text-field
                v-model="certSerial"
                :label="$t('inventory.erasure.diskSerial')"
                density="compact"
                style="max-width: 220px"
              />
              <v-file-input
                v-model="certFile"
                :label="$t('inventory.erasure.certificate')"
                prepend-icon=""
                prepend-inner-icon="mdi-paperclip"
                density="compact"
                style="min-width: 220px"
              />
              <AssetModelPicker
                v-if="certResult === 'failure'"
                v-model="diskModel"
                tracking="unit"
                :label="$t('inventory.erasure.diskModel')"
                density="compact"
                style="min-width: 260px"
              />
              <v-btn color="primary" data-testid="certificate-save" @click="saveCertificate">{{
                $t('common.save')
              }}</v-btn>
            </div>
            <v-list density="compact">
              <v-list-item
                v-for="c in report.erasures"
                :key="c.id"
                :href="c.name ? certificateUrl(report.id, c.id) : undefined"
                target="_blank"
                class="px-0"
              >
                <v-list-item-title>
                  {{ $t(`inventory.erasure.results.${c.result}`) }} · {{ c.tool_label }} ·
                  {{ $t(`inventory.erasure.methodNames.${c.method}`) }}
                </v-list-item-title>
                <v-list-item-subtitle>
                  {{ c.disk_serial || '—' }}
                  <template v-if="c.removed_disk_code">
                    ·
                    {{
                      $t('inventory.erasure.diskRemoved', { code: c.removed_disk_code })
                    }}</template
                  >
                  · {{ c.operator_name }}
                </v-list-item-subtitle>
              </v-list-item>
            </v-list>
          </template>

          <!-- 8. Classification -->
          <template v-else-if="step === 'classification'">
            <div class="text-subtitle-1 font-weight-medium mb-3">
              {{ $t('inventory.wizard.steps.classification') }}
            </div>
            <v-row dense>
              <v-col cols="12" md="4">
                <v-select
                  :model-value="report.conservation || null"
                  :items="levelOptions('conservation')"
                  :label="$t('inventory.grades.domains.conservation')"
                  data-testid="conservation"
                  @update:model-value="save({ conservation: $event })"
                />
              </v-col>
              <v-col cols="12" md="4">
                <v-select
                  :model-value="report.functioning || null"
                  :items="levelOptions('functioning')"
                  :label="$t('inventory.grades.domains.functioning')"
                  :hint="
                    report.suggestions.functioning
                      ? `${$t('inventory.wizard.suggested')}: ${report.suggestions.functioning}`
                      : ''
                  "
                  persistent-hint
                  @update:model-value="save({ functioning: $event })"
                />
              </v-col>
              <v-col cols="12" md="4">
                <v-select
                  :model-value="report.completeness || null"
                  :items="levelOptions('completeness')"
                  :label="$t('inventory.grades.domains.completeness')"
                  :hint="
                    report.suggestions.completeness
                      ? `${$t('inventory.wizard.suggested')}: ${report.suggestions.completeness}`
                      : ''
                  "
                  persistent-hint
                  data-testid="completeness"
                  @update:model-value="save({ completeness: $event })"
                />
              </v-col>
            </v-row>
            <div class="d-flex flex-wrap ga-6 align-center my-4">
              <div>
                <div class="text-caption">{{ $t('inventory.reports.grade') }}</div>
                <div class="text-h4 font-weight-bold" data-testid="grade-preview">
                  {{ report.grade || '—' }}
                </div>
              </div>
              <div>
                <div class="text-caption">{{ $t('inventory.reports.destination') }}</div>
                <div class="text-h6">
                  {{ $t(`inventory.reports.destinations.${report.suggestions.destination}`) }}
                </div>
              </div>
            </div>
            <v-textarea
              :model-value="report.notes"
              :label="$t('customers.fields.notes')"
              rows="2"
              auto-grow
              @change="save({ notes: ($event.target as HTMLTextAreaElement).value })"
            />
            <v-alert
              v-if="report.problems.length"
              type="info"
              variant="tonal"
              density="compact"
              class="mb-3"
              data-testid="problems"
            >
              <div class="font-weight-medium mb-1">{{ $t('inventory.wizard.stillMissing') }}</div>
              <ul class="ml-4">
                <li v-for="p in report.problems" :key="p">{{ p }}</li>
              </ul>
            </v-alert>
            <div class="d-flex justify-end">
              <v-btn
                color="primary"
                size="large"
                prepend-icon="mdi-send-check-outline"
                :disabled="report.problems.length > 0"
                :loading="saving"
                data-testid="submit-report"
                @click="submit"
              >
                {{ $t('inventory.wizard.submit') }}
              </v-btn>
            </div>
          </template>
        </v-card>
      </v-col>
    </v-row>
  </div>
</template>

<style scoped>
.photo-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 12px;
}
.photo img {
  width: 100%;
  height: 110px;
  object-fit: cover;
  border-radius: 8px;
}
</style>
