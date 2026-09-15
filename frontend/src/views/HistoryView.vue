<template>
  <div class="history-view">
    <HistoryList />
  </div>
</template>

<script setup lang="ts">
import HistoryList from '../components/history/HistoryList.vue'
</script>

<style scoped>
.history-view {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
</style>
