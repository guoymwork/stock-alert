<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useStockStore } from '../stores/stock'
import { useSettingsStore } from '../stores/settings'
import { detectCrossover } from '../utils/indicators'
import StockCard from '../components/StockCard.vue'
import AddStockModal from '../components/AddStockModal.vue'
import AppHeader from '../components/AppHeader.vue'
import MiniSparkline from '../components/MiniSparkline.vue'

const store = useStockStore()
const settings = useSettingsStore()

const showModal = ref(false)
const showSettings = ref(false)
const initialized = ref(false)
const viewMode = ref(localStorage.getItem('viewMode') || 'grid')
const listSort = ref({ key: 'changePct', dir: 'desc' })  // key: changePct|price|volume|high|low, dir: asc|desc
const showDock = ref(false)
const mutedSymbols = ref(JSON.parse(localStorage.getItem('mutedSymbols') || '[]'))
const priceAlerts = ref(JSON.parse(localStorage.getItem('priceAlerts') || '{}'))  // { symbol: { above: number|null, below: number|null } }
let refreshTimer = null

// ---- drag ----
const dragIdx = ref(-1)
const overIdx = ref(-1)
let isDragging = false

async function init() {
  await store.fetchWatchlist()
  initialized.value = true
  if (store.watchlist.length > 0) {
    await Promise.all([store.fetchAllQuotes(), store.fetchAllIntraday()])
  }
}

function scheduleRefresh() {
  clearTimeout(refreshTimer)
  refreshTimer = setTimeout(async () => {
    if (store.watchlist.length > 0) {
      await Promise.all([store.fetchAllQuotes(), store.fetchAllIntraday()])
      checkPriceAlerts()
    }
    scheduleRefresh()
  }, settings.refreshInterval)
}

async function onAdded(codes) { await store.addStocks(codes); await store.fetchAllIntraday() }
const confirmDel = ref({ show: false, symbol: '', market: '' })
function onRemove(symbol, market) { confirmDel.value = { show: true, symbol, market: market || '' } }
async function doRemove() { await store.removeStock(confirmDel.value.symbol, confirmDel.value.market); confirmDel.value = { show: false, symbol: '', market: '' } }

const highlightSymbol = ref(null)

function scrollCardIntoView(symbol) {
  highlightSymbol.value = symbol
  const el = document.querySelector(`.card-wrapper[data-symbol="${symbol}"]`)
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
}
function clearHighlight() { highlightSymbol.value = null }

const marqueeText = computed(() => {
  if (!alertStocks.value.length) return ''
  return alertStocks.value.map(item => {
    const name = item.quote?.name || item.symbol
    if (item.limitType === 'limit_up') return '🔒 ' + name + '(' + item.symbol + ') 涨停!'
    if (item.limitType === 'limit_down') return '🔒 ' + name + '(' + item.symbol + ') 跌停!'
    if (item.limitType === 'near_up') return '⚠️ ' + name + '(' + item.symbol + ') 接近涨停'
    if (item.limitType === 'near_down') return '⚠️ ' + name + '(' + item.symbol + ') 接近跌停'
    const label = item.crossType === 'golden_cross' ? '金叉↑' : '死叉↓'
    return '🔔 ' + name + '(' + item.symbol + ') MACD ' + label
  }).join('　　✦　　')
})

