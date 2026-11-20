<script setup lang="ts">
/**
 * Create (user = null) or edit a user, in tabs: Account (photo — cropped square in the browser,
 * sent after saving —, login, name, email, roles, active, password: required when creating,
 * empty keeps the current one when editing), Personal Data (identity document, nationality,
 * birth date), Employment (employee number, job, manager, phones…) and, for account managers,
 * the business verticals they work in. The server checks the rules (CPF, password, duplicates)
 * and refuses locking yourself out (409, shown here).
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api'
import PhotoField, { type PhotoChange } from '@/components/PhotoField.vue'
import RemoteAutocomplete, { type RemoteOption } from '@/components/RemoteAutocomplete.vue'
import VerticalPicker from '@/modules/catalogs/verticals/VerticalPicker.vue'
import { countryOptions } from '@/utils/countries'
import { useValidationRules } from '@/composables/useValidationRules'
import { useAuthStore } from '@/stores/auth'
import { useNotificationsStore } from '@/stores/notifications'
import {
  ACCOUNT_MANAGER_ROLE,
  allRoles,
  createUser,
  ID_DOCUMENT_TYPES,
  listUsers,
  deleteUserPhoto,
  updateUser,
  uploadUserPhoto,
  userPhotoUrl,
  type Role,
  type User,
  type UserInput,
} from './api'
import { roleName } from './roleText'

const props = defineProps<{ user: User | null }>()
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ saved: [user: User, created: boolean] }>()

const { t, locale } = useI18n()
const rules = useValidationRules()
const auth = useAuthStore()
const notifications = useNotificationsStore()

type Tab = 'account' | 'personal' | 'employment' | 'accountManager'

/** The tab each field is on (to open the tab of the first error). */
const TAB_OF: Record<string, Tab> = {
  username: 'account',
  first_name: 'account',
  last_name: 'account',
  email: 'account',
  roles: 'account',
  password: 'account',
  is_active: 'account',
  id_document_type: 'personal',
  id_document_number: 'personal',
  nationality: 'personal',
  birth_date: 'personal',
  employee_number: 'employment',
  job_title: 'employment',
  department: 'employment',
  work_location: 'employment',
  manager: 'employment',
  hire_date: 'employment',
  phone: 'employment',
  mobile_phone: 'employment',
  verticals: 'accountManager',
}
const FIELDS = Object.keys(TAB_OF)

const emptyForm = () => ({
  username: '',
  first_name: '',
  last_name: '',
  email: '',
  is_active: true,
  roles: [] as number[],
  password: '',
  confirm: '',
  id_document_type: '' as UserInput['id_document_type'],
  id_document_number: '',
  employee_number: '',
  nationality: '',
  birth_date: '' as string | null,
  job_title: '',
  department: '',
  work_location: '',
  manager: null as number | null,
  hire_date: '' as string | null,
  phone: '',
  mobile_phone: '',
  verticals: [] as number[],
})
const form = ref(emptyForm())
const tab = ref<Tab>('account')
const openCount = ref(0) // remounts the pickers on every open
const photo = ref<PhotoChange>(null)
const roles = ref<Role[]>([])
const fieldErrors = ref<Record<string, string[]>>({})
const generalError = ref('')
const saving = ref(false)
const showPassword = ref(false)
const formRef = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(null)

const isEdit = computed(() => props.user !== null)
const isMe = computed(() => props.user !== null && props.user.id === auth.user?.id)
const currentPhoto = computed(() =>
  props.user?.photo_version ? userPhotoUrl(props.user.id, props.user.photo_version) : null,
)
const nameForInitials = computed(
  () => `${form.value.first_name} ${form.value.last_name}`.trim() || form.value.username,
)
const roleItems = computed(() => roles.value.map((r) => ({ value: r.id, title: roleName(r, t) })))

// The verticals tab shows when the user gets the Account Manager role
const accountManagerRoleId = computed(
  () => roles.value.find((r) => r.key === ACCOUNT_MANAGER_ROLE)?.id,
)
const isAccountManager = computed(
  () =>
    accountManagerRoleId.value !== undefined &&
    form.value.roles.includes(accountManagerRoleId.value),
)
watch(isAccountManager, (yes) => {
  if (!yes && tab.value === 'accountManager') tab.value = 'account'
})

const documentTypes = computed(() =>
  ID_DOCUMENT_TYPES.map((value) => ({ value, title: t(`users.documentTypes.${value}`) })),
)
const countries = computed(() =>
  countryOptions(locale.value).map((c) => ({ value: c.code, title: c.name })),
)

