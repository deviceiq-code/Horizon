<script setup lang="ts">
/** A new container — its kind and the location where it is (read with the gun) — or a
 * container's kind, description and active flag. It moves only by reading it (Movement). */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import FormDialog from '@/components/FormDialog.vue'
import { useValidationRules } from '@/composables/useValidationRules'
import {
  CONTAINER_KINDS,
  createContainer,
  lookupCode,
  updateContainer,
  type Container,
  type ContainerKind,
} from './api'

const props = defineProps<{ container: Container | null }>()
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ saved: [container: Container, created: boolean] }>()

const { t } = useI18n()
const rules = useValidationRules()

const kind = ref<ContainerKind>('box')
const locationCode = ref('')
const description = ref('')
const isActive = ref(true)
const fieldErrors = ref<Record<string, string[]>>({})
const generalError = ref('')
const saving = ref(false)
const formRef = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(null)

const isEdit = computed(() => props.container !== null)
const kindOptions = computed(() =>
  CONTAINER_KINDS.map((value) => ({ value, title: t(`inventory.containerKinds.${value}`) })),
)

watch(open, (isOpen) => {
  if (!isOpen) return
  kind.value = props.container?.kind ?? 'box'
  locationCode.value = ''
  description.value = props.container?.description ?? ''
  isActive.value = props.container?.is_active ?? true
  fieldErrors.value = {}
  generalError.value = ''
})

async function submit() {
  const result = await formRef.value?.validate()
  if (!result?.valid) return
  saving.value = true
  fieldErrors.value = {}
  generalError.value = ''
  try {
    let saved: Container
    if (props.container) {
      saved = await updateContainer(props.container.id, {
        kind: kind.value,
        description: description.value,
        is_active: isActive.value,
      })
    } else {
      let found
      try {
        found = await lookupCode(locationCode.value)
      } catch (error) {
        fieldErrors.value = {
          location: [error instanceof ApiError ? error.message : t('common.saveError')],
        }
        return
      }
      if (found.kind !== 'location') {
        fieldErrors.value = { location: [t('inventory.containers.readLocation')] }
        return
      }
      saved = await createContainer({
        kind: kind.value,
        current_location: found.item.id,
        description: description.value,
      })
    }
    emit('saved', saved, !props.container)
    open.value = false
  } catch (error) {
    const errors = error instanceof ApiError ? error.fieldErrors() : {}
    if (Object.keys(errors).length) fieldErrors.value = errors
    else generalError.value = error instanceof ApiError ? error.message : t('common.saveError')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <FormDialog
    ref="formRef"
    v-model="open"
    :title="isEdit ? $t('inventory.containers.edit') : $t('inventory.containers.new')"
    :subtitle="container?.code ?? null"
    icon="mdi-package-variant"
    max-width="560"
    :persistent="saving"
    @submit="submit"
  >
    <v-row dense>
      <v-col cols="12">
        <v-select
          v-model="kind"
          :items="kindOptions"
          :label="$t('inventory.containers.kind')"
          data-testid="kind"
        />
      </v-col>
      <v-col v-if="!isEdit" cols="12">
        <v-text-field
          v-model="locationCode"
          :label="$t('inventory.containers.where')"
          :hint="$t('inventory.containers.whereHint')"
          persistent-hint
          :rules="[rules.required]"
          :error-messages="fieldErrors.location ?? fieldErrors.current_location"
          prepend-inner-icon="mdi-barcode-scan"
          autocomplete="off"
          autofocus
          data-testid="location"
        />
      </v-col>
      <v-col cols="12">
        <v-text-field
          v-model="description"
          :label="$t('inventory.locations.description')"
          :error-messages="fieldErrors.description"
          maxlength="150"
        />
      </v-col>
      <v-col v-if="isEdit" cols="12">
        <v-switch
          v-model="isActive"
          :label="$t('customers.status.active')"
          :error-messages="fieldErrors.is_active"
          color="primary"
          inset
        />
      </v-col>
    </v-row>

    <v-alert v-if="generalError" type="error" variant="tonal" density="compact">
      {{ generalError }}
    </v-alert>

    <template #actions>
      <v-btn variant="text" :disabled="saving" @click="open = false">
        {{ $t('common.cancel') }}
      </v-btn>
      <v-btn type="submit" color="primary" variant="flat" :loading="saving" data-testid="save">
        {{ $t('common.save') }}
      </v-btn>
    </template>
  </FormDialog>
</template>