function exportWatchlist() {
  const codes = store.watchlist.map(item => item.symbol)
  if (!codes.length) return
  const blob = new Blob([codes.join(' ')], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'watchlist_' + new Date().toISOString().slice(0,10) + '.txt'
  a.click()
  URL.revokeObjectURL(url)
}

// ---- view mode ----
function toggleMute(symbol) {
  const idx = mutedSymbols.value.indexOf(symbol)
  if (idx >= 0) mutedSymbols.value.splice(idx, 1)
  else mutedSymbols.value.push(symbol)
  localStorage.setItem('mutedSymbols', JSON.stringify(mutedSymbols.value))
}

function isMuted(symbol) { return mutedSymbols.value.includes(symbol) }

// ---- price alerts ----
function getPriceAlert(symbol) { return priceAlerts.value[symbol] || { above: null, below: null } }
function setPriceAlert(symbol, field, val) {
  const alert = { ...getPriceAlert(symbol), [field]: val ? Number(val) : null }
  if (!alert.above && !alert.below) delete priceAlerts.value[symbol]
  else priceAlerts.value[symbol] = alert
  priceAlerts.value = { ...priceAlerts.value }
  localStorage.setItem('priceAlerts', JSON.stringify(priceAlerts.value))
}
function removePriceAlert(symbol) {
  delete priceAlerts.value[symbol]
  priceAlerts.value = { ...priceAlerts.value }
  localStorage.setItem('priceAlerts', JSON.stringify(priceAlerts.value))
}

// ---- price alert check on refresh ----
const triggeredPriceAlerts = ref([])

function checkPriceAlerts() {
  const triggered = []
  for (const [symbol, alert] of Object.entries(priceAlerts.value)) {
    if (mutedSymbols.value.includes(symbol)) continue
    const item = store.sortedWatchlist.find(i => i.symbol === symbol)
    if (!item?.quote) continue
    const price = item.quote.price
    const name = item.quote.name || symbol
    if (alert.above && price >= alert.above) triggered.push({ symbol, name, type: 'above', target: alert.above, price })
    if (alert.below && price <= alert.below) triggered.push({ symbol, name, type: 'below', target: alert.below, price })
  }
  if (triggered.length > 0) {
    triggeredPriceAlerts.value = triggered
    if (settings.alertMode === 'beep') playAlertBeep()
    else if (settings.alertMode === 'voice') {
      speechSynthesis.cancel()
      const text = triggered.map(t => `${t.name}已${t.type === 'above' ? '突破' : '跌破'}${t.target}元`).join('，')
      const u = new SpeechSynthesisUtterance('价格预警：' + text)
      u.lang = 'zh-CN'; u.rate = 1.1
      setTimeout(() => speechSynthesis.speak(u), 50)
    }
  }
}

// ---- price alert dialog ----
const priceDialog = ref({ show: false, symbol: '', name: '', above: '', below: '' })
function openPriceDialog(item) {
  const alert = getPriceAlert(item.symbol)
  priceDialog.value = { show: true, symbol: item.symbol, name: item.quote?.name || item.symbol, above: alert.above || '', below: alert.below || '' }
}
function savePriceDialog() {
  const { symbol, above, below } = priceDialog.value
  if (above) setPriceAlert(symbol, 'above', above)
  else { const a = getPriceAlert(symbol); if (a.above) setPriceAlert(symbol, 'above', null) }
  if (below) setPriceAlert(symbol, 'below', below)
  else { const a = getPriceAlert(symbol); if (a.below) setPriceAlert(symbol, 'below', null) }
  priceDialog.value.show = false
}

// ---- alert sort for list ----
function getAlertScore(item) {
  const cross = item.macd?.length >= 2 ? detectCrossover(item.macd) : 'none'
  const limit = detectLimit(item.quote, item.symbol)
  const hasPriceAlert = !!priceAlerts.value[item.symbol]
  let score = 0
  if (cross !== 'none') score += 2
  if (limit !== 'none') score += 3
  if (hasPriceAlert) score += 1
  return score
}

const sortedList = computed(() => {
  const arr = [...store.sortedWatchlist]
  const { key, dir } = listSort.value
  const mul = dir === 'desc' ? -1 : 1
  arr.sort((a, b) => {
    if (key === 'alert') {
      return (getAlertScore(a) - getAlertScore(b)) * mul
    }
    const va = a.quote?.[key] ?? 0
    const vb = b.quote?.[key] ?? 0
    return (va - vb) * mul
  })
  return arr
})

function toggleSort(key) {
  if (listSort.value.key === key) {
    listSort.value.dir = listSort.value.dir === 'desc' ? 'asc' : 'desc'
  } else {
    listSort.value = { key, dir: 'desc' }
  }
}

function sortIcon(key) {
  if (listSort.value.key !== key) return '↕'
  return listSort.value.dir === 'desc' ? '↓' : '↑'
}

function setViewMode(mode) {
  viewMode.value = mode
  localStorage.setItem('viewMode', mode)
}

// ---- price limit detection ----
function getLimitPct(symbol) {
  const s = String(symbol)
  if (s.startsWith('688') || s.startsWith('689')) return 20   // 科创板
  if (s.startsWith('300') || s.startsWith('301')) return 20   // 创业板
  if (s.startsWith('8')) return 30                             // 北交所
  return 10                                                    // 主板
}

function detectLimit(quote, symbol) {
  if (!quote) return 'none'
  const pct = Math.abs(quote.changePct ?? 0)
  const limit = getLimitPct(symbol)
  if (pct >= limit - 0.1) return pct > 0 ? 'limit_up' : 'limit_down'
  if (pct >= limit - 1) return pct > 0 ? 'near_up' : 'near_down'
  return 'none'
}

// ---- alert dock ----
const alertStocks = computed(() => {
  const items = []
  for (const item of store.sortedWatchlist) {
    if (mutedSymbols.value.includes(item.symbol)) continue
    const cross = item.macd?.length >= 2 ? detectCrossover(item.macd) : 'none'
    const limit = detectLimit(item.quote, item.symbol)
    if (cross !== 'none' || limit !== 'none') {
      items.push({ ...item, crossType: cross, limitType: limit })
    }
  }
  return items
})

// ---- alert sound ----
const seenAlerts = ref(new Set())

// Reuse a single AudioContext to avoid browser autoplay policy issues
let audioCtx = null
function getAudioCtx() {
  if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)()
  return audioCtx
}

