<script setup lang="ts">
/**
 * The address block of a form (customers, service providers, warehouses): postal code, street,
 * number, complement, district, city and state. In Brazil the postal code is the CEP and the
 * state is picked from the list. `errors` are the server's field errors; `clear` tells the form
 * which field was edited (to clear its error).
 */
import { computed } from 'vue'
import { useValidationRules } from '@/composables/useValidationRules'
import { BRAZILIAN_STATES } from '@/modules/customers/format'

export interface Address {
  postal_code: string
  street: string
  number: string
  complement: string
  district: string
  city: string
  state: string
}

const address = defineModel<Address>({ required: true })
const props = defineProps<{
  /** ISO 3166-1 alpha-2 of the address */
  country: string
  errors?: Record<string, string[] | undefined>
}>()
const emit = defineEmits<{ clear: [field: keyof Address] }>()

const rules = useValidationRules()
const isBrazil = computed(() => props.country === 'BR')
const stateOptions: string[] = [...BRAZILIAN_STATES]

function edited(field: keyof Address) {
  emit('clear', field)
}
</script>

<template>
  <v-row dense>
    <v-col cols="12" sm="4" md="3">
      <v-text-field
        v-model="address.postal_code"
        :label="
          isBrazil ? $t('customers.fields.postalCodeBrazil') : $t('customers.fields.postalCode')
        "
        :rules="[rules.maxLength(10)]"
        :error-messages="errors?.postal_code"
        maxlength="10"
        data-testid="postal-code"
        @update:model-value="edited('postal_code')"
      />
    </v-col>
    <v-col cols="12" sm="8" md="7">
      <v-text-field
        v-model="address.street"
        :label="$t('customers.fields.street')"
        :rules="[rules.maxLength(200)]"
        :error-messages="errors?.street"
        maxlength="200"
        @update:model-value="edited('street')"
      />
    </v-col>
    <v-col cols="4" md="2">
      <v-text-field
        v-model="address.number"
        :label="$t('customers.fields.number')"
        :rules="[rules.maxLength(20)]"
        :error-messages="errors?.number"
        maxlength="20"
        @update:model-value="edited('number')"
      />
    </v-col>
    <v-col cols="8" md="4">
      <v-text-field
        v-model="address.complement"
        :label="$t('customers.fields.complement')"
        :rules="[rules.maxLength(100)]"
        :error-messages="errors?.complement"
        maxlength="100"
        @update:model-value="edited('complement')"
      />
    </v-col>
    <v-col cols="12" md="3">
      <v-text-field
        v-model="address.district"
        :label="$t('customers.fields.district')"
        :rules="[rules.maxLength(100)]"
        :error-messages="errors?.district"
        maxlength="100"
        @update:model-value="edited('district')"
      />
    </v-col>
    <v-col cols="8" md="3">
      <v-text-field
        v-model="address.city"
        :label="$t('customers.fields.city')"
        :rules="[rules.maxLength(100)]"
        :error-messages="errors?.city"
        maxlength="100"
        data-testid="city"
        @update:model-value="edited('city')"
      />
    </v-col>
    <v-col cols="4" md="2">
      <v-autocomplete
        v-if="isBrazil"
        v-model="address.state"
        :items="stateOptions"
        :label="$t('customers.fields.state')"
        :error-messages="errors?.state"
        clearable
        @update:model-value="edited('state')"
      />
      <v-text-field
        v-else
        v-model="address.state"
        :label="$t('customers.fields.state')"
        :rules="[rules.maxLength(50)]"
        :error-messages="errors?.state"
        maxlength="50"
        @update:model-value="edited('state')"
      />
    </v-col>
  </v-row>
</template>