// Manager: any other user
const managerInitial = computed<RemoteOption[]>(() =>
  props.user?.manager && props.user.manager_name
    ? [{ value: props.user.manager, title: props.user.manager_name }]
    : [],
)
async function searchUsers(term: string): Promise<RemoteOption[]> {
  const data = await listUsers({ page: 1, pageSize: 20, search: term, ordering: 'first_name' })
  return data.results
    .filter((u) => u.id !== props.user?.id)
    .map((u) => ({ value: u.id, title: u.full_name || u.username }))
}

watch(open, async (isOpen) => {
  if (!isOpen) return
  const user = props.user
  form.value = user
    ? {
        ...emptyForm(),
        username: user.username,
        first_name: user.first_name,
        last_name: user.last_name,
        email: user.email,
        is_active: user.is_active,
        roles: [...user.roles],
        id_document_type: user.id_document_type,
        id_document_number: user.id_document_number,
        employee_number: user.employee_number,
        nationality: user.nationality,
        birth_date: user.birth_date ?? '',
        job_title: user.job_title,
        department: user.department,
        work_location: user.work_location,
        manager: user.manager,
        hire_date: user.hire_date ?? '',
        phone: user.phone,
        mobile_phone: user.mobile_phone,
        verticals: [...user.verticals],
      }
    : emptyForm()
  tab.value = 'account'
  openCount.value += 1
  photo.value = null
  fieldErrors.value = {}
  generalError.value = ''
  showPassword.value = false
  try {
    roles.value = await allRoles()
  } catch {
    generalError.value = t('common.loadError')
  }
})

const passwordRules = computed(() => [
  (v: string) => isEdit.value || !!v || t('validation.required'),
])
const confirmRules = computed(() => [
  (v: string) => v === form.value.password || t('users.passwordMismatch'),
])

/** Send the photo change after the user is saved (a failure keeps the user saved). */
async function applyPhoto(saved: User): Promise<User> {
  try {
    if (photo.value instanceof File) return await uploadUserPhoto(saved.id, photo.value)
    if (photo.value === 'remove' && saved.photo_version) {
      await deleteUserPhoto(saved.id)
      return { ...saved, photo_version: null }
    }
  } catch (error) {
    const messages = error instanceof ApiError ? error.fieldErrors().file : undefined
    notifications.notify(messages?.join(' ') || t('photo.saveError'), 'error')
  }
  return saved
}

/** Show the tab of the first field with an error. */
function showTabOf(fields: string[]) {
  const first = FIELDS.find((field) => fields.includes(field))
  if (first) tab.value = TAB_OF[first]!
}

