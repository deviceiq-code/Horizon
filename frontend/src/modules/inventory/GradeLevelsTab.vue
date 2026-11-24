<script setup lang="ts">
/** The grade code's three domains — Conservation (A–D), Functioning (1, 2, 3, 0) and
 * Completeness (C, P, I) — and what each level means. Codes are fixed (the grade "B1C" always
 * has the same shape); names and descriptions are edited by supervisors. */
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import { useNotificationsStore } from '@/stores/notifications'
import { listGradeLevels, updateGradeLevel, type GradeDomain, type GradeLevel } from './api'
import { useInventoryRoles } from './roles'

const { t } = useI18n()
const notifications = useNotificationsStore()
const { isSupervisor } = useInventoryRoles()

const levels = ref<GradeLevel[]>([])
const DOMAINS: GradeDomain[] = ['conservation', 'functioning', 'completeness']
const byDomain = computed(() =>
  Object.fromEntries(
    DOMAINS.map((domain) => [
      domain,
      levels.value.filter((l) => l.domain === domain).sort((a, b) => a.order - b.order),
    ]),
  ),
)

onMounted(async () => {
  levels.value = await listGradeLevels()
})

async function save(level: GradeLevel) {
  try {
    const saved = await updateGradeLevel(level.id, {
      name: level.name,
      description: level.description,
    })
    Object.assign(level, saved)
    notifications.notify(t('inventory.grades.saved'))
  } catch (error) {
    notifications.notify(error instanceof ApiError ? error.message : t('common.saveError'), 'error')
  }
}
</script>

<template>
  <div>
    <v-alert type="info" variant="tonal" class="mb-4" density="compact">
      {{ $t('inventory.grades.explain') }}
    </v-alert>
    <v-row>
      <v-col v-for="(domain, index) in DOMAINS" :key="domain" cols="12" md="4">
        <v-card class="pa-4 h-100" :data-testid="`domain-${domain}`">
          <div class="text-subtitle-1 font-weight-medium">
            {{ index + 1 }}ª · {{ $t(`inventory.grades.domains.${domain}`) }}
          </div>
          <p class="text-body-2 text-medium-emphasis mb-3">
            {{ $t(`inventory.grades.domainHints.${domain}`) }}
          </p>
          <div v-for="level in byDomain[domain]" :key="level.id" class="d-flex ga-3 mb-3">
            <v-avatar color="primary" variant="tonal" size="36" rounded class="font-weight-bold">
              {{ level.code }}
            </v-avatar>
            <div class="flex-grow-1">
              <v-text-field
                v-model="level.name"
                density="compact"
                hide-details
                :readonly="!isSupervisor"
                variant="underlined"
                class="font-weight-medium"
                @change="save(level)"
              />
              <v-textarea
                v-model="level.description"
                density="compact"
                rows="1"
                auto-grow
                hide-details
                :readonly="!isSupervisor"
                variant="plain"
                class="text-body-2"
                @change="save(level)"
              />
            </div>
          </div>
        </v-card>
      </v-col>
    </v-row>
  </div>
</template>
