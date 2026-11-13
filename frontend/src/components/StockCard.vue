<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { detectCrossover } from '../utils/indicators'
import KlineChart from './KlineChart.vue'
import MacdChart from './MacdChart.vue'

const props = defineProps({
  symbol: { type: String, required: true },
  market: { type: String, default: '' },
  quote: { type: Object, default: null },
  intradayData: { type: Array, default: () => [] },
  macdData: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  muted: { type: Boolean, default: false }
})

const emit = defineEmits(['remove', 'dragstart', 'toggle-mute'])
const router = useRouter()

const handleHover = ref(false)
const crossoverState = ref('none') // 'none' | 'golden_cross' | 'death_cross'

const priceClass = computed(() => {
  if (!props.quote) return 'price-flat'
  const pct = props.quote.changePct ?? 0
  if (pct > 0) return 'price-up'
  if (pct < 0) return 'price-down'
  return 'price-flat'
})

const limitClass = computed(() => {
  const p = Math.abs(props.quote?.changePct ?? 0)
  const s = String(props.symbol)
  let limit = 10
  if (s.startsWith('688') || s.startsWith('689') || s.startsWith('300') || s.startsWith('301')) limit = 20
  if (s.startsWith('8')) limit = 30
  if (p >= limit - 0.1) return (props.quote?.changePct ?? 0) > 0 ? 'card-limit-up' : 'card-limit-down'
  if (p >= limit - 1) return (props.quote?.changePct ?? 0) > 0 ? 'card-near-up' : 'card-near-down'
  return ''
})

const borderClass = computed(() => {
  if (limitClass.value) return limitClass.value
  if (crossoverState.value === 'golden_cross') return 'border-golden-cross'
  if (crossoverState.value === 'death_cross') return 'border-death-cross'
  return ''
})

const changeSign = computed(() => {
  if (!props.quote) return ''
  const pct = props.quote.changePct ?? 0
  if (pct > 0) return '+'
  return ''
})

function formatPrice(val) {
  if (val === null || val === undefined) return '--'
  return Number(val).toFixed(Math.abs(val) < 10 ? 3 : 2)
}

function formatChange(val) {
  if (val === null || val === undefined) return '--'
  return (val > 0 ? '+' : '') + Number(val).toFixed(2)
}

function formatPct(val) {
  if (val === null || val === undefined) return '--'
  return (val > 0 ? '+' : '') + Number(val).toFixed(2) + '%'
}

function onCrossover(type) {
  crossoverState.value = type
  // 3 秒后恢复普通状态
  setTimeout(() => {
    if (crossoverState.value === type) {
      crossoverState.value = 'none'
    }
  }, 3000)
}

function goToDetail() {
  if (handleHover.value) return
  router.push({ path: `/stock/${props.symbol}`, query: { market: props.market } })
}

function onRemove(e) {
  e.stopPropagation()
  emit('remove', props.symbol, props.market)
}
</script>

<template>
  <div
    class="stock-card"
    :class="borderClass"
    @click="goToDetail"
  >
    <!-- 头部：名称、代码、删除按钮 -->
    <div class="card-header">
      <div class="card-title-row">
        <span class="card-name">{{ quote?.name || symbol }}</span>
        <span class="card-symbol mono">{{ symbol }}</span>
      </div>
      <div class="card-handle" title="长按拖动"
        @pointerenter="handleHover = true"
        @pointerleave="handleHover = false"
        @pointerdown.stop="emit('dragstart', $event)">⠿</div>
      <button class="card-remove" title="移除" @click="onRemove">✕</button>
      <button class="card-bell" :class="{ off: muted }" :title="muted ? '开启预警' : '关闭预警'" @click.stop="emit('toggle-mute', symbol)">{{ muted ? '🔕' : '🔔' }}</button>
    </div>

    <!-- 价格区 -->
    <div class="card-price-row">
      <span class="card-price mono" :class="priceClass">
        {{ formatPrice(quote?.price) }}
      </span>
      <div class="card-change" :class="priceClass">
        <span class="mono">{{ formatChange(quote?.change) }}</span>
        <span class="mono">{{ formatPct(quote?.changePct) }}</span>
      </div>
    </div>

    <!-- 分时 K 线迷你图 -->
    <div class="card-chart">
      <KlineChart
        :data="intradayData"
        chart-type="intraday"
        :height="120"
      />
    </div>

    <!-- MACD 迷你图 -->
    <div class="card-macd">
      <MacdChart
        :data="macdData"
        :height="80"
        @crossover="onCrossover"
      />
    </div>

    <!-- 加载遮罩 -->
    <div v-if="loading" class="card-loading">
      <div class="card-loading-spinner" />
    </div>
  </div>
</template>

<style scoped>
.stock-card {
  position: relative;
  background: var(--bg-card);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  padding: 14px 16px;
  cursor: pointer;
  transition: background 0.15s, border-color 0.3s, box-shadow 0.3s, transform 0.15s;
  will-change: transform;
  contain: layout style;
  overflow: hidden;
}

.stock-card:hover {
  background: var(--bg-card-hover);
  transform: translateY(-2px);
  box-shadow: var(--shadow);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.card-title-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  min-width: 0;
}

.card-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 160px;
}

.card-symbol {
  font-size: 12px;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.card-handle {
  width: 22px; height: 22px;
  display: flex; align-items: center; justify-content: center;
  color: var(--text-muted); font-size: 16px; cursor: grab;
  border-radius: 4px; flex-shrink: 0;
  transition: all .15s; user-select: none;
}
.card-handle:hover { color: var(--text-primary); background: var(--bg-surface); }
.card-handle:active { cursor: grabbing; }

.card-remove {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  color: var(--text-muted);
  border-radius: 4px;
  font-size: 12px;
  flex-shrink: 0;
  transition: all 0.15s;
}

.card-bell {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border-radius: 4px;
  font-size: 13px;
  flex-shrink: 0;
  transition: all 0.15s;
  margin-left: 2px;
}
.card-bell.off { opacity: 0.4; }
.card-bell:hover { background: rgba(210,153,34,0.15); }
.card-remove:hover {
  background: rgba(248, 81, 73, 0.1);
  color: var(--accent-red);
}

.card-price-row {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 10px;
}

.card-price {
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1.1;
}

.card-change {
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
}

.card-chart {
  margin-bottom: 4px;
  border-radius: var(--radius);
  overflow: hidden;
}

.card-macd {
  border-radius: var(--radius);
  overflow: hidden;
}

.card-loading {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(13, 17, 23, 0.7);
  border-radius: var(--radius-lg);
  z-index: 2;
}

.card-loading-spinner {
  width: 24px;
  height: 24px;
  border: 2px solid var(--border-default);
  border-top-color: var(--accent-blue);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.card-limit-up { border-color: var(--accent-red) !important; box-shadow: 0 0 12px rgba(248,81,73,0.3); animation: limit-pulse 2s ease-in-out infinite; }
.card-limit-down { border-color: var(--accent-green, #3fb950) !important; box-shadow: 0 0 12px rgba(63,185,80,0.3); animation: limit-pulse 2s ease-in-out infinite; }
.card-near-up { border-color: rgba(248,81,73,0.5) !important; }
.card-near-down { border-color: rgba(63,185,80,0.5) !important; }
@keyframes limit-pulse { 0%,100% { opacity:1; } 50% { opacity:0.85; } }
</style>
