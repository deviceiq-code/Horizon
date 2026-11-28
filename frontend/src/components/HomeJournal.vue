<script setup lang="ts">
/**
 * The Home's journal, in lines (no cards): first the Data Journal — what happened in the period of the user's preference (today, 7 or 30
 * days — Settings › Appearance) in the modules they may open, counts only, each opening its
 * module —, then the System Journal — what is new in each version (all users). Versions newer than the last one the
 * user saw here are marked "New" (`ui_state.lastSeenRelease`). Each part can be hidden
 * (Settings › Appearance › Home: `show_data_journal`, `show_system_journal`), and they go
 * one under the other or side by side (`journal_layout`).
 */
import { computed, onMounted, ref } from 'vue'
import { useDateFormat } from '@/composables/useDateFormat'
import { eventModule, getJournal, type Journal } from '@/journal'
import { usePreferencesStore } from '@/stores/preferences'

const preferences = usePreferencesStore()
const { d } = useDateFormat()

const journal = ref<Journal | null>(null)
const failed = ref(false)
/** The last version seen before this visit (the newer ones are "New") */
const seenBefore = ref<string | undefined>(undefined)

const number = (version: string) => version.split('.').map((part) => Number(part) || 0)
function isNewer(version: string, than: string | undefined): boolean {
  if (!than) return true
  const a = number(version)
  const b = number(than)
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    if ((a[i] ?? 0) !== (b[i] ?? 0)) return (a[i] ?? 0) > (b[i] ?? 0)
  }
  return false
}

onMounted(async () => {
  // Both parts hidden (Settings › Appearance › Home): nothing to ask for
  if (!preferences.showDataJournal && !preferences.showSystemJournal) return
  try {
    journal.value = await getJournal()
  } catch {
    failed.value = true
    return
  }
  seenBefore.value = preferences.uiState.lastSeenRelease
  const newest = journal.value.releases[0]?.version
  // Seen only when the System Journal is shown
  if (preferences.showSystemJournal && newest && isNewer(newest, seenBefore.value)) {
    preferences.saveUiState((state) => ({ ...state, lastSeenRelease: newest }))
  }
})

const events = computed(() =>
  (journal.value?.events ?? []).map((event) => {
    const module = eventModule(event.key)
    return {
      ...event,
      icon: module?.icon ?? 'mdi-circle-small',
      to: module ? { name: module.name } : undefined,
    }
  }),
)
</script>

<template>
  <section
    v-if="preferences.showDataJournal || preferences.showSystemJournal"
    :class="['journal', `journal--${preferences.journalLayout}`]"
    data-testid="journal"
  >
    <!-- Data Journal: what happened lately -->
    <div v-if="preferences.showDataJournal" class="journal-part" data-testid="data-journal">
      <div class="d-flex align-baseline ga-2 mb-2">
        <h2 class="journal-title">
          <v-icon icon="mdi-notebook-outline" color="primary" size="small" class="mr-1" />
          {{ $t('home.journal.dataTitle') }}
        </h2>
        <span v-if="journal" class="text-body-2 text-medium-emphasis">
          {{ $t(`home.journal.periods.${journal.days}`) }}
        </span>
      </div>
      <v-alert v-if="failed" type="error" variant="tonal" density="compact" class="mb-6">
        {{ $t('common.loadError') }}
      </v-alert>
      <v-progress-linear v-else-if="!journal" indeterminate class="mb-6" />
      <p v-else-if="!events.length" class="text-medium-emphasis mb-6" data-testid="journal-empty">
        {{ $t('home.journal.empty') }}
      </p>
      <div v-else class="mb-6" data-testid="journal-events">
        <component
          :is="event.to ? 'RouterLink' : 'div'"
          v-for="event in events"
          :key="event.key"
          :to="event.to"
          class="journal-line"
          :data-testid="`journal-event-${event.key}`"
        >
          <v-icon :icon="event.icon" size="small" class="text-medium-emphasis" />
          <span>{{ $t(`home.journal.events.${event.key}`, event.count) }}</span>
        </component>
      </div>
    </div>

    <!-- System Journal: what is new in each version -->
    <div v-if="preferences.showSystemJournal" class="journal-part" data-testid="system-journal">
      <div class="d-flex align-baseline ga-2 mb-2">
        <h2 class="journal-title">
          <v-icon icon="mdi-rocket-launch-outline" color="primary" size="small" class="mr-1" />
          {{ $t('home.journal.systemTitle') }}
        </h2>
        <span v-if="journal?.version" class="text-body-2 text-medium-emphasis">
          {{ $t('home.journal.current', { version: journal.version }) }}
        </span>
      </div>
      <div v-if="journal">
        <div
          v-for="release in journal.releases"
          :key="release.version"
          class="journal-release"
          :data-testid="`release-${release.version}`"
        >
          <div class="d-flex align-center ga-2 mb-1">
            <span class="font-weight-medium">
              {{ $t('home.journal.version', { version: release.version }) }}
            </span>
            <span class="text-caption text-medium-emphasis">
              {{ d(new Date(`${release.date}T12:00:00`), 'short') }}
            </span>
            <v-chip
              v-if="isNewer(release.version, seenBefore)"
              size="x-small"
              color="primary"
              variant="flat"
              data-testid="release-new"
            >
              {{ $t('home.journal.new') }}
            </v-chip>
          </div>
          <ul class="text-body-2 pl-5">
            <li v-for="(note, i) in release.notes" :key="i">{{ note }}</li>
          </ul>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
/* Vertical: one under the other; horizontal: side by side (stacked on narrow screens) */
.journal--horizontal {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 420px), 1fr));
  gap: 0 40px;
  align-items: start;
}
.journal-title {
  font-size: 1.125rem;
  font-weight: 600;
  margin: 0;
}
/* Data Journal: plain lines, no separators */
.journal-line {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 6px 4px;
  border-radius: 8px;
  color: inherit;
  text-decoration: none;
}
a.journal-line:hover {
  background: rgba(var(--v-theme-on-surface), 0.04);
}
/* System Journal: a blank line after each note, for reading */
.journal-release {
  padding: 4px 4px 12px;
}
.journal-release ul li + li {
  margin-top: 1.25em;
}
</style>