function playAlertBeep() {
  try {
    const ctx = getAudioCtx()
    if (ctx.state === 'suspended') ctx.resume()
    const t = ctx.currentTime
    const notes = [880, 1100]
    notes.forEach((freq, i) => {
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.type = 'sine'
      osc.frequency.value = freq
      gain.gain.setValueAtTime(0, t + i * 0.15)
      gain.gain.linearRampToValueAtTime(0.3, t + i * 0.15 + 0.04)
      gain.gain.linearRampToValueAtTime(0, t + i * 0.15 + 0.15)
      osc.connect(gain)
      gain.connect(ctx.destination)
      osc.start(t + i * 0.15)
      osc.stop(t + i * 0.15 + 0.2)
    })
  } catch (e) { console.warn('beep failed', e) }
}

function speakAlert(stocks) {
  try {
    speechSynthesis.cancel()
    const text = stocks.map(item => {
      const name = item.quote?.name || item.symbol
      if (item.limitType === 'limit_up') return `${name}涨停`
      if (item.limitType === 'limit_down') return `${name}跌停`
      if (item.limitType === 'near_up') return `${name}接近涨停`
      if (item.limitType === 'near_down') return `${name}接近跌停`
      const label = item.crossType === 'golden_cross' ? '金叉' : '死叉'
      return `${name}${label}`
    }).join('，')
    const utter = new SpeechSynthesisUtterance('预警：' + text)
    utter.lang = 'zh-CN'
    utter.rate = 1.1
    // Chrome bug: need to speak shortly after cancel
    setTimeout(() => speechSynthesis.speak(utter), 50)
  } catch (e) { console.warn('speak failed', e) }
}

// Warm up audio on first user interaction to unlock browser autoplay
let audioWarmed = false
function warmUpAudio() {
  if (audioWarmed) return
  audioWarmed = true
  try {
    const ctx = getAudioCtx()
    if (ctx.state === 'suspended') ctx.resume()
    // silent oscillator to unlock
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    gain.gain.value = 0
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.start()
    osc.stop(ctx.currentTime + 0.01)
    // warm up speechSynthesis
    const u = new SpeechSynthesisUtterance('')
    u.volume = 0
    speechSynthesis.speak(u)
  } catch {}
  document.removeEventListener('click', warmUpAudio)
  document.removeEventListener('touchstart', warmUpAudio)
}
document.addEventListener('click', warmUpAudio, { once: false })
document.addEventListener('touchstart', warmUpAudio, { once: false })

function triggerAlert(freshKeys) {
  const items = alertStocks.value.filter(a => freshKeys.has(a.symbol + ':' + a.crossType + ':' + a.limitType))
  if (settings.alertMode === 'beep') playAlertBeep()
  else if (settings.alertMode === 'voice') speakAlert(items)
  // scroll to first alerted card
  if (items.length) {
    const firstSymbol = items[0].symbol
    highlightSymbol.value = firstSymbol
    const el = document.querySelector(`.card-wrapper[data-symbol="${firstSymbol}"]`)
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    setTimeout(() => { highlightSymbol.value = null }, 3000)
  }
}

watch(alertStocks, (newVal) => {
  const keys = new Set(newVal.map(a => a.symbol + ':' + a.crossType + ':' + a.limitType))
  const fresh = [...keys].filter(k => !seenAlerts.value.has(k))
  if (fresh.length > 0 && seenAlerts.value.size > 0 && settings.alertMode !== 'off') {
    triggerAlert(new Set(fresh))
  }
  seenAlerts.value = keys
})

function fmtVol(v) {
  if (!v) return '--'
  if (v >= 1e8) return (v / 1e8).toFixed(2) + '亿'
  if (v >= 1e4) return (v / 1e4).toFixed(1) + '万'
  return v.toFixed(0)
}
function fmtP(v) { if (v == null) return '--'; return Number(v).toFixed(Math.abs(v) < 10 ? 3 : 2) }
function fmtPct(v) { return v == null ? '--' : (v > 0 ? '+' : '') + Number(v).toFixed(2) + '%' }
function priceCls(pct) { return pct > 0 ? 'price-up' : pct < 0 ? 'price-down' : 'price-flat' }

// ---- drag from handle ----
function onCardDragStart(idx, e) {
  isDragging = true
  dragIdx.value = idx
  // capture pointer so we get move/up even outside the element
  e.target.setPointerCapture?.(e.pointerId)
  document.addEventListener('pointermove', onDocPointerMove)
  document.addEventListener('pointerup', onDocPointerUp)
}

function onDocPointerMove(e) {
  if (!isDragging) return
  e.preventDefault()
  // Find which card wrapper the pointer is over
  const els = document.elementsFromPoint(e.clientX, e.clientY)
  const wrapper = els.find(el => el.classList.contains('card-wrapper'))
  if (wrapper) {
    const idx = wrapper.dataset.idx
    overIdx.value = idx !== undefined ? Number(idx) : -1
  }
}

