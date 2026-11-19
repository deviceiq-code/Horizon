<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
</script>

<template>
  <v-container style="max-width: 1100px">
    <v-card>
      <v-card-title>{{ $t('home.welcome', { name: auth.user?.name }) }}</v-card-title>
      <v-card-text>{{ $t('home.text') }}</v-card-text>
    </v-card>
  </v-container>
</template>
