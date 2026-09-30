<template>
  <!-- Nothing is drawn until the first navigation (and its sign-in check) has
       settled, so the shell never asks the server for data it may not see. -->
  <el-config-provider :locale="elementLocale">
    <template v-if="ready">
      <router-view v-if="$route.meta.public" />
      <AppShell v-else>
        <router-view />
      </AppShell>
    </template>
  </el-config-provider>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import elementEn from 'element-plus/es/locale/lang/en'
import elementKo from 'element-plus/es/locale/lang/ko'
import AppShell from './components/layout/AppShell.vue'
import { locale, t } from './i18n'

// Element Plus's own texts (empty tables, pagination, date pickers, confirm buttons).
const elementLocale = computed(() => (locale.value === 'en' ? elementEn : elementKo))

// The browser tab names the screen in the chosen language.
const route = useRoute()
watch(
  [locale, () => route.meta.title],
  () => {
    document.title = `${route.meta.title ? t(String(route.meta.title)) : 'KFMS'} - Knowledge Flow Management System`
  },
  { immediate: true }
)

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
