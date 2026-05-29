<script setup>
import { ref, watch } from 'vue'
import * as api from '../api/stock'

defineProps({ visible: { type: Boolean, default: false } })
const emit = defineEmits(['close', 'added'])

const query = ref('')
const results = ref([])
const loading = ref(false)
const error = ref('')
const selected = ref([])   // [{ symbol, name, market }]
let searchTimer = null

function close() {
  query.value = ''; results.value = []; error.value = ''; selected.value = []
  emit('close')
}

// Debounced search
watch(query, (val) => {
  clearTimeout(searchTimer)
  if (!val.trim()) { results.value = []; return }
  searchTimer = setTimeout(() => doSearch(val.trim()), 200)
})

async function doSearch(q) {
  loading.value = true
  try {
    results.value = await api.searchStocks(q) || []
  } catch { results.value = [] }
  loading.value = false
}

function toggleSelect(item) {
  const idx = selected.value.findIndex(s => s.symbol === item.symbol)
  if (idx >= 0) {
    selected.value.splice(idx, 1)
  } else {
    selected.value.push(item)
  }
}

function isSelected(sym) {
  return selected.value.some(s => s.symbol === sym)
}

async function confirm() {
  // If no selection but query looks like a code, add directly
  if (selected.value.length === 0 && query.value.trim()) {
    const q = query.value.trim()
    if (/^\d+$/.test(q) || /^hk\d+$/i.test(q)) {
      selected.value = [{ symbol: q, name: '', market: '' }]
    } else {
      error.value = '请从搜索结果中选择，或输入股票代码'
      return
    }
  }
  if (selected.value.length === 0) {
    error.value = '请输入股票代码或名称搜索'
    return
  }
  loading.value = true; error.value = ''
  const codes = selected.value.map(s => {
    if (s.market) return s.market === 'HK' ? `hk${s.symbol}` : s.symbol
    return s.symbol
  }).join(' ')
  try {
    emit('added', codes)
    close()
  } catch (e) { error.value = e.message }
  loading.value = false
}

function onKeydown(e) {
  if (e.key === 'Escape') close()
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) confirm()
}

