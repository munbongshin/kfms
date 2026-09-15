<template>
  <div class="database-view">
    <DatabaseManager />
  </div>
</template>

<script setup lang="ts">
import DatabaseManager from '../components/database/DatabaseManager.vue'
</script>

<style scoped>
.database-view {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
</style>
