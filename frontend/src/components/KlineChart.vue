<script setup>
import { ref, onMounted, onUnmounted, watch, shallowRef, nextTick } from 'vue'
import { useSettingsStore } from '../stores/settings'
import { createChart } from 'lightweight-charts'

const props = defineProps({
  data: { type: Array, default: () => [] },
  chartType: { type: String, default: 'daily' },
  height: { type: Number, default: 300 },
  maLines: { type: Array, default: () => [] }  // e.g. [5, 10, 20]
})

const settings = useSettingsStore()
const upColor = () => settings.theme === "cn" ? "#f85149" : "#3fb950"
const downColor = () => settings.theme === "cn" ? "#3fb950" : "#f85149"
const containerRef = ref(null)
const chart = shallowRef(null)
const mainSeries = shallowRef(null)
const volumeSeries = shallowRef(null)
const maSeriesMap = {}

const baseOpts = {
  layout: { background: { type: 'solid', color: 'transparent' }, textColor: '#8b949e', fontSize: 11 },
  grid: { vertLines: { color: 'rgba(48,54,61,0.5)' }, horzLines: { color: 'rgba(48,54,61,0.5)' } },
  crosshair: { mode: 0 },
  rightPriceScale: { borderColor: '#30363d', scaleMargins: { top: 0.1, bottom: 0.25 } },
  timeScale: { borderColor: '#30363d', timeVisible: true, secondsVisible: false },
  handleScroll: { vertTouchDrag: false }
}

function calcMA(closes, period) {
  const result = []
  for (let i = 0; i < closes.length; i++) {
    if (i < period - 1) { result.push(null); continue }
    let sum = 0
    for (let j = i - period + 1; j <= i; j++) sum += closes[j]
    result.push(sum / period)
  }
  return result
}

const MA_COLORS = { 5: '#f0c040', 10: '#58a6ff', 20: '#d29922', 60: '#bc8cff', 250: '#f85149' }

function getTime(item) {
  return item.timestamp || item.time || item.date || ''
}

function toChartTime(raw, isIntraday) {
  if (!raw) return ''
  if (isIntraday) {
    // lightweight-charts needs Unix timestamp (seconds) for intraday
    const ms = new Date(raw.endsWith("Z") ? raw : raw + "Z").getTime()
    if (!isNaN(ms)) return Math.floor(ms / 1000)
    return raw
  }
  // daily/weekly/monthly: must be yyyy-mm-dd
  if (raw.length === 8 && !raw.includes('-'))
    return `${raw.slice(0,4)}-${raw.slice(4,6)}-${raw.slice(6,8)}`
  // ISO string → take date part only
  if (raw.includes('T')) return raw.split('T')[0]
  return raw
}

function build() {
  if (!props.data || props.data.length === 0) return { candles: [], volumes: [] }
  const candles = [], volumes = []
  for (const item of props.data) {
    const isIntraday = props.chartType === 'intraday'
    const time = toChartTime(getTime(item), isIntraday)
    if (isIntraday) {
      candles.push({ time, value: item.close ?? 0 })
    } else {
      candles.push({ time, open: item.open ?? 0, high: item.high ?? 0, low: item.low ?? 0, close: item.close ?? 0 })
    }
    if (item.volume !== undefined) {
      const price = item.close ?? 0
      const prev = candles.length > 1 ? (candles[candles.length - 2]?.close ?? candles[candles.length - 2]?.value ?? price) : price
      volumes.push({ time, value: item.volume, color: price >= prev ? (settings.theme === "cn" ? "rgba(248,81,73,0.5)" : "rgba(63,185,80,0.5)") : (settings.theme === "cn" ? "rgba(63,185,80,0.5)" : "rgba(248,81,73,0.5)") })
    }
  }
  return { candles, volumes }
}

