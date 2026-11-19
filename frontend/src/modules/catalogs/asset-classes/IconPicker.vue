<script setup lang="ts">
/** Choose an icon from ASSET_ICONS: shows the current one and opens a grid to pick another. */
import { ref } from 'vue'
import { ASSET_ICONS } from './icons'

const model = defineModel<string>({ required: true })
withDefaults(defineProps<{ label: string; errorMessages?: string[] }>(), {
  errorMessages: undefined,
})

const open = ref(false)

/** "mdi-dump-truck" → "dump truck" (tooltip / screen readers). */
function iconName(icon: string) {
  return icon.replace(/^mdi-/, '').replace(/-/g, ' ')
}

function choose(icon: string) {
  model.value = icon
  open.value = false
}
</script>

<template>
  <v-input :model-value="model" :error-messages="errorMessages">
    <div class="d-flex align-center ga-3">
      <v-avatar color="primary" variant="tonal" size="56" rounded="lg">
        <v-icon :icon="model" size="32" data-testid="icon-current" />
      </v-avatar>
      <div>
        <div class="text-body-2 text-medium-emphasis mb-1">{{ label }}</div>
        <v-menu v-model="open" :close-on-content-click="false" location="bottom start">
          <template #activator="{ props: activator }">
            <v-btn
              v-bind="activator"
              size="small"
              variant="tonal"
              prepend-icon="mdi-palette-swatch-outline"
              data-testid="icon-choose"
            >
              {{ $t('assetClasses.chooseIcon') }}
            </v-btn>
          </template>
          <v-card max-width="440">
            <v-card-text class="d-flex flex-wrap ga-1">
              <v-btn
                v-for="icon in ASSET_ICONS"
                :key="icon"
                :icon="icon"
                :variant="icon === model ? 'flat' : 'text'"
                :color="icon === model ? 'primary' : undefined"
                :title="iconName(icon)"
                :aria-label="iconName(icon)"
                :aria-pressed="icon === model"
                size="small"
                data-testid="icon-option"
                :data-icon="icon"
                @click="choose(icon)"
              />
            </v-card-text>
          </v-card>
        </v-menu>
      </div>
    </div>
  </v-input>
</template>