function onDocPointerUp() {
  if (isDragging && dragIdx.value !== -1 && overIdx.value !== -1 && dragIdx.value !== overIdx.value) {
    store.reorderCards(dragIdx.value, overIdx.value)
  }
  isDragging = false
  dragIdx.value = -1
  overIdx.value = -1
  document.removeEventListener('pointermove', onDocPointerMove)
  document.removeEventListener('pointerup', onDocPointerUp)
}

onMounted(() => { init(); scheduleRefresh() })
onUnmounted(() => { clearTimeout(refreshTimer); document.removeEventListener('pointermove', onDocPointerMove); document.removeEventListener('pointerup', onDocPointerUp) })
</script>

<template>
  <div class="home-view">
    <AppHeader @add="showModal = true" :marquee="marqueeText">
      <template #actions>
        <button class="btn btn-ghost btn-sm" @click="showModal = true">＋ 添加</button>
        <button class="btn btn-ghost btn-sm" @click="exportWatchlist" title="导出自选股">📥 导出</button>
        <div class="view-toggle">
          <button class="vt-btn" :class="{ active: viewMode === 'grid' }" @click="setViewMode('grid')" title="卡片视图">▦</button>
          <button class="vt-btn" :class="{ active: viewMode === 'list' }" @click="setViewMode('list')" title="列表视图">☰</button>
        </div>
        <button class="btn btn-ghost btn-sm alert-btn" :class="{ active: showDock, 'has-alerts': alertStocks.length }" @click="showDock = !showDock" title="预警清单">
          🔔<span v-if="alertStocks.length" class="alert-badge">{{ alertStocks.length }}</span>
        </button>
        <button class="btn btn-ghost btn-sm" :class="{ active: showSettings }" @click="showSettings = !showSettings">⚙️</button>
      </template>
    </AppHeader>

    <Transition name="dropdown">
      <div v-if="showSettings" class="settings-dropdown">
        <div class="settings-row">
          <span class="settings-label">涨跌配色</span>
          <div class="settings-btns">
            <button class="settings-opt" :class="{ active: settings.theme === 'cn' }" @click="settings.theme = 'cn'">
              <span class="price-up">红涨</span> <span class="price-down">绿跌</span>
            </button>
            <button class="settings-opt" :class="{ active: settings.theme === 'intl' }" @click="settings.theme = 'intl'">
              <span class="price-up">绿涨</span> <span class="price-down">红跌</span>
            </button>
          </div>
        </div>
        <div class="settings-row">
          <span class="settings-label">交易时段加速</span>
          <button class="toggle-btn" :class="{ on: settings.fastRefresh }" @click="settings.fastRefresh = !settings.fastRefresh">
            <span class="toggle-knob" />
          </button>
          <span class="settings-hint mono">{{ settings.fastRefresh ? '5s / 30s' : '30s' }}</span>
        </div>
        <div class="settings-row">
          <span class="settings-label">预警提示</span>
          <div class="settings-btns">
            <button class="settings-opt" :class="{ active: settings.alertMode === 'off' }" @click="settings.alertMode = 'off'">关闭</button>
            <button class="settings-opt" :class="{ active: settings.alertMode === 'beep' }" @click="settings.alertMode = 'beep'">🔔 提示音</button>
            <button class="settings-opt" :class="{ active: settings.alertMode === 'voice' }" @click="settings.alertMode = 'voice'">🗣 语音</button>
          </div>
        </div>
        <div class="settings-row" v-if="store.cardOrder.length">
          <span class="settings-label">卡片排序</span>
          <button class="btn btn-ghost btn-sm" @click="store.resetOrder()">恢复默认</button>
        </div>
      </div>
    </Transition>

    <div v-if="initialized && store.watchlist.length === 0" class="empty-state">
      <div class="empty-icon">📊</div>
      <h2 class="empty-title">还没有添加自选股</h2>
      <p class="empty-desc">点击"添加"按钮，输入股票代码开始监控</p>
      <button class="btn btn-primary" @click="showModal = true">＋ 添加股票</button>
    </div>

    <div v-if="!initialized" class="card-grid">
      <div v-for="i in 4" :key="i" class="skeleton-card">
        <div class="skeleton" style="height:20px;width:60%;margin-bottom:12px" />
        <div class="skeleton" style="height:32px;width:40%;margin-bottom:16px" />
        <div class="skeleton" style="height:120px;margin-bottom:8px" />
        <div class="skeleton" style="height:80px" />
      </div>
    </div>

    <!-- card grid view -->
    <div v-if="initialized && store.watchlist.length > 0 && viewMode === 'grid'" class="card-grid">
      <div
        v-for="(item, idx) in store.sortedWatchlist"
        :key="item.symbol"
        class="card-wrapper"
        :data-idx="idx"
        :data-symbol="item.symbol"
        :class="{ 'drag-source': dragIdx === idx, 'drag-over': overIdx === idx && dragIdx !== idx, 'card-highlight': highlightSymbol === item.symbol }"
      >
        <StockCard
          :symbol="item.symbol"
          :market="item.market"
          :quote="item.quote"
          :intraday-data="item.intraday"
          :macd-data="item.macd"
          :loading="item.loading"
          :muted="isMuted(item.symbol)"
          @remove="onRemove"
          @toggle-mute="toggleMute"
          @dragstart="onCardDragStart(idx, $event)"
        />
        <div v-if="detectLimit(item.quote, item.symbol) !== 'none'" class="limit-badge"
          :class="detectLimit(item.quote, item.symbol)">
          {{ detectLimit(item.quote, item.symbol).includes('up') ? '涨停' : '跌停' }}
        </div>
      </div>
    </div>

    <!-- list view -->
    <div v-if="initialized && store.watchlist.length > 0 && viewMode === 'list'" class="list-view">
      <div class="list-header">
        <span class="lh-name">名称</span>
        <span class="lh-code">代码</span>
        <span class="lh-trend">走势</span>
        <span class="lh-sortable" @click="toggleSort('price')">现价 <span class="sort-icon">{{ sortIcon('price') }}</span></span>
        <span class="lh-sortable" @click="toggleSort('changePct')">涨跌幅 <span class="sort-icon">{{ sortIcon('changePct') }}</span></span>
        <span class="lh-sortable" @click="toggleSort('volume')">成交量 <span class="sort-icon">{{ sortIcon('volume') }}</span></span>
        <span class="lh-sortable" @click="toggleSort('high')">最高 <span class="sort-icon">{{ sortIcon('high') }}</span></span>
        <span class="lh-sortable" @click="toggleSort('low')">最低 <span class="sort-icon">{{ sortIcon('low') }}</span></span>
        <span class="lh-sortable" @click="toggleSort('alert')">预警 <span class="sort-icon">{{ sortIcon('alert') }}</span></span>
        <span class="lh-price-alert">价格</span>
      </div>
      <div v-for="item in sortedList" :key="item.symbol" class="list-row"
        @click="$router.push({ name: 'Detail', params: { symbol: item.symbol }, query: { market: item.market } })">
        <span class="lr-name">{{ item.quote?.name || '--' }}</span>
        <span class="lr-code mono">{{ item.symbol }}</span>
        <span class="lr-trend"><MiniSparkline :data="item.intraday" :color="priceCls(item.quote?.changePct) === 'price-up' ? '#f85149' : priceCls(item.quote?.changePct) === 'price-down' ? '#3fb950' : '#58a6ff'" :width="72" :height="24" /></span>
        <span class="lr-price mono" :class="priceCls(item.quote?.changePct)">{{ fmtP(item.quote?.price) }}</span>
        <span class="lr-change mono" :class="priceCls(item.quote?.changePct)">{{ fmtPct(item.quote?.changePct) }}</span>
        <span class="lr-vol mono">{{ fmtVol(item.quote?.volume) }}</span>
        <span class="lr-high mono">{{ fmtP(item.quote?.high) }}</span>
        <span class="lr-low mono">{{ fmtP(item.quote?.low) }}</span>
        <span class="lr-alert">
          <template v-if="detectCrossover(item.macd) === 'golden_cross'"><span class="cross-dot golden">金叉</span></template>
          <template v-else-if="detectCrossover(item.macd) === 'death_cross'"><span class="cross-dot death">死叉</span></template>
          <template v-else><span class="cross-dot none">--</span></template>
        </span>
        <span class="lr-price-alert">
          <button class="price-alert-btn" :class="{ active: priceAlerts[item.symbol] }"
            @click.stop="openPriceDialog(item)" :title="priceAlerts[item.symbol] ? '编辑价格预警' : '设置价格预警'">💰</button>
        </span>

      </div>
    </div>

    <!-- price alert dialog -->
    <Transition name="dropdown">
      <div v-if="priceDialog.show" class="confirm-overlay" @click.self="priceDialog.show = false">
        <div class="confirm-box">
          <div class="confirm-title">💰 价格预警 · {{ priceDialog.name }}</div>
          <div class="price-alert-form">
            <label class="calc-label">高于此价格提醒（突破）</label>
            <input v-model="priceDialog.above" type="number" step="0.01" class="calc-input" placeholder="如 15.00" />
            <label class="calc-label">低于此价格提醒（跌破）</label>
            <input v-model="priceDialog.below" type="number" step="0.01" class="calc-input" placeholder="如 10.00" />
          </div>
          <div class="confirm-actions">
            <button v-if="priceAlerts[priceDialog.symbol]" class="btn btn-ghost btn-sm" @click="removePriceAlert(priceDialog.symbol); priceDialog.show = false">删除</button>
            <button class="btn btn-ghost btn-sm" @click="priceDialog.show = false">取消</button>
            <button class="btn btn-primary btn-sm" @click="savePriceDialog">保存</button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- triggered price alerts toast -->
    <Transition name="dropdown">
      <div v-if="triggeredPriceAlerts.length" class="price-toast">
        <div class="toast-head">💰 价格预警触发 <button class="ann-close" @click="triggeredPriceAlerts=[]">✕</button></div>
        <div v-for="t in triggeredPriceAlerts" :key="t.symbol+t.type" class="toast-item" @click="triggeredPriceAlerts=[]; $router.push({ name:'Detail', params:{ symbol:t.symbol }, query:{ market: store.sortedWatchlist.find(i=>i.symbol===t.symbol)?.market } })">
          <span class="toast-name">{{ t.name }}</span>
          <span :class="t.type==='above' ? 'price-up' : 'price-down'">{{ t.type === 'above' ? '突破' : '跌破' }} {{ fmtP(t.target) }}</span>
          <span class="mono">→ {{ fmtP(t.price) }}</span>
        </div>
      </div>
    </Transition>

    <!-- delete confirm dialog -->
    <Transition name="dropdown">
      <div v-if="confirmDel.show" class="confirm-overlay" @click.self="confirmDel.show = false">
        <div class="confirm-box">
          <div class="confirm-title">确认删除</div>
          <div class="confirm-msg">确定要将 <b>{{ confirmDel.symbol }}</b> 从自选中移除吗？</div>
          <div class="confirm-actions">
            <button class="btn btn-ghost btn-sm" @click="confirmDel.show = false">取消</button>
            <button class="btn btn-danger btn-sm" @click="doRemove">删除</button>
          </div>
        </div>
      </div>
    </Transition>

    <AddStockModal :visible="showModal" @close="showModal = false" @added="onAdded" />

    <!-- alert sidebar overlay -->
    <Transition name="sidebar-bg">
      <div v-if="showDock" class="sidebar-overlay" @click.self="showDock=false">
        <Transition name="sidebar">
          <div v-if="showDock" class="alert-sidebar">
            <div class="sidebar-head">
              <span>🔔 MACD 预警</span>
              <button class="ann-close" @click="showDock=false">✕</button>
            </div>
            <div v-if="!alertStocks.length" class="sidebar-empty">暂无预警信号</div>
            <div v-else class="sidebar-list">
              <div v-for="item in alertStocks" :key="item.symbol" class="sidebar-item" :class="'sb-' + item.crossType"
                @mouseenter="scrollCardIntoView(item.symbol)"
                @mouseleave="clearHighlight()"
                @click="showDock=false; $router.push({ name: 'Detail', params: { symbol: item.symbol }, query: { market: item.market } })">
                <div class="sb-top">
                  <span class="sb-name">{{ item.quote?.name || item.symbol }}</span>
                  <span class="sb-cross" :class="item.crossType === 'golden_cross' ? 'price-up' : 'price-down'">
                    {{ item.crossType === 'golden_cross' ? '金叉 ↑' : '死叉 ↓' }}
                  </span>
                </div>
                <div class="sb-bottom">
                  <span class="sb-code mono">{{ item.symbol }}</span>
                  <span class="mono" :class="priceCls(item.quote?.changePct)">{{ fmtP(item.quote?.price) }}</span>
                  <span class="mono sb-pct" :class="priceCls(item.quote?.changePct)">{{ fmtPct(item.quote?.changePct) }}</span>
                </div>
              </div>
            </div>
          </div>
        </Transition>
      </div>
    </Transition>

  </div>
