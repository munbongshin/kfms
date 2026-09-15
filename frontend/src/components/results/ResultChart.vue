<template>
  <div class="result-chart">
    <div class="chart-toolbar">
      <p v-if="autoRecommendation?.reasoning" class="recommendation">
        💡 {{ autoRecommendation.reasoning }}
      </p>
      <el-radio-group v-model="selectedChartType" size="small" class="chart-controls">
        <el-radio-button value="bar">
          <el-icon><Histogram /></el-icon>
          Bar
        </el-radio-button>
        <el-radio-button value="line">
          <el-icon><TrendCharts /></el-icon>
          Line
        </el-radio-button>
        <el-radio-button value="pie">
          <el-icon><PieChart /></el-icon>
          Pie
        </el-radio-button>
      </el-radio-group>
    </div>

    <div v-if="chartOption" class="chart-container">
      <v-chart :option="chartOption" :autoresize="true" style="height: 460px" />
    </div>

    <el-empty v-else description="Cannot generate chart for this data" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart, PieChart as PieChartComponent } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
} from 'echarts/components'
import VChart from 'vue-echarts'
import { Histogram, TrendCharts, PieChart } from '@element-plus/icons-vue'
import { useVisualization, type ChartRecommendation } from '../../composables/useVisualization'

// Register ECharts components
use([
  CanvasRenderer,
  BarChart,
  LineChart,
  PieChartComponent,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
])

const props = defineProps<{
  data: any[]
  recommendation?: ChartRecommendation
}>()

const { generateChart, detectBestChartType } = useVisualization()

const selectedChartType = ref<'bar' | 'line' | 'pie'>('bar')

// Auto-detect or use recommendation
const autoRecommendation = computed(() => {
  if (props.recommendation) return props.recommendation
  return detectBestChartType(props.data)
})

// Set initial chart type from recommendation
watch(() => props.recommendation, (newRec) => {
  if (newRec && newRec.chart_type !== 'table') {
    selectedChartType.value = newRec.chart_type as any
  }
}, { immediate: true })

const chartOption = computed(() => {
  return generateChart(
    selectedChartType.value,
    props.data,
    autoRecommendation.value.x_axis,
    autoRecommendation.value.y_axis
  )
})
</script>

<style scoped>
.chart-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.recommendation {
  margin: 0;
  color: #409eff;
  font-size: 14px;
}

.chart-controls {
  display: flex;
  gap: 10px;
  align-items: center;
}

.chart-container {
  min-height: 460px;
}
</style>