function createChartInstance() {
  if (!containerRef.value || chart.value) return
  const w = containerRef.value.clientWidth || containerRef.value.parentElement?.clientWidth || 300
  chart.value = createChart(containerRef.value, { ...baseOpts, width: w, height: props.height })

  if (props.chartType === 'intraday') {
    mainSeries.value = chart.value.addAreaSeries({
      topColor: 'rgba(88,166,255,0.15)', bottomColor: 'rgba(88,166,255,0.02)',
      lineColor: '#58a6ff', lineWidth: 1.5, crosshairMarkerRadius: 3
    })
  } else {
    mainSeries.value = chart.value.addCandlestickSeries({
      upColor: upColor(), downColor: downColor(),
      borderUpColor: upColor(), borderDownColor: downColor(),
      wickUpColor: upColor(), wickDownColor: downColor()
    })
  }

  volumeSeries.value = chart.value.addHistogramSeries({
    priceFormat: { type: 'volume' }, priceScaleId: 'volume'
  })
  chart.value.priceScale('volume').applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } })

  // MA series
  for (const p of props.maLines) {
    const s = chart.value.addLineSeries({
      color: MA_COLORS[p] || '#888', lineWidth: 1, priceLineVisible: false,
      lastValueVisible: false, crosshairMarkerVisible: false,
    })
    maSeriesMap[p] = s
  }

  const { candles, volumes } = build()
  applyData(candles, volumes)
}

function applyData(candles, volumes) {
  if (candles.length === 0) return
  mainSeries.value.setData(candles)
  if (volumeSeries.value && volumes.length > 0) volumeSeries.value.setData(volumes)
  // MA lines
  const isKline = props.chartType !== 'intraday'
  if (isKline && props.maLines.length > 0) {
    const closes = candles.map(c => c.close ?? c.value ?? 0)
    for (const p of props.maLines) {
      const maData = calcMA(closes, p)
      const lineData = candles.map((c, i) => maData[i] != null ? { time: c.time, value: maData[i] } : null).filter(Boolean)
      if (maSeriesMap[p]) maSeriesMap[p].setData(lineData)
    }
  }
  chart.value.timeScale().fitContent()
}

function updateData() {
  if (!chart.value || !mainSeries.value) return
  const { candles, volumes } = build()
  applyData(candles, volumes)
}

let ro = null

onMounted(() => {
  nextTick(() => {
    // Create chart immediately — container is always in DOM now
    createChartInstance()
    if (containerRef.value) {
      ro = new ResizeObserver(() => {
        if (chart.value && containerRef.value) {
          chart.value.applyOptions({ width: containerRef.value.clientWidth })
        }
      })
      ro.observe(containerRef.value)
    }
  })
})

onUnmounted(() => {
  ro?.disconnect()
  if (chart.value) { chart.value.remove(); chart.value = null }
})

watch(() => props.data, () => {
  if (!chart.value) createChartInstance()
  updateData()
}, { deep: true })

watch(() => props.height, (v) => { chart.value?.applyOptions({ height: v }) })

watch(() => props.maLines, () => {
  // Rebuild MA series
  for (const key of Object.keys(maSeriesMap)) {
    try { chart.value?.removeSeries(maSeriesMap[key]) } catch {}
    delete maSeriesMap[key]
  }
  for (const p of props.maLines) {
    if (!chart.value) break
    const s = chart.value.addLineSeries({
      color: MA_COLORS[p] || '#888', lineWidth: 1, priceLineVisible: false,
      lastValueVisible: false, crosshairMarkerVisible: false,
    })
    maSeriesMap[p] = s
  }
  updateData()
}, { deep: true })
</script>

<template>
  <div class="kline-chart-wrapper">
    <div v-if="!data || data.length === 0" class="chart-empty">
      <span class="chart-empty-text">暂无数据</span>
    </div>
    <div ref="containerRef" class="kline-chart-container" />
  </div>
</template>

<style scoped>
.kline-chart-wrapper { width: 100%; position: relative; contain: layout style paint; }
.kline-chart-container { width: 100%; }
.chart-empty { display:flex; align-items:center; justify-content:center; width:100%; height:100%; min-height:100px; position:absolute; }
.chart-empty-text { font-size:12px; color:var(--text-muted); }</style>
