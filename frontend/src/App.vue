<template>
  <!-- Nothing is drawn until the first navigation (and its sign-in check) has
       settled, so the shell never asks the server for data it may not see. -->
  <template v-if="ready">
    <router-view v-if="$route.meta.public" />
    <AppShell v-else>
      <router-view />
    </AppShell>
  </template>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import AppShell from './components/layout/AppShell.vue'

const ready = ref(false)
useRouter().isReady().then(() => {
  ready.value = true
})
</script>

<style>
#app {
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}
</style>
