<script setup>
import { ref, onMounted, onUnmounted, watch, shallowRef, nextTick } from 'vue'
import { useSettingsStore } from '../stores/settings'
import { createChart } from 'lightweight-charts'
import { detectCrossover } from '../utils/indicators'

const props = defineProps({
  data: { type: Array, default: () => [] },
  height: { type: Number, default: 150 }
})

const emit = defineEmits(['crossover', 'range-change'])

const settings = useSettingsStore()
const containerRef = ref(null)
const chart = shallowRef(null)
const difSeries = shallowRef(null)
const deaSeries = shallowRef(null)
const macdSeries = shallowRef(null)

const baseOpts = {
  layout: { background: { type: 'solid', color: 'transparent' }, textColor: '#8b949e', fontSize: 11 },
  grid: { vertLines: { color: 'rgba(48,54,61,0.5)' }, horzLines: { color: 'rgba(48,54,61,0.5)' } },
  crosshair: { mode: 0 },
  rightPriceScale: { borderColor: '#30363d' },
  timeScale: { borderColor: '#30363d', timeVisible: false },
  handleScroll: { vertTouchDrag: false },
}

function getTime(item) { return item.timestamp || item.time || item.date || '' }

function toChartTime(raw) {
  if (!raw) return ''
  // ISO datetime with T → Unix timestamp (lightweight-charts needs this for intraday)
  if (raw.includes('T')) {
    const ms = new Date(raw.endsWith("Z") ? raw : raw + "Z").getTime()
    if (!isNaN(ms)) return Math.floor(ms / 1000)
  }
  // YYYYMMDD → yyyy-mm-dd
  if (raw.length === 8 && !raw.includes('-'))
    return `${raw.slice(0,4)}-${raw.slice(4,6)}-${raw.slice(6,8)}`
  return raw
}

function build() {
  if (!props.data || props.data.length === 0) return { dif: [], dea: [], hist: [] }
  const dif = [], dea = [], hist = []
  for (const item of props.data) {
    const time = toChartTime(getTime(item))
    dif.push({ time, value: item.dif ?? 0 })
    dea.push({ time, value: item.dea ?? 0 })
    hist.push({ time, value: item.macd ?? 0, color: (item.macd ?? 0) >= 0 ? (settings.theme === "cn" ? "rgba(248,81,73,0.8)" : "rgba(63,185,80,0.8)") : (settings.theme === "cn" ? "rgba(63,185,80,0.8)" : "rgba(248,81,73,0.8)") })
  }
  return { dif, dea, hist }
}

function createChartInstance() {
  if (!containerRef.value || chart.value) return
  const w = containerRef.value.clientWidth || 300
  chart.value = createChart(containerRef.value, { ...baseOpts, width: w, height: props.height })

  difSeries.value = chart.value.addLineSeries({ color: '#58a6ff', lineWidth: 1, priceLineVisible: false, lastValueVisible: false })
  deaSeries.value = chart.value.addLineSeries({ color: '#d29922', lineWidth: 1, priceLineVisible: false, lastValueVisible: false })
  macdSeries.value = chart.value.addHistogramSeries({
    priceFormat: { type: 'price', precision: 4, minMove: 0.0001 },
    lastValueVisible: false, priceLineVisible: false
  })

  const { dif, dea, hist } = build()
  if (dif.length > 0) {
    difSeries.value.setData(dif)
    deaSeries.value.setData(dea)
    macdSeries.value.setData(hist)
    chart.value.timeScale().fitContent()
  }

  // Emit range change for time sync
  chart.value.timeScale().subscribeVisibleLogicalRangeChange((range) => {
    if (range) emit('range-change', range)
  })
}

function updateData() {
  if (!chart.value || !difSeries.value) return
  const { dif, dea, hist } = build()
  if (dif.length === 0) return
  difSeries.value.setData(dif)
  deaSeries.value.setData(dea)
  macdSeries.value.setData(hist)
  chart.value.timeScale().fitContent()
}

/** Called by parent to sync visible range */
function setVisibleRange(range) {
  if (chart.value) {
    chart.value.timeScale().setVisibleLogicalRange(range)
  }
}

let ro = null

onMounted(() => {
  nextTick(() => {
    createChartInstance()
    if (containerRef.value) {
      ro = new ResizeObserver(() => {
        if (chart.value && containerRef.value)
          chart.value.applyOptions({ width: containerRef.value.clientWidth })
      })
      ro.observe(containerRef.value)
    }
  })
})

onUnmounted(() => {
  ro?.disconnect()
  if (chart.value) { chart.value.remove(); chart.value = null }
})

watch(() => props.data, (newData) => {
  if (!chart.value) createChartInstance()
  updateData()
  const cross = detectCrossover(newData)
  if (cross !== 'none') emit('crossover', cross)
}, { deep: true })

watch(() => props.height, (v) => { chart.value?.applyOptions({ height: v }) })

defineExpose({ setVisibleRange })
</script>

<template>
  <div class="macd-chart-wrapper">
    <div v-if="!data || data.length === 0" class="chart-empty">
      <span class="chart-empty-text">暂无 MACD 数据</span>
    </div>
    <div ref="containerRef" class="macd-chart-container" />
  </div>
</template>

<style scoped>
.macd-chart-wrapper { width:100%; position:relative; contain:layout style paint; }
.macd-chart-container { width:100%; }
.chart-empty { display:flex; align-items:center; justify-content:center; width:100%; height:100%; min-height:80px; position:absolute; }
.chart-empty-text { font-size:12px; color:var(--text-muted); }</style>