async function submit() {
  const result = (await formRef.value?.validate()) as
    { valid: boolean; errors?: { id: string | number }[] } | undefined
  if (!result?.valid) {
    // Fields are named after the API fields: open the tab of the first invalid one
    showTabOf((result?.errors ?? []).map((e) => String(e.id)))
    return
  }

  saving.value = true
  fieldErrors.value = {}
  generalError.value = ''
  const f = form.value
  const data: UserInput = {
    username: f.username.trim(),
    first_name: f.first_name.trim(),
    last_name: f.last_name.trim(),
    email: f.email.trim(),
    is_active: f.is_active,
    roles: f.roles,
    id_document_type: f.id_document_type ?? '',
    id_document_number: f.id_document_number.trim(),
    employee_number: f.employee_number.trim(),
    nationality: f.nationality ?? '',
    birth_date: f.birth_date || null,
    job_title: f.job_title.trim(),
    department: f.department.trim(),
    work_location: f.work_location.trim(),
    manager: f.manager,
    hire_date: f.hire_date || null,
    phone: f.phone.trim(),
    mobile_phone: f.mobile_phone.trim(),
    verticals: isAccountManager.value ? f.verticals : [],
  }
  if (form.value.password) data.password = form.value.password
  try {
    let saved = props.user ? await updateUser(props.user.id, data) : await createUser(data)
    saved = await applyPhoto(saved)
    // Your own photo or name changed: the top bar follows
    if (saved.id === auth.user?.id) await auth.refresh()
    emit('saved', saved, !props.user)
    open.value = false
  } catch (error) {
    const errors = error instanceof ApiError ? error.fieldErrors() : {}
    if (Object.keys(errors).some((k) => FIELDS.includes(k))) {
      fieldErrors.value = errors
      showTabOf(Object.keys(errors))
    } else if (error instanceof ApiError && error.status === 409 && error.message) {
      generalError.value = error.message
    } else {
      generalError.value = t('common.saveError')
    }
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <v-dialog v-model="open" max-width="860" scrollable :persistent="saving">
    <v-card :title="isEdit ? $t('users.edit') : $t('users.new')">
      <v-form ref="formRef" @submit.prevent="submit">
        <v-tabs v-model="tab" color="primary" density="compact" class="px-4">
          <v-tab value="account" data-testid="tab-account">{{
            $t('users.formTabs.account')
          }}</v-tab>
          <v-tab value="personal" data-testid="tab-personal">{{
            $t('users.formTabs.personal')
          }}</v-tab>
          <v-tab value="employment" data-testid="tab-employment">{{
            $t('users.formTabs.employment')
          }}</v-tab>
          <v-tab v-if="isAccountManager" value="accountManager" data-testid="tab-account-manager">
            {{ $t('users.formTabs.accountManager') }}
          </v-tab>
        </v-tabs>
        <v-divider />
        <v-card-text style="min-height: 420px">
          <!-- Every tab stays mounted (eager) so the form validates all of them -->
          <v-window v-model="tab">
            <v-window-item value="account" eager>
              <PhotoField
                v-model="photo"
                :name="nameForInitials"
                :current-url="currentPhoto"
                class="mb-4"
              />
              <v-text-field
                v-model="form.username"
                :label="$t('users.fields.username')"
                :rules="[rules.required, rules.maxLength(150)]"
                :error-messages="fieldErrors.username"
                maxlength="150"
                autocomplete="off"
                name="username"
                data-testid="username"
                @update:model-value="fieldErrors.username = []"
              />
              <v-row dense>
                <v-col cols="12" sm="6">
                  <v-text-field
                    v-model="form.first_name"
                    :label="$t('users.fields.firstName')"
                    :rules="[rules.maxLength(150)]"
                    :error-messages="fieldErrors.first_name"
                    maxlength="150"
                    name="first_name"
                    data-testid="first-name"
                  />
                </v-col>
                <v-col cols="12" sm="6">
                  <v-text-field
                    v-model="form.last_name"
                    :label="$t('users.fields.lastName')"
                    :rules="[rules.maxLength(150)]"
                    :error-messages="fieldErrors.last_name"
                    maxlength="150"
                    name="last_name"
                    data-testid="last-name"
                  />
                </v-col>
              </v-row>
              <v-text-field
                v-model="form.email"
                :label="$t('users.fields.email')"
                type="email"
                :rules="[rules.email]"
                :error-messages="fieldErrors.email"
                name="email"
                data-testid="email"
                @update:model-value="fieldErrors.email = []"
              />
              <v-select
                v-model="form.roles"
                :items="roleItems"
                :label="$t('users.fields.roles')"
                :error-messages="fieldErrors.roles"
                multiple
                chips
                closable-chips
                data-testid="roles"
              />
              <v-switch
                v-model="form.is_active"
                :label="$t(form.is_active ? 'users.status.active' : 'users.status.inactive')"
                :hint="$t('users.activeHint')"
                :disabled="isMe"
                persistent-hint
                color="primary"
                inset
                class="mb-2"
                data-testid="is-active"
              />

              <div class="text-subtitle-2 mt-2">{{ $t('users.fields.password') }}</div>
              <p v-if="isEdit" class="text-caption text-medium-emphasis mb-2">
                {{ $t('users.passwordKeep') }}
              </p>
              <v-row dense>
                <v-col cols="12" sm="6">
                  <v-text-field
                    v-model="form.password"
                    :label="$t(isEdit ? 'users.fields.newPassword' : 'users.fields.password')"
                    :type="showPassword ? 'text' : 'password'"
                    :append-inner-icon="showPassword ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
                    :rules="passwordRules"
                    :error-messages="fieldErrors.password"
                    autocomplete="new-password"
                    name="password"
                    data-testid="password"
                    @click:append-inner="showPassword = !showPassword"
                    @update:model-value="fieldErrors.password = []"
                  />
                </v-col>
                <v-col cols="12" sm="6">
                  <v-text-field
                    v-model="form.confirm"
                    :label="$t('users.fields.passwordConfirm')"
                    :type="showPassword ? 'text' : 'password'"
                    :rules="confirmRules"
                    autocomplete="new-password"
                    data-testid="password-confirm"
                  />
                </v-col>
              </v-row>
            </v-window-item>

            <v-window-item value="personal" eager>
              <v-row dense>
                <v-col cols="12" sm="5">
                  <v-select
                    v-model="form.id_document_type"
                    :items="documentTypes"
                    :label="$t('users.fields.idDocumentType')"
                    :error-messages="fieldErrors.id_document_type"
                    clearable
                    name="id_document_type"
                    data-testid="id-document-type"
                    @update:model-value="fieldErrors.id_document_type = []"
                  />
                </v-col>
                <v-col cols="12" sm="7">
                  <v-text-field
                    v-model="form.id_document_number"
                    :label="$t('users.fields.idDocumentNumber')"
                    :error-messages="fieldErrors.id_document_number"
                    maxlength="40"
                    name="id_document_number"
                    data-testid="id-document-number"
                    @update:model-value="fieldErrors.id_document_number = []"
                  />
                </v-col>
                <v-col cols="12" sm="7">
                  <v-autocomplete
                    v-model="form.nationality"
                    :items="countries"
                    :label="$t('users.fields.nationality')"
                    :error-messages="fieldErrors.nationality"
                    clearable
                    name="nationality"
                    data-testid="nationality"
                  />
                </v-col>
                <v-col cols="12" sm="5">
                  <v-text-field
                    v-model="form.birth_date"
                    type="date"
                    :label="$t('users.fields.birthDate')"
                    :error-messages="fieldErrors.birth_date"
                    name="birth_date"
                    data-testid="birth-date"
                    @update:model-value="fieldErrors.birth_date = []"
                  />
                </v-col>
              </v-row>
            </v-window-item>

            <v-window-item value="employment" eager>
              <v-row dense>
                <v-col cols="12" sm="5">
                  <v-text-field
                    v-model="form.employee_number"
                    :label="$t('users.fields.employeeNumber')"
                    :error-messages="fieldErrors.employee_number"
                    maxlength="30"
                    name="employee_number"
                    data-testid="employee-number"
                    @update:model-value="fieldErrors.employee_number = []"
                  />
                </v-col>
                <v-col cols="12" sm="7">
                  <v-text-field
                    v-model="form.job_title"
                    :label="$t('users.fields.jobTitle')"
                    maxlength="100"
                    name="job_title"
                    data-testid="job-title"
                  />
                </v-col>
                <v-col cols="12" sm="6">
                  <v-text-field
                    v-model="form.department"
                    :label="$t('users.fields.department')"
                    maxlength="100"
                    name="department"
                    data-testid="department"
                  />
                </v-col>
                <v-col cols="12" sm="6">
                  <v-text-field
                    v-model="form.work_location"
                    :label="$t('users.fields.workLocation')"
                    maxlength="100"
                    name="work_location"
                    data-testid="work-location"
                  />
                </v-col>
                <v-col cols="12" sm="7">
                  <RemoteAutocomplete
                    :key="openCount"
                    v-model="form.manager"
                    :label="$t('users.fields.manager')"
                    :search="searchUsers"
                    :initial-options="managerInitial"
                    :error-messages="fieldErrors.manager"
                    data-testid="manager"
                  />
                </v-col>
                <v-col cols="12" sm="5">
                  <v-text-field
                    v-model="form.hire_date"
                    type="date"
                    :label="$t('users.fields.hireDate')"
                    :error-messages="fieldErrors.hire_date"
                    name="hire_date"
                    data-testid="hire-date"
                    @update:model-value="fieldErrors.hire_date = []"
                  />
                </v-col>
                <v-col cols="12" sm="6">
                  <v-text-field
                    v-model="form.phone"
                    :label="$t('users.fields.phone')"
                    type="tel"
                    maxlength="30"
                    name="phone"
                    data-testid="phone"
                  />
                </v-col>
                <v-col cols="12" sm="6">
                  <v-text-field
                    v-model="form.mobile_phone"
                    :label="$t('users.fields.mobilePhone')"
                    type="tel"
                    maxlength="30"
                    name="mobile_phone"
                    data-testid="mobile-phone"
                  />
                </v-col>
              </v-row>
            </v-window-item>

            <v-window-item v-if="isAccountManager" value="accountManager" eager>
              <p class="text-body-2 text-medium-emphasis mb-3">
                {{ $t('users.verticalsHint') }}
              </p>
              <VerticalPicker
                :key="openCount"
                v-model="form.verticals"
                multiple
                :initial-options="user?.verticals_detail ?? []"
                :label="$t('users.fields.verticals')"
                :error-messages="fieldErrors.verticals"
                data-testid="verticals"
              />
            </v-window-item>
          </v-window>

          <v-alert
            v-if="generalError"
            type="error"
            variant="tonal"
            density="compact"
            data-testid="general-error"
          >
            {{ generalError }}
          </v-alert>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" :disabled="saving" @click="open = false">
            {{ $t('common.cancel') }}
          </v-btn>
          <v-btn type="submit" color="primary" variant="flat" :loading="saving" data-testid="save">
            {{ $t('common.save') }}
          </v-btn>
        </v-card-actions>
      </v-form>
    </v-card>
  </v-dialog>
</template>
