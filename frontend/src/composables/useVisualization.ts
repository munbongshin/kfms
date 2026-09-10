/**
 * Visualization Composable
 * Generates ECharts configurations for different chart types
 */
import type { EChartsOption } from 'echarts'

export interface ChartRecommendation {
  chart_type: 'table' | 'bar' | 'line' | 'pie'
  x_axis?: string
  y_axis?: string
  reasoning?: string
}

export function useVisualization() {
  function generateBarChart(
    data: any[],
    xAxis: string,
    yAxis: string
  ): EChartsOption {
    return {
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'shadow'
        }
      },
      xAxis: {
        type: 'category',
        data: data.map(d => d[xAxis]),
        axisLabel: {
          rotate: 45,
          interval: 0
        }
      },
      yAxis: {
        type: 'value'
      },
      series: [
        {
          type: 'bar',
          data: data.map(d => d[yAxis]),
          itemStyle: {
            color: '#409eff'
          }
        }
      ],
      grid: {
        bottom: 100,
        left: 60,
        right: 30
      }
    }
  }

  function generateLineChart(
    data: any[],
    xAxis: string,
    yAxis: string
  ): EChartsOption {
    return {
      tooltip: {
        trigger: 'axis'
      },
      xAxis: {
        type: 'category',
        data: data.map(d => d[xAxis]),
        boundaryGap: false
      },
      yAxis: {
        type: 'value'
      },
      series: [
        {
          type: 'line',
          data: data.map(d => d[yAxis]),
          smooth: true,
          itemStyle: {
            color: '#67c23a'
          },
          areaStyle: {
            color: 'rgba(103, 194, 58, 0.2)'
          }
        }
      ],
      grid: {
        left: 60,
        right: 30,
        bottom: 60
      }
    }
  }

  function generatePieChart(
    data: any[],
    nameField: string,
    valueField: string
  ): EChartsOption {
    return {
      tooltip: {
        trigger: 'item',
        formatter: '{a} <br/>{b}: {c} ({d}%)'
      },
      legend: {
        orient: 'vertical',
        right: 10,
        top: 'center',
        type: 'scroll'
      },
      series: [
        {
          name: valueField,
          type: 'pie',
          radius: ['40%', '70%'],
          avoidLabelOverlap: false,
          itemStyle: {
            borderRadius: 10,
            borderColor: '#fff',
            borderWidth: 2
          },
          label: {
            show: false,
            position: 'center'
          },
          emphasis: {
            label: {
              show: true,
              fontSize: 20,
              fontWeight: 'bold'
            }
          },
          labelLine: {
            show: false
          },
          data: data.map(d => ({
            name: d[nameField],
            value: d[valueField]
          }))
        }
      ]
    }
  }

  function generateChart(
    chartType: string,
    data: any[],
    xAxis?: string,
    yAxis?: string
  ): EChartsOption | null {
    if (!data || data.length === 0) return null

    // Auto-detect axes if not provided
    if (!xAxis || !yAxis) {
      const columns = Object.keys(data[0])
      if (columns.length < 2) return null

      xAxis = xAxis || columns[0]
      yAxis = yAxis || columns[1]
    }

    switch (chartType) {
      case 'bar':
        return generateBarChart(data, xAxis, yAxis)
      case 'line':
        return generateLineChart(data, xAxis, yAxis)
      case 'pie':
        return generatePieChart(data, xAxis, yAxis)
      default:
        return null
    }
  }

  function detectBestChartType(data: any[]): ChartRecommendation {
    if (!data || data.length === 0) {
      return { chart_type: 'table' }
    }

    const columns = Object.keys(data[0])
    if (columns.length < 2) {
      return { chart_type: 'table' }
    }

    const firstCol = columns[0]
    const secondCol = columns[1]

    // Check if first column looks like dates/time
    const firstVal = String(data[0][firstCol])
    if (firstVal.match(/\d{4}-\d{2}-\d{2}/) || firstVal.match(/\d{4}\/\d{2}/)) {
      return {
        chart_type: 'line',
        x_axis: firstCol,
        y_axis: secondCol,
        reasoning: 'Time series data detected'
      }
    }

    // Check if second column is numeric
    const isNumeric = data.every(row => !isNaN(Number(row[secondCol])))

    if (isNumeric) {
      // If few unique values in first column, use pie
      const uniqueFirst = new Set(data.map(d => d[firstCol]))
      if (uniqueFirst.size <= 10) {
        return {
          chart_type: 'pie',
          x_axis: firstCol,
          y_axis: secondCol,
          reasoning: 'Categorical distribution with few categories'
        }
      }

      // Otherwise bar chart
      return {
        chart_type: 'bar',
        x_axis: firstCol,
        y_axis: secondCol,
        reasoning: 'Categorical comparison'
      }
    }

    return { chart_type: 'table' }
  }

  return {
    generateChart,
    detectBestChartType,
    generateBarChart,
    generateLineChart,
    generatePieChart
  }
}
