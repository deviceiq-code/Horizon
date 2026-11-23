<script setup lang="ts">
/** A lot's files: fiscal document, photos of the packages and of damage, photos of assets
 * without a serial number, occurrences' evidence. Opened through the API (signed in). */
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import { useDateFormat } from '@/composables/useDateFormat'
import { useNotificationsStore } from '@/stores/notifications'
import { formatBytes } from '@/utils/bytes'
import {
  ATTACHMENT_KINDS,
  deleteLotAttachment,
  listLotAttachments,
  lotAttachmentUrl,
  uploadLotAttachment,
  type AttachmentKind,
  type Lot,
  type LotAttachment,
} from './api'
import { useInventoryRoles } from './roles'

const props = defineProps<{ lot: Lot }>()

const { t, locale } = useI18n()
const { d } = useDateFormat()
const notifications = useNotificationsStore()
const { canReceive } = useInventoryRoles()

const items = ref<LotAttachment[]>([])
const kind = ref<AttachmentKind>('fiscal_document')
const file = ref<File | null>(null)
const uploading = ref(false)
const kindOptions = ATTACHMENT_KINDS.map((value) => ({
  value,
  title: t(`inventory.attachments.kinds.${value}`),
}))

async function load() {
  items.value = await listLotAttachments(props.lot.id)
}
onMounted(load)

async function upload() {
  if (!file.value) return
  uploading.value = true
  try {
    items.value = await uploadLotAttachment(props.lot.id, file.value, kind.value)
    file.value = null
  } catch (error) {
    notifications.notify(error instanceof ApiError ? error.message : t('common.saveError'), 'error')
  } finally {
    uploading.value = false
  }
}

async function remove(attachment: LotAttachment) {
  try {
    await deleteLotAttachment(props.lot.id, attachment.id)
    await load()
  } catch (error) {
    notifications.notify(
      error instanceof ApiError ? error.message : t('common.deleteError'),
      'error',
    )
  }
}
</script>

<template>
  <div>
    <div
      v-if="canReceive && lot.status !== 'closed'"
      class="d-flex flex-wrap align-start ga-3 mb-4"
    >
      <v-select
        v-model="kind"
        :items="kindOptions"
        :label="$t('inventory.attachments.kind')"
        density="compact"
        style="max-width: 260px"
      />
      <v-file-input
        v-model="file"
        :label="$t('inventory.attachments.file')"
        density="compact"
        prepend-icon=""
        prepend-inner-icon="mdi-paperclip"
        style="max-width: 360px"
        data-testid="attachment-file"
      />
      <v-btn
        color="primary"
        :disabled="!file"
        :loading="uploading"
        prepend-icon="mdi-upload"
        data-testid="attachment-upload"
        @click="upload"
      >
        {{ $t('inventory.attachments.upload') }}
      </v-btn>
    </div>
    <v-list v-if="items.length" density="compact" data-testid="attachments">
      <v-list-item
        v-for="a in items"
        :key="a.id"
        :href="lotAttachmentUrl(lot.id, a.id, true)"
        target="_blank"
        class="px-0"
      >
        <template #prepend>
          <v-icon
            :icon="a.content_type.startsWith('image/') ? 'mdi-image-outline' : 'mdi-file-outline'"
          />
        </template>
        <v-list-item-title>{{ a.name }}</v-list-item-title>
        <v-list-item-subtitle>
          {{ $t(`inventory.attachments.kinds.${a.kind}`) }}
          <template v-if="a.asset_code"> · {{ a.asset_code }}</template>
          · {{ formatBytes(a.size, locale) }} · {{ d(new Date(a.uploaded_at), 'dateTime') }} ·
          {{ a.uploaded_by_name }}
        </v-list-item-subtitle>
        <template v-if="canReceive && lot.status !== 'closed'" #append>
          <v-btn
            icon="mdi-delete-outline"
            size="small"
            variant="text"
            color="error"
            :aria-label="$t('common.delete')"
            @click.prevent.stop="remove(a)"
          />
        </template>
      </v-list-item>
    </v-list>
    <p v-else class="text-body-2 text-medium-emphasis">{{ $t('inventory.attachments.empty') }}</p>
  </div>
</template>