</template>

<style scoped>
.home-view { min-height: calc(100vh - 60px); position: relative; }

.empty-state { display:flex; flex-direction:column; align-items:center; justify-content:center; padding:80px 20px; text-align:center; }
.empty-icon { font-size:48px; margin-bottom:16px; }
.empty-title { font-size:20px; font-weight:600; color:var(--text-primary); margin-bottom:8px; }
.empty-desc { font-size:14px; color:var(--text-secondary); margin-bottom:20px; max-width:360px; }
.skeleton-card { background:var(--bg-card); border:1px solid var(--border-default); border-radius:var(--radius-lg); padding:16px; }

.settings-dropdown { background:var(--bg-card); border:1px solid var(--border-default); border-radius:var(--radius); padding:12px 16px; margin-bottom:12px; display:flex; gap:20px; flex-wrap:wrap; }
.settings-row { display:flex; align-items:center; gap:10px; }
.settings-label { font-size:12px; color:var(--text-secondary); white-space:nowrap; }
.settings-btns { display:flex; gap:4px; }
.settings-opt { padding:4px 12px; font-size:12px; border-radius:4px; background:var(--bg-surface); border:1px solid var(--border-default); color:var(--text-secondary); transition:all .15s; display:flex; gap:4px; }
.settings-opt:hover { border-color:var(--text-muted); }
.settings-opt.active { border-color:var(--accent-blue); color:var(--text-primary); }
.toggle-btn { width:36px; height:20px; border-radius:10px; background:var(--border-default); border:none; position:relative; cursor:pointer; transition:background .2s; }
.toggle-btn.on { background:var(--accent-blue); }
.toggle-knob { position:absolute; top:2px; left:2px; width:16px; height:16px; border-radius:50%; background:#fff; transition:transform .2s; }
.toggle-btn.on .toggle-knob { transform:translateX(16px); }
.settings-hint { font-size:11px; color:var(--text-muted); }
.dropdown-enter-active, .dropdown-leave-active { transition:all .2s ease; }
.dropdown-enter-from, .dropdown-leave-to { opacity:0; transform:translateY(-8px); }

/* drag */
.card-wrapper { transition: transform .15s ease, opacity .15s ease; touch-action: none; user-select: none; position: relative; }
.card-wrapper.drag-source { opacity: 0.35; transform: scale(0.96); }
.card-wrapper.drag-over { transform: scale(1.02); }
.card-wrapper.drag-over :deep(.stock-card) { border-color: var(--accent-blue) !important; box-shadow: 0 0 0 2px rgba(88,166,255,0.3); }
.card-highlight { transition: transform .3s ease, box-shadow .3s ease; }
.card-highlight :deep(.stock-card) { box-shadow: 0 0 0 2px var(--accent-orange), 0 0 16px rgba(210,153,34,0.3) !important; }

/* view toggle */
.view-toggle { display:flex; gap:2px; background:var(--bg-surface); border-radius:6px; padding:2px; }
.vt-btn { width:28px; height:26px; border:none; border-radius:4px; background:transparent; color:var(--text-muted); font-size:14px; cursor:pointer; transition:all .15s; display:flex; align-items:center; justify-content:center; }
.vt-btn:hover { color:var(--text-primary); }
.vt-btn.active { background:var(--accent-blue); color:#fff; }

/* alert button */
.alert-btn { position:relative; }
.alert-badge { position:absolute; top:-4px; right:-6px; min-width:16px; height:16px; border-radius:8px; background:var(--accent-red); color:#fff; font-size:10px; font-weight:700; line-height:16px; text-align:center; padding:0 4px; animation:pulse-badge 2s infinite; }
@keyframes pulse-badge { 0%,100%{transform:scale(1)} 50%{transform:scale(1.15)} }
.alert-btn.has-alerts { color:var(--accent-red); }

/* alert sidebar overlay */
.sidebar-overlay { position:fixed; top:0; right:0; bottom:0; left:0; z-index:200; background:rgba(0,0,0,0.35); backdrop-filter:blur(2px); display:flex; justify-content:flex-end; }
.alert-sidebar { width:280px; height:100vh; background:var(--bg-card); border-left:1px solid var(--border-default); display:flex; flex-direction:column; overflow:hidden; box-shadow:-4px 0 24px rgba(0,0,0,0.4); }
.sidebar-head { display:flex; justify-content:space-between; align-items:center; padding:14px 16px; border-bottom:1px solid var(--border-default); font-size:13px; font-weight:600; color:var(--accent-orange); flex-shrink:0; }
.sidebar-empty { padding:40px 14px; text-align:center; font-size:12px; color:var(--text-muted); }
.sidebar-list { flex:1; overflow-y:auto; }
.sidebar-item { padding:12px 16px; border-bottom:1px solid var(--border-default); cursor:pointer; transition:background .12s; }
.sidebar-item:last-child { border-bottom:none; }
.sidebar-item:hover { background:var(--bg-surface); }
.sidebar-item.sb-golden { border-left:3px solid var(--price-up); }
.sidebar-item.sb-death { border-left:3px solid var(--price-down); }
.sb-top { display:flex; justify-content:space-between; align-items:center; margin-bottom:4px; }
.sb-name { font-size:13px; font-weight:500; color:var(--text-primary); }
.sb-cross { font-size:11px; font-weight:600; }
.sb-bottom { display:flex; align-items:center; gap:8px; }
.sb-code { font-size:11px; color:var(--text-muted); }
.sb-pct { font-size:12px; }
.sidebar-enter-active, .sidebar-leave-active { transition:transform .25s ease; }
.sidebar-enter-from, .sidebar-leave-to { transform:translateX(100%); }
.sidebar-bg-enter-active, .sidebar-bg-leave-active { transition:opacity .25s ease; }
.sidebar-bg-enter-from, .sidebar-bg-leave-to { opacity:0; }

/* list view */
.list-view { background:var(--bg-card); border:1px solid var(--border-default); border-radius:var(--radius-lg); overflow:hidden; }
.list-header { display:grid; grid-template-columns:1.2fr 0.7fr 64px 0.7fr 0.7fr 0.7fr 0.7fr 0.7fr 0.5fr 0.4fr; padding:8px 16px; font-size:11px; color:var(--text-muted); border-bottom:1px solid var(--border-default); background:var(--bg-surface); gap:8px; align-items:center; }
.list-row { display:grid; grid-template-columns:1.2fr 0.7fr 64px 0.7fr 0.7fr 0.7fr 0.7fr 0.7fr 0.5fr 0.4fr; padding:10px 16px; font-size:13px; border-bottom:1px solid var(--border-default); cursor:pointer; transition:background .12s; align-items:center; gap:8px; }
.list-row:last-child { border-bottom:none; }
.list-row:hover { background:var(--bg-surface); }
.lh-name { text-align:left; }
.lh-code { text-align:left; }
.lh-trend { text-align:center; }
.lh-alert { text-align:center; }
.lr-name { font-weight:500; color:var(--text-primary); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; text-align:left; }
.lr-code { font-size:12px; color:var(--text-secondary); }
.lr-price, .lr-change, .lr-vol, .lr-high, .lr-low { text-align:right; }
.cross-dot { font-size:11px; font-weight:600; padding:2px 6px; border-radius:4px; }
.cross-dot.golden { background:rgba(248,81,73,0.12); color:var(--price-up); }
.cross-dot.death { background:rgba(63,185,80,0.12); color:var(--price-down); }
.cross-dot.none { color:var(--text-muted); font-weight:400; }
.lh-sortable { cursor:pointer; user-select:none; transition:color .15s; text-align:right; white-space:nowrap; }
.lh-sortable:hover { color:var(--text-primary); }
.sort-icon { font-size:9px; opacity:0.5; margin-left:1px; }
.lh-sortable:hover .sort-icon { opacity:1; }
.ann-close { background:transparent; color:var(--text-muted); font-size:12px; }
.ann-close:hover { color:var(--text-primary); }
.lr-trend { display:flex; align-items:center; justify-content:center; }

@media (max-width: 768px) {
  .alert-sidebar { width:85vw; }
  .list-header, .list-row { grid-template-columns:1fr 0.6fr 50px 0.6fr 0.6fr; font-size:12px; padding:8px 12px; }
  .lh-vol, .lh-high, .lh-low, .lh-alert, .lh-price-alert, .lr-vol, .lr-high, .lr-low, .lr-alert, .lr-price-alert { display:none; }
}

/* confirm dialog */
.price-alert-form { display:flex; flex-direction:column; gap:6px; margin-bottom:12px; }
.lh-price-alert { text-align:center; font-size:11px; }
.lr-price-alert { text-align:center; }
.price-alert-btn { background:transparent; font-size:14px; cursor:pointer; opacity:0.3; transition:opacity .15s; padding:2px 4px; }
.price-alert-btn:hover, .price-alert-btn.active { opacity:1; }
.price-toast { position:fixed; top:70px; left:50%; transform:translateX(-50%); z-index:250; background:var(--bg-card); border:1px solid var(--accent-orange); border-radius:var(--radius-lg); padding:10px 14px; min-width:260px; box-shadow:0 4px 20px rgba(0,0,0,0.5); }
.toast-head { display:flex; justify-content:space-between; align-items:center; font-size:13px; font-weight:600; color:var(--accent-orange); margin-bottom:6px; }
.toast-item { padding:6px 0; font-size:12px; cursor:pointer; display:flex; gap:8px; align-items:center; border-bottom:1px solid var(--border-default); }
.toast-item:last-child { border-bottom:none; }
.toast-item:hover { opacity:0.8; }
.toast-name { font-weight:500; color:var(--text-primary); min-width:60px; }

.confirm-overlay { position:fixed; top:0; left:0; right:0; bottom:0; z-index:300; background:rgba(0,0,0,0.45); backdrop-filter:blur(2px); display:flex; align-items:center; justify-content:center; }
.confirm-box { background:var(--bg-card); border:1px solid var(--border-default); border-radius:var(--radius-lg); padding:20px 24px; min-width:280px; max-width:360px; box-shadow:0 8px 32px rgba(0,0,0,0.5); }
.confirm-title { font-size:15px; font-weight:600; color:var(--text-primary); margin-bottom:8px; }
.confirm-msg { font-size:13px; color:var(--text-secondary); margin-bottom:16px; line-height:1.5; }
.confirm-msg b { color:var(--text-primary); }
.confirm-actions { display:flex; justify-content:flex-end; gap:8px; }
.btn-danger { background:var(--accent-red); color:#fff; border:none; }
.btn-danger:hover { background:#da3633; }

/* price limit alerts */
.sb-limit_up, .sb-near_up { border-left: 3px solid var(--accent-red) !important; }
.sb-limit_down, .sb-near_down { border-left: 3px solid var(--accent-green, #3fb950) !important; }
.limit-badge { position:absolute; top:-6px; right:-6px; font-size:10px; font-weight:700; padding:2px 6px; border-radius:4px; z-index:5; pointer-events:none; }
.limit-badge.limit_up, .limit-badge.near_up { background:var(--accent-red); color:#fff; }
.limit-badge.limit_down, .limit-badge.near_down { background:var(--accent-green, #3fb950); color:#fff; }
</style>
