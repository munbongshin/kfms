<template>
  <div class="database-view">
    <DatabaseManager />
    <ExcelUpload />
  </div>
</template>

<script setup lang="ts">
import DatabaseManager from '../components/database/DatabaseManager.vue'
import ExcelUpload from '../components/excel/ExcelUpload.vue'
</script>

<style scoped>
.database-view {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
</style>
