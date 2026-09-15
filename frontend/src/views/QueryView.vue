<template>
  <div class="query-view">
    <QueryInput />
    <SQLPreview />

    <ResultTable v-if="queryStore.queryResults" :results="queryStore.queryResults" />

    <ResultChart
      v-if="queryStore.queryResults && queryStore.queryResults.results.length > 0"
      :data="queryStore.queryResults.results"
    />

    <el-card v-if="!queryStore.queryResults" class="help-card">
      <template #header>
        <span>💡 Example Questions</span>
      </template>
      <ul class="examples">
        <li>"카테고리별 총 매출을 보여줘"</li>
        <li>"월별 매출 추이를 보여줘"</li>
        <li>"30대 고객의 총 구매 금액은?"</li>
        <li>"가장 많이 구매한 고객 TOP 5"</li>
      </ul>
      <el-alert type="info" :closable="false" show-icon>
        <template #title>
          질문을 SQL로 변환한 뒤, 실행 전에 확인을 거칩니다.
        </template>
      </el-alert>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { useQueryStore } from '../stores/query'
import QueryInput from '../components/query/QueryInput.vue'
import SQLPreview from '../components/query/SQLPreview.vue'
import ResultTable from '../components/results/ResultTable.vue'
import ResultChart from '../components/results/ResultChart.vue'

const queryStore = useQueryStore()
</script>

<style scoped>
.query-view {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.help-card {
  margin-top: 20px;
}

.examples {
  list-style: none;
  padding: 0;
  margin: 0 0 20px 0;
}

.examples li {
  padding: 10px;
  margin: 5px 0;
  background: #f0f9ff;
  border-left: 3px solid #409eff;
  border-radius: 4px;
}
</style>
