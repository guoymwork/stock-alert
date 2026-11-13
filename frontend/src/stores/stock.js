import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as api from '../api/stock'

export const useStockStore = defineStore('stock', () => {
  const watchlist = ref([])
  const quotes = ref({})
  const intradayData = ref({})
  const intradayMacd = ref({})
  const loading = ref({})
  const errors = ref({})
  const cardOrder = ref(JSON.parse(localStorage.getItem('stock-card-order') || '[]'))

  const watchlistWithQuotes = computed(() => {
    return watchlist.value.map((item) => ({
      ...item,
      quote: quotes.value[item.symbol] || null,
      intraday: intradayData.value[item.symbol] || [],
      macd: intradayMacd.value[item.symbol] || [],
      loading: loading.value[item.symbol] || false,
      error: errors.value[item.symbol] || null
    }))
  })

  const sortedWatchlist = computed(() => {
    const items = watchlistWithQuotes.value
    if (cardOrder.value.length > 0) {
      // Custom order: items in cardOrder first (preserving order), then new items
      const orderMap = new Map(cardOrder.value.map((s, i) => [s, i]))
      return [...items].sort((a, b) => {
        const ia = orderMap.has(a.symbol) ? orderMap.get(a.symbol) : 999
        const ib = orderMap.has(b.symbol) ? orderMap.get(b.symbol) : 999
        return ia - ib
      })
    }
    // Default: sort by change percentage
    return [...items].sort((a, b) => {
      if (!a.quote) return 1
      if (!b.quote) return -1
      return Math.abs(b.quote.changePct ?? 0) - Math.abs(a.quote.changePct ?? 0)
    })
  })

  function setLoading(symbol, val) {
    loading.value = { ...loading.value, [symbol]: val }
  }

  function setError(symbol, val) {
    errors.value = { ...errors.value, [symbol]: val }
  }

  /** Build "symbol@MARKET" code for unambiguous API calls */
  function _codeWithMarket(item) {
    return `${item.symbol}@${item.market}`
  }

  async function fetchWatchlist() {
    try {
      const data = await api.getWatchlist()
      watchlist.value = Array.isArray(data) ? data : []
    } catch (e) {
      console.error('获取自选股列表失败:', e.message)
    }
  }

  async function addStocks(codes) {
    const data = await api.addToWatchlist(codes)
    await fetchWatchlist()
    await fetchAllQuotes()
    return data
  }

  async function removeStock(symbol, market) {
    await api.removeFromWatchlist(symbol, market)
    // 同一 symbol 可能对应不同市场（000001@SH 上证指数 / 000001@SZ 平安银行），
    // 指定 market 时只移除这一条
    watchlist.value = watchlist.value.filter((item) =>
      market
        ? !(item.symbol === symbol && item.market === market)
        : item.symbol !== symbol
    )
    // 只有当该 symbol 已完全不在列表中时才清理缓存，避免误删同代码另一市场的数据
    if (!watchlist.value.some((item) => item.symbol === symbol)) {
      delete quotes.value[symbol]
      delete intradayData.value[symbol]
      delete intradayMacd.value[symbol]
    }
  }

  async function fetchAllQuotes() {
    if (watchlist.value.length === 0) return
    // Use symbol@market format for unambiguous resolution
    const codes = watchlist.value.map(item => _codeWithMarket(item)).join(',')
    try {
      const data = await api.getBatchQuotes(codes)
      const list = Array.isArray(data) ? data : [data]
      const map = {}
      for (const q of list) {
        if (q && q.symbol) map[q.symbol] = q
      }
      quotes.value = { ...quotes.value, ...map }
    } catch (e) {
      console.error('批量获取行情失败:', e.message)
    }
  }

  async function fetchIntradayData(symbol) {
    const item = watchlist.value.find(i => i.symbol === symbol)
    const market = item?.market
    const hasData = (intradayData.value[symbol]?.length ?? 0) > 0
    if (!hasData) setLoading(symbol, true)
    setError(symbol, null)
    try {
      const data = await api.getIntradayData(symbol, market)
      intradayData.value = { ...intradayData.value, [symbol]: Array.isArray(data) ? data : [] }
    } catch (e) {
      setError(symbol, e.message)
    } finally {
      setLoading(symbol, false)
    }
  }

  async function fetchIntradayMacd(symbol) {
    const item = watchlist.value.find(i => i.symbol === symbol)
    const market = item?.market
    try {
      const data = await api.getIntradayMacd(symbol, market)
      if (data && data.macd) {
        intradayMacd.value = { ...intradayMacd.value, [symbol]: data.macd }
      } else {
        intradayMacd.value = { ...intradayMacd.value, [symbol]: Array.isArray(data) ? data : [] }
      }
    } catch (e) {
      console.error(`获取 ${symbol} MACD 失败:`, e.message)
    }
  }

  async function fetchAllIntraday() {
    const tasks = watchlist.value.map((item) =>
      Promise.all([
        fetchIntradayData(item.symbol),
        fetchIntradayMacd(item.symbol)
      ])
    )
    await Promise.all(tasks)
  }

  function reorderCards(fromIdx, toIdx) {
    const items = sortedWatchlist.value
    const order = items.map(i => i.symbol)
    const [moved] = order.splice(fromIdx, 1)
    order.splice(toIdx, 0, moved)
    cardOrder.value = order
    localStorage.setItem('stock-card-order', JSON.stringify(order))
  }

  function resetOrder() {
    cardOrder.value = []
    localStorage.removeItem('stock-card-order')
  }

  return {
    cardOrder,
    watchlist,
    quotes,
    intradayData,
    intradayMacd,
    loading,
    errors,
    watchlistWithQuotes,
    sortedWatchlist,
    fetchWatchlist,
    addStocks,
    removeStock,
    fetchAllQuotes,
    fetchIntradayData,
    fetchIntradayMacd,
    fetchAllIntraday,
    reorderCards,
    resetOrder
  }
})
