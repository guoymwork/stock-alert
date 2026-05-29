<script setup>
import { ref, onMounted, onUnmounted, watch, computed, shallowRef, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { createChart } from 'lightweight-charts'
import * as api from '../api/stock'
import MacdChart from '../components/MacdChart.vue'
import { useSettingsStore } from '../stores/settings'

const route = useRoute()
const router = useRouter()
const symbol = computed(() => route.params.symbol)
const market = computed(() => route.query.market || '')

const quote = ref(null)
const klineData = ref([])
const macdData = ref([])
const intradayData = ref([])
const intradayMacd = ref([])
const annotations = ref([])
const loading = ref(true)
function isTradingHours() {
  const now = new Date()
  const day = now.getDay()
  if (day === 0 || day === 6) return false
  const h = now.getHours(), m = now.getMinutes()
  const mins = h * 60 + m
  return (mins >= 570 && mins <= 690) || (mins >= 780 && mins <= 900)  // 9:30-11:30, 13:00-15:00
}
const period = ref(isTradingHours() ? 'intraday' : 'daily')   // daily | weekly | monthly | intraday
const chartStyle = ref('candle')
const maEnabled = ref([5, 10, 20])  // active MA periods

const chartWrap = ref(null)
const chart = shallowRef(null)
const mainSeries = shallowRef(null)
const volSeries = shallowRef(null)
const macdChartRef = ref(null)

let suppressSync = false
let refreshTimer = null

// ---- annotation popup ----
const popup = ref({ show: false, x: 0, y: 0, time: '', price: 0, text: '', editId: null })

// ---- panel ----
const settings = useSettingsStore()
const showPanel = ref(false)
const crossoverAlert = ref({ show: false, type: 'none', message: '' })

// ---- calculator ----
const showCalc = ref(false)
const calc = ref({
  amount: 10000,     // 投入金额
  costPrice: 0,      // 买入成本
  currentPrice: 0,   // 当前价格
})

const periodOptions = [
  { label: '分时', value: 'intraday' },
  { label: '日K', value: 'daily' },
  { label: '周K', value: 'weekly' },
  { label: '月K', value: 'monthly' },
]
const styleOptions = [
  { icon: '🕯', value: 'candle', title: '蜡烛图' },
  { icon: '📈', value: 'line', title: '折线图' },
  { icon: '⛰', value: 'area', title: '面积图' },
]

const priceClass = computed(() => {
  if (!quote.value) return 'price-flat'
  const p = quote.value.changePct ?? 0
  return p > 0 ? 'price-up' : p < 0 ? 'price-down' : 'price-flat'
})

// ---- calculator computed ----
const calcShares = computed(() => {
  const { amount, costPrice } = calc.value
  if (!costPrice || costPrice <= 0) return 0
  return Math.floor(amount / costPrice)
})
const calcMarketValue = computed(() => calcShares.value * calc.value.currentPrice)
const calcProfit = computed(() => calcMarketValue.value - calc.value.amount)
const calcProfitPct = computed(() => {
  if (!calc.value.amount) return 0
  return (calcProfit.value / calc.value.amount) * 100
})

function fmt(v, d) { if (v == null) return '--'; const n = Number(v); return n.toFixed(d ?? (Math.abs(n) < 10 ? 3 : 2)) }

function toChartTime(raw) {
  if (!raw) return ''
  if (raw.length === 8 && !raw.includes('-'))
    return `${raw.slice(0,4)}-${raw.slice(4,6)}-${raw.slice(6,8)}`
  return raw
}

// =========== DATA ===========
async function fetchQuote() { try { quote.value = await api.getQuote(symbol.value, market.value) } catch {} }
async function fetchKline() { try { klineData.value = await api.getKlineData(symbol.value, period.value, '', '', market.value) || [] } catch {} }
async function fetchMacd() { try { macdData.value = await api.getMacdData(symbol.value, period.value, '', '', market.value) || [] } catch {} }
async function fetchIntraday() {
  try {
    intradayData.value = await api.getIntradayData(symbol.value, market.value) || []
    const macdRes = await api.getIntradayMacd(symbol.value, market.value)
    intradayMacd.value = macdRes?.macd || (Array.isArray(macdRes) ? macdRes : [])
  } catch {}
}
async function fetchAnnotations() { try { annotations.value = await api.getAnnotations(symbol.value, market.value) || [] } catch {} }
async function fetchAll() {
  loading.value = true
  await Promise.all([fetchQuote(), fetchKline(), fetchMacd(), fetchIntraday(), fetchAnnotations()])
  // sync current price into calculator
  if (quote.value) calc.value.currentPrice = quote.value.price || 0
  loading.value = false
}

// =========== CHART ===========
const baseOpts = {
  layout: { background: { type: 'solid', color: '#0d1117' }, textColor: '#8b949e', fontSize: 11 },
  grid: { vertLines: { color: 'rgba(48,54,61,0.4)' }, horzLines: { color: 'rgba(48,54,61,0.4)' } },
  crosshair: { mode: 0 },
  rightPriceScale: { borderColor: '#30363d', scaleMargins: { top: 0.05, bottom: 0.2 } },
  timeScale: { borderColor: '#30363d', timeVisible: period.value === 'intraday' },
  handleScroll: { vertTouchDrag: false },
}

function toUnix(raw) {
  if (!raw) return undefined
  if (raw.includes('T')) { const ms = new Date(raw.endsWith("Z") ? raw : raw + "Z").getTime(); return isNaN(ms) ? undefined : Math.floor(ms / 1000) }
  return toChartTime(raw)
}

const MA_COLORS = { 5: '#f0c040', 10: '#58a6ff', 20: '#d29922', 60: '#bc8cff', 250: '#f85149' }
const maSeriesMap = {}

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

function toggleMA(p) {
  const idx = maEnabled.value.indexOf(p)
  if (idx >= 0) maEnabled.value.splice(idx, 1)
  else maEnabled.value.push(p)
  rebuildMA()
}

function rebuildMA() {
  // Remove old MA series
  for (const key of Object.keys(maSeriesMap)) {
    try { chart.value?.removeSeries(maSeriesMap[key]) } catch {}
    delete maSeriesMap[key]
  }
  if (!chart.value || period.value === 'intraday') return
  const closes = buildCandles().map(c => c.close)
  if (!closes.length) return
  for (const p of maEnabled.value) {
    const s = chart.value.addLineSeries({
      color: MA_COLORS[p] || '#888', lineWidth: 1, priceLineVisible: false,
      lastValueVisible: false, crosshairMarkerVisible: false,
    })
    const maData = calcMA(closes, p)
    const times = buildCandles()
    const lineData = times.map((c, i) => maData[i] != null ? { time: c.time, value: maData[i] } : null).filter(Boolean)
    if (lineData.length) s.setData(lineData)
    maSeriesMap[p] = s
  }
}

function buildIntradayCandles() {
  return intradayData.value.map(d => ({ time: toUnix(d.timestamp), value: d.close }))
}
function buildIntradayVol() {
  return intradayData.value.map((d, i) => {
    const prev = i > 0 ? intradayData.value[i-1].close : d.open
    return { time: toUnix(d.timestamp), value: d.volume, color: d.close >= prev ? (settings.theme==="cn"?"rgba(248,81,73,0.45)":"rgba(63,185,80,0.45)") : (settings.theme==="cn"?"rgba(63,185,80,0.45)":"rgba(248,81,73,0.45)") }
  })
}
function buildCandles() { return klineData.value.map(d => ({ time: toChartTime(d.timestamp), open: d.open, high: d.high, low: d.low, close: d.close })) }
function buildLine() {
  const src = period.value === 'intraday' ? intradayData.value : klineData.value
  return src.map(d => ({ time: period.value === 'intraday' ? toUnix(d.timestamp) : toChartTime(d.timestamp), value: d.close }))
}
function buildKlineLine() { return klineData.value.map(d => ({ time: toChartTime(d.timestamp), value: d.close })) }
function buildVol() {
  const isIntra = period.value === 'intraday'
  const src = isIntra ? intradayData.value : klineData.value
  return src.map((d, i) => {
    const prev = i > 0 ? src[i-1].close : d.open
    const time = isIntra ? toUnix(d.timestamp) : toChartTime(d.timestamp)
    return { time, value: d.volume, color: d.close >= prev ? (settings.theme==="cn"?"rgba(248,81,73,0.45)":"rgba(63,185,80,0.45)") : (settings.theme==="cn"?"rgba(63,185,80,0.45)":"rgba(248,81,73,0.45)") }
  })
}
function buildMarkers() {
  return annotations.value.map(a => ({
    time: a.time, position: 'belowBar', color: '#d29922', shape: 'circle',
    text: '📌 ' + (a.text.length > 8 ? a.text.slice(0,8) + '…' : a.text),
  })).sort((a, b) => a.time < b.time ? -1 : 1)
}

function refreshMarkers() {
  if (!mainSeries.value) return
  const ts = chart.value?.timeScale()
  const range = ts?.getVisibleLogicalRange()
  mainSeries.value.setMarkers(buildMarkers())
  if (ts && range) ts.setVisibleLogicalRange(range)
}

function getActiveMacd() {
  return period.value === 'intraday' ? intradayMacd.value : macdData.value
}

function initChart() {
  if (!chartWrap.value) return
  if (chart.value) { chart.value.remove(); chart.value = null }

  const isIntra = period.value === 'intraday'
  const w = chartWrap.value.clientWidth
  const h = chartWrap.value.clientHeight || 420
  chart.value = createChart(chartWrap.value, {
    ...baseOpts,
    width: w, height: h,
    timeScale: { ...baseOpts.timeScale, timeVisible: isIntra },
  })

  if (isIntra) {
    // intraday: always area
    mainSeries.value = chart.value.addAreaSeries({
      topColor: 'rgba(88,166,255,0.2)', bottomColor: 'rgba(88,166,255,0.02)',
      lineColor: '#58a6ff', lineWidth: 1.5, crosshairMarkerRadius: 3,
    })
    const c = buildIntradayCandles()
    if (c.length) mainSeries.value.setData(c)
  } else if (chartStyle.value === 'candle') {
    mainSeries.value = chart.value.addCandlestickSeries({
      upColor: settings.theme==="cn"?"#f85149":"#3fb950", downColor: settings.theme==="cn"?"#3fb950":"#f85149", borderUpColor: settings.theme==="cn"?"#f85149":"#3fb950", borderDownColor: settings.theme==="cn"?"#3fb950":"#f85149", wickUpColor: settings.theme==="cn"?"#f85149":"#3fb950", wickDownColor: settings.theme==="cn"?"#3fb950":"#f85149"
    })
    const c = buildCandles(); if (c.length) mainSeries.value.setData(c)
  } else if (chartStyle.value === 'line') {
    mainSeries.value = chart.value.addLineSeries({ color:'#58a6ff', lineWidth:1.5 })
    const p = buildKlineLine(); if (p.length) mainSeries.value.setData(p)
  } else {
    mainSeries.value = chart.value.addAreaSeries({ topColor:'rgba(88,166,255,0.2)', bottomColor:'rgba(88,166,255,0.02)', lineColor:'#58a6ff', lineWidth:1.5 })
    const p = buildKlineLine(); if (p.length) mainSeries.value.setData(p)
  }

  // volume
  volSeries.value = chart.value.addHistogramSeries({ priceFormat:{ type:'volume' }, priceScaleId:'vol' })
  chart.value.priceScale('vol').applyOptions({ scaleMargins:{ top:0.82, bottom:0 } })
  const v = buildVol(); if (v.length) volSeries.value.setData(v)

  // markers (only for kline, not intraday)
  if (!isIntra) refreshMarkers()

  chart.value.timeScale().fitContent()
  if (!isIntra) rebuildMA()

  // click handler
  chart.value.subscribeClick((param) => {
    if (!param.time) return
    const price = param.point?.price ?? mainSeries.value?.coordinateToPrice(param.point?.y)
    if (price == null) return

    // If calculator is open, fill cost price
    if (showCalc.value) {
      calc.value.costPrice = Number(price.toFixed(4))
      return
    }

    // Otherwise annotation logic
    if (isIntra) return // no annotations on intraday
    const existing = annotations.value.find(a => a.time === param.time)
    if (existing) {
      openEditPopup(existing, param.point)
    } else {
      openCreatePopup(param.time, price, param.point)
    }
  })

  // time-range sync: K-line → MACD
  chart.value.timeScale().subscribeVisibleLogicalRangeChange((range) => {
    if (suppressSync || !range) return
    suppressSync = true
    macdChartRef.value?.setVisibleRange(range)
    requestAnimationFrame(() => { suppressSync = false })
  })
}

function openCreatePopup(time, price, point) {
  const rect = chartWrap.value.getBoundingClientRect()
  popup.value = { show:true, x:Math.min(point.x+20, rect.width-240), y:Math.max(point.y-30,10), time, price, text:'', editId:null }
}
function openEditPopup(ann, point) {
  const rect = chartWrap.value.getBoundingClientRect()
  popup.value = { show:true, x:Math.min((point?.x??100)+20, rect.width-240), y:Math.max((point?.y??100)-30,10), time:ann.time, price:ann.price, text:ann.text, editId:ann.id }
}
async function saveAnnotation() {
  const { time, price, text, editId } = popup.value
  if (!text.trim()) return
  if (editId) { try { await api.deleteAnnotation(editId); annotations.value = annotations.value.filter(a => a.id !== editId) } catch {} }
  try {
    const saved = await api.addAnnotation({ symbol:symbol.value, market:market.value, time, price, text:text.trim() })
    annotations.value.push(saved); refreshMarkers()
  } catch {}
  popup.value.show = false
}
async function deleteAnnotation(id) {
  try { await api.deleteAnnotation(id); annotations.value = annotations.value.filter(a => a.id !== id); refreshMarkers(); if (popup.value.editId === id) popup.value.show = false } catch {}
}
function closePopup() { popup.value.show = false }
function openFromPanel(ann) { showPanel.value = false; openEditPopup(ann, null) }

function onMacdRangeChange(range) {
  if (suppressSync || !range || !chart.value) return
  suppressSync = true
  chart.value.timeScale().setVisibleLogicalRange(range)
  requestAnimationFrame(() => { suppressSync = false })
}

function onCrossover(type) {
  if (type === 'none') return
  crossoverAlert.value = {
    show: true,
    type,
    message: type === 'golden_cross' ? '🔴 金叉信号 — DIF 上穿 DEA' : '🟢 死叉信号 — DIF 下穿 DEA',
  }
  // Auto hide after 5s
  setTimeout(() => { crossoverAlert.value.show = false }, 5000)
}

let ro = null

onMounted(async () => {
  await fetchAll()
  nextTick(initChart)
  if (chartWrap.value) {
    ro = new ResizeObserver(() => {
      if (chart.value && chartWrap.value) {
        const ts = chart.value.timeScale()
        const range = ts.getVisibleLogicalRange()
        chart.value.applyOptions({ width: chartWrap.value.clientWidth, height: chartWrap.value.clientHeight })
        if (range) ts.setVisibleLogicalRange(range)
      }
    })
    ro.observe(chartWrap.value)
  }
  refreshTimer = setInterval(() => { fetchQuote().then(() => { if (quote.value) calc.value.currentPrice = quote.value.price || 0 }) }, 30000)
})
onUnmounted(() => { ro?.disconnect(); chart.value?.remove(); clearInterval(refreshTimer) })

watch(symbol, fetchAll)
watch(period, async () => {
  if (period.value === 'intraday') {
    await fetchIntraday()
    // update macd chart with intraday data
    nextTick(() => { initChart(); macdChartRef.value?.setData?.(intradayMacd.value) })
  } else {
    await Promise.all([fetchKline(), fetchMacd(), fetchAnnotations()])
    nextTick(initChart)
  }
})
watch(chartStyle, () => { if (period.value !== 'intraday') nextTick(initChart) })
</script>

<template>
  <div class="detail-page">
    <!-- topbar -->
    <div class="detail-topbar">
      <button class="btn btn-ghost btn-sm" @click="router.push('/')">← 返回</button>

      <div class="topbar-quote" v-if="!loading && quote">
        <span class="tq-name">{{ quote.name }}</span>
        <span class="tq-sym mono">{{ symbol }}</span>
        <span class="tq-price mono" :class="priceClass">{{ fmt(quote.price) }}</span>
        <span class="tq-chg mono" :class="priceClass">
          {{ (quote.change>0?'+':'') + fmt(quote.change) }}
          ({{ (quote.changePct>0?'+':'') + fmt(quote.changePct) }}%)
        </span>
      </div>

      <div class="topbar-tools">
        <!-- 计算器 -->
        <div class="tool-group">
          <button class="tool-btn" :class="{ active: showCalc }" title="做T计算器"
            @click="showCalc = !showCalc; if (showCalc && quote) { calc.currentPrice = quote.price; if (!calc.costPrice) calc.costPrice = quote.price }">🧮</button>
        </div>
        <!-- 便签 -->
        <div class="tool-group" v-if="period !== 'intraday'">
          <button class="tool-btn" :class="{ active: showPanel }" title="便签管理"
            @click="showPanel = !showPanel">
            📌 <span v-if="annotations.length" class="ann-count">{{ annotations.length }}</span>
          </button>
        </div>
        <!-- 图表样式 (only for kline modes) -->
        <div class="tool-group" v-if="period !== 'intraday'">
          <button v-for="s in styleOptions" :key="s.value"
            class="tool-btn" :class="{ active: chartStyle === s.value }"
            :title="s.title" @click="chartStyle = s.value"
          >{{ s.icon }}</button>
        </div>
        <!-- 均线 -->
        <div class="tool-group" v-if="period !== 'intraday'">
          <button v-for="p in [5, 10, 20, 60, 250]" :key="'ma'+p"
            class="tool-btn ma-btn" :class="{ active: maEnabled.includes(p) }"
            :style="maEnabled.includes(p) ? { color: MA_COLORS[p], borderColor: MA_COLORS[p]+'60' } : {}"
            @click="toggleMA(p)"
          >MA{{ p }}</button>
        </div>
        <!-- 周期 -->
        <div class="tool-group">
          <button v-for="p in periodOptions" :key="p.value"
            class="tool-btn" :class="{ active: period === p.value }"
            @click="period = p.value"
          >{{ p.label }}</button>
        </div>
      </div>
    </div>

    <!-- chart area -->
    <div class="chart-area">
      <div class="chart-main" ref="chartWrap">
        <!-- annotation popup -->
        <div v-if="popup.show" class="ann-popup" :style="{ left: popup.x+'px', top: popup.y+'px' }">
          <div class="ann-popup-head"><span>📌 {{ popup.editId ? '编辑便签' : '新建便签' }}</span><button class="ann-close" @click="closePopup">✕</button></div>
          <div class="ann-popup-meta">{{ popup.time }} · {{ fmt(popup.price) }}</div>
          <textarea v-model="popup.text" class="ann-input" placeholder="输入便签内容…" rows="3" autofocus
            @keydown.meta.enter="saveAnnotation" @keydown.ctrl.enter="saveAnnotation" />
          <div class="ann-popup-actions">
            <button v-if="popup.editId" class="btn btn-danger btn-sm" @click="deleteAnnotation(popup.editId)">删除</button>
            <button class="btn btn-primary btn-sm" @click="saveAnnotation">{{ popup.editId ? '更新' : '保存' }}</button>
          </div>
        </div>
      </div>

      <!-- annotation panel -->
      <Transition name="panel">
        <div v-if="showPanel && period !== 'intraday'" class="ann-panel">
          <div class="ann-panel-head"><span>📌 便签</span><button class="ann-close" @click="showPanel=false">✕</button></div>
          <div v-if="!annotations.length" class="ann-panel-empty">点击图表添加便签</div>
          <div v-else class="ann-panel-list">
            <div v-for="a in annotations" :key="a.id" class="ann-item" @click="openFromPanel(a)">
              <div class="ann-item-top"><span>{{ a.time }}</span><span class="mono">{{ fmt(a.price) }}</span></div>
              <div class="ann-item-text">{{ a.text }}</div>
              <button class="ann-del" @click.stop="deleteAnnotation(a.id)">✕</button>
            </div>
          </div>
        </div>
      </Transition>

      <!-- calculator panel -->
      <Transition name="panel">
        <div v-if="showCalc" class="calc-panel">
          <div class="calc-head"><span>🧮 做T计算器</span><button class="ann-close" @click="showCalc=false">✕</button></div>
          <div class="calc-hint" v-if="period !== 'intraday'">点击图表可快速填入买入价</div>
          <div class="calc-form">
            <label class="calc-label">投入金额 (元)</label>
            <input v-model.number="calc.amount" type="number" class="calc-input" />

            <label class="calc-label">买入成本 <span class="calc-label-hint">点击K线带入</span></label>
            <input v-model.number="calc.costPrice" type="number" step="0.01" class="calc-input" :class="{ 'calc-highlight': calc.costPrice }" />

            <label class="calc-label">当前价格</label>
            <input v-model.number="calc.currentPrice" type="number" step="0.01" class="calc-input" />
          </div>
          <div class="calc-result">
            <div class="calc-row calc-shares-row">
              <span>可购买股数</span>
              <span class="mono" style="font-size:18px;font-weight:700;color:var(--accent-blue)">{{ calcShares }} 股</span>
            </div>
            <template v-if="calc.costPrice > 0">
              <div class="calc-divider" />
              <div class="calc-row"><span>当前市值</span><span class="mono">¥{{ fmt(calcMarketValue) }}</span></div>
              <div class="calc-row"><span>成本市值</span><span class="mono">¥{{ fmt(calc.amount) }}</span></div>
              <div class="calc-divider" />
              <div class="calc-row calc-profit-row">
                <span>做T盈亏</span>
                <span class="mono" :class="calcProfit >= 0 ? 'price-up' : 'price-down'">
                  {{ calcProfit >= 0 ? '+' : '' }}¥{{ fmt(calcProfit) }}
                  ({{ calcProfitPct >= 0 ? '+' : '' }}{{ fmt(calcProfitPct) }}%)
                </span>
              </div>
            </template>
          </div>
        </div>
      </Transition>
    </div>

    <!-- MACD -->
    <!-- crossover alert -->
    <Transition name="alert">
      <div v-if="crossoverAlert.show" class="crossover-banner" :class="crossoverAlert.type">
        {{ crossoverAlert.message }}
        <button class="banner-close" @click="crossoverAlert.show = false">✕</button>
      </div>
    </Transition>

    <div class="chart-macd" :class="{ 'macd-golden': crossoverAlert.show && crossoverAlert.type === 'golden_cross', 'macd-death': crossoverAlert.show && crossoverAlert.type === 'death_cross' }">
      <div class="macd-label">MACD</div>
      <MacdChart
        ref="macdChartRef"
        :data="period === 'intraday' ? intradayMacd : macdData"
        :height="130"
        @range-change="onMacdRangeChange" @crossover="onCrossover"
      />
    </div>
  </div>
</template>

<style scoped>
.detail-page { display:flex; flex-direction:column; height:calc(100vh - 44px); overflow:hidden; }

.detail-topbar { display:flex; align-items:center; gap:8px; padding:6px 0; flex-shrink:0; flex-wrap:wrap; }
.topbar-quote { display:flex; align-items:baseline; gap:6px; flex:1; min-width:0; }
.tq-name { font-size:14px; font-weight:600; }
.tq-sym  { font-size:11px; color:var(--text-secondary); }
.tq-price { font-size:17px; font-weight:700; }
.tq-chg { font-size:12px; }
.topbar-tools { display:flex; gap:4px; flex-shrink:0; flex-wrap:wrap; }
.tool-group { display:flex; gap:1px; background:var(--bg-card); border:1px solid var(--border-default); border-radius:5px; padding:2px; }
.tool-btn { padding:3px 9px; font-size:12px; color:var(--text-secondary); background:transparent; border-radius:3px; transition:all .12s; display:flex; align-items:center; gap:3px; }
.tool-btn:hover { color:var(--text-primary); background:var(--bg-surface); }
.tool-btn.active { color:var(--accent-blue); background:rgba(88,166,255,.12); font-weight:600; }
.ann-count { font-size:10px; background:var(--accent-orange); color:#000; border-radius:8px; padding:0 5px; line-height:1.5; font-weight:600; }

.chart-area { flex:1 1 auto; min-height:0; display:flex; gap:0; position:relative; }
.chart-main { flex:1 1 auto; min-width:0; position:relative; background:var(--bg-card); border:1px solid var(--border-default); border-radius:var(--radius); overflow:hidden; }

/* popup */
.ann-popup { position:absolute; z-index:20; width:230px; background:var(--bg-card); border:1px solid var(--accent-orange); border-radius:var(--radius); padding:10px; box-shadow:0 4px 16px rgba(0,0,0,.5); }
.ann-popup-head { display:flex; justify-content:space-between; align-items:center; font-size:12px; font-weight:600; color:var(--accent-orange); margin-bottom:4px; }
.ann-popup-meta { font-size:11px; color:var(--text-muted); font-family:var(--font-mono); margin-bottom:8px; }
.ann-close { background:transparent; color:var(--text-muted); font-size:12px; }
.ann-close:hover { color:var(--text-primary); }
.ann-input { width:100%; padding:6px 8px; font-size:12px; background:var(--bg-primary); border:1px solid var(--border-default); border-radius:4px; color:var(--text-primary); resize:none; }
.ann-input:focus { border-color:var(--accent-blue); outline:none; }
.ann-popup-actions { display:flex; justify-content:flex-end; gap:6px; margin-top:6px; }

/* panel */
.ann-panel { width:210px; flex-shrink:0; background:var(--bg-card); border:1px solid var(--border-default); border-radius:var(--radius); margin-left:6px; display:flex; flex-direction:column; overflow:hidden; }
.ann-panel-head { display:flex; justify-content:space-between; align-items:center; padding:8px 10px; border-bottom:1px solid var(--border-default); font-size:12px; font-weight:600; color:var(--accent-orange); flex-shrink:0; }
.ann-panel-empty { padding:20px 10px; text-align:center; font-size:12px; color:var(--text-muted); }
.ann-panel-list { flex:1; overflow-y:auto; padding:4px; }
.ann-item { position:relative; padding:8px 10px; border-radius:6px; cursor:pointer; transition:background .12s; margin-bottom:2px; }
.ann-item:hover { background:var(--bg-surface); }
.ann-item-top { display:flex; justify-content:space-between; font-size:11px; color:var(--text-secondary); margin-bottom:3px; }
.ann-item-text { font-size:12px; color:var(--text-primary); line-height:1.4; word-break:break-all; }
.ann-del { position:absolute; top:6px; right:6px; background:transparent; color:var(--text-muted); font-size:10px; opacity:0; transition:opacity .15s; }
.ann-item:hover .ann-del { opacity:1; }
.ann-del:hover { color:var(--accent-red); }

/* calculator panel */
.calc-panel { width:230px; flex-shrink:0; background:var(--bg-card); border:1px solid var(--accent-blue); border-radius:var(--radius); margin-left:6px; padding:10px; overflow:hidden; }
.calc-head { display:flex; justify-content:space-between; align-items:center; font-size:13px; font-weight:600; color:var(--accent-blue); margin-bottom:4px; }
.calc-hint { font-size:10px; color:var(--text-muted); margin-bottom:8px; }
.calc-form { display:flex; flex-direction:column; gap:6px; margin-bottom:10px; }
.calc-label { font-size:11px; color:var(--text-secondary); display:flex; justify-content:space-between; }
.calc-label-hint { font-size:10px; color:var(--accent-blue); }
.calc-input { padding:5px 8px; font-size:13px; font-family:var(--font-mono); background:var(--bg-primary); border:1px solid var(--border-default); border-radius:4px; color:var(--text-primary); width:100%; }
.calc-input:focus { border-color:var(--accent-blue); outline:none; }
.calc-highlight { border-color:var(--accent-orange); }
.calc-result { background:var(--bg-primary); border-radius:6px; padding:8px 10px; }
.calc-row { display:flex; justify-content:space-between; font-size:12px; padding:3px 0; color:var(--text-secondary); }
.calc-profit-row { font-weight:600; font-size:13px; }
.calc-divider { height:1px; background:var(--border-default); margin:4px 0; }

/* transitions */
.panel-enter-active, .panel-leave-active { transition:all .2s ease; }
.panel-enter-from, .panel-leave-to { opacity:0; transform:translateX(10px); }

.chart-macd { flex-shrink:0; height:170px; background:var(--bg-card); border:1px solid var(--border-default); border-radius:var(--radius); margin-top:5px; padding:3px 8px; overflow:hidden; }
.macd-label { font-size:11px; color:var(--text-muted); font-weight:500; margin-bottom:1px; }
.crossover-banner {
  flex-shrink: 0; padding: 6px 14px; border-radius: var(--radius);
  font-size: 13px; font-weight: 600; display: flex; align-items: center; justify-content: space-between;
  animation: alert-pulse 1.5s ease-in-out 2;
}
.crossover-banner.golden_cross {
  background: rgba(248,81,73,0.12); border: 1px solid var(--price-up); color: var(--price-up);
}
.crossover-banner.death_cross {
  background: rgba(63,185,80,0.12); border: 1px solid var(--price-down); color: var(--price-down);
}
.banner-close { background: transparent; color: var(--text-muted); font-size: 12px; }
.banner-close:hover { color: var(--text-primary); }
.macd-golden { border-color: var(--price-up) !important; }
.macd-death { border-color: var(--price-down) !important; }
@keyframes alert-pulse { 0%,100% { opacity:1; } 50% { opacity:0.6; } }
.alert-enter-active, .alert-leave-active { transition: all .3s ease; }
.alert-enter-from, .alert-leave-to { opacity:0; transform:translateY(-6px); }
.ma-btn { font-size:10px; padding:2px 6px; min-width:auto; }
.ma-btn.active { font-weight:600; }
</style>