function fmtMarket(m) {
  return { SH: '沪', SZ: '深', HK: '港' }[m] || m
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="visible" class="modal-overlay" @click.self="close" @keydown="onKeydown">
        <div class="modal-container">
          <div class="modal-header">
            <h2 class="modal-title">添加自选股</h2>
            <button class="modal-close" @click="close">✕</button>
          </div>

          <div class="modal-body">
            <!-- search input -->
            <div class="search-box">
              <input
                v-model="query"
                class="search-input"
                placeholder="输入代码、名称或拼音，如 600519 / 茅台 / gzm"
                autofocus
              />
              <span v-if="loading" class="search-spinner" />
            </div>

            <!-- selected chips -->
            <div v-if="selected.length" class="selected-chips">
              <span v-for="s in selected" :key="s.symbol" class="chip">
                {{ s.name || s.symbol }}
                <button class="chip-x" @click="toggleSelect(s)">✕</button>
              </span>
            </div>

            <!-- search results -->
            <div v-if="results.length" class="result-list">
              <div
                v-for="r in results" :key="r.symbol"
                class="result-item"
                :class="{ selected: isSelected(r.symbol) }"
                @click="toggleSelect(r)"
              >
                <span class="result-code mono">{{ r.symbol }}</span>
                <span class="result-name">{{ r.name }}</span>
                <span class="result-market">{{ fmtMarket(r.market) }}</span>
                <span class="result-check">{{ isSelected(r.symbol) ? '✓' : '' }}</span>
              </div>
            </div>
            <div v-else-if="query.trim() && !loading" class="result-empty">
              无匹配结果，可直接输入代码添加
            </div>

            <p class="modal-hint">
              支持代码 (600519)、中文 (茅台)、拼音首字母 (gzm)、全拼音 (guizhoumaotai)
            </p>
            <p v-if="error" class="modal-error">{{ error }}</p>
          </div>

          <div class="modal-footer">
            <button class="btn btn-ghost" @click="close">取消</button>
            <button class="btn btn-primary" :disabled="loading" @click="confirm">
              {{ loading ? '添加中...' : `确认添加${selected.length ? '(' + selected.length + ')' : ''}` }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-overlay { position:fixed; inset:0; z-index:1000; display:flex; align-items:center; justify-content:center; background:rgba(0,0,0,.6); backdrop-filter:blur(4px); padding:16px; }
.modal-container { width:100%; max-width:520px; background:var(--bg-card); border:1px solid var(--border-default); border-radius:var(--radius-lg); box-shadow:var(--shadow-lg); overflow:hidden; display:flex; flex-direction:column; max-height:80vh; }
.modal-header { display:flex; align-items:center; justify-content:space-between; padding:14px 20px; border-bottom:1px solid var(--border-default); flex-shrink:0; }
.modal-title { font-size:16px; font-weight:600; }
.modal-close { width:28px; height:28px; display:flex; align-items:center; justify-content:center; background:transparent; color:var(--text-secondary); border-radius:4px; font-size:14px; }
.modal-close:hover { background:var(--bg-surface); color:var(--text-primary); }
.modal-body { padding:16px 20px; overflow-y:auto; flex:1; }
.modal-footer { display:flex; align-items:center; justify-content:flex-end; gap:8px; padding:12px 20px; border-top:1px solid var(--border-default); flex-shrink:0; }

.search-box { position:relative; }
.search-input {
  width:100%; padding:10px 12px; padding-right:32px;
  background:var(--bg-primary); border:1px solid var(--border-default);
  border-radius:var(--radius); color:var(--text-primary); font-size:14px;
  transition:border-color .15s;
}
.search-input:focus { border-color:var(--accent-blue); outline:none; }
.search-input::placeholder { color:var(--text-muted); }
.search-spinner {
  position:absolute; right:10px; top:50%; transform:translateY(-50%);
  width:14px; height:14px; border:2px solid var(--border-default);
  border-top-color:var(--accent-blue); border-radius:50%;
  animation:spin .6s linear infinite;
}
@keyframes spin { to { transform:translateY(-50%) rotate(360deg); } }

.selected-chips { display:flex; gap:4px; flex-wrap:wrap; margin-top:8px; }
.chip {
  display:inline-flex; align-items:center; gap:4px;
  padding:2px 8px; font-size:12px; color:var(--accent-blue);
  background:rgba(88,166,255,.1); border:1px solid rgba(88,166,255,.25);
  border-radius:12px;
}
.chip-x { background:transparent; color:var(--text-muted); font-size:10px; }
.chip-x:hover { color:var(--accent-red); }

.result-list { margin-top:8px; max-height:240px; overflow-y:auto; border:1px solid var(--border-default); border-radius:var(--radius); }
.result-item {
  display:flex; align-items:center; gap:8px;
  padding:8px 12px; cursor:pointer; transition:background .1s;
  border-bottom:1px solid var(--border-subtle);
}
.result-item:last-child { border-bottom:none; }
.result-item:hover { background:var(--bg-surface); }
.result-item.selected { background:rgba(88,166,255,.08); }
.result-code { font-size:12px; color:var(--accent-blue); width:60px; flex-shrink:0; }
.result-name { font-size:13px; color:var(--text-primary); flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.result-market { font-size:10px; color:var(--text-muted); background:var(--bg-surface); padding:1px 5px; border-radius:3px; flex-shrink:0; }
.result-check { font-size:12px; color:var(--accent-blue); width:16px; text-align:center; flex-shrink:0; }
.result-empty { padding:16px; text-align:center; font-size:12px; color:var(--text-muted); }

.modal-hint { margin-top:10px; font-size:11px; color:var(--text-secondary); line-height:1.6; }
.modal-error { margin-top:6px; font-size:12px; color:var(--accent-red); }

.modal-enter-active, .modal-leave-active { transition:all .25s cubic-bezier(.4,0,.2,1); }
.modal-enter-from, .modal-leave-to { opacity:0; }
.modal-enter-from .modal-container, .modal-leave-to .modal-container { transform:scale(.95) translateY(8px); }
</style>
