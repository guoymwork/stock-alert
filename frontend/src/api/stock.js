import axios from 'axios'

const client = axios.create({
  baseURL: '/api',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' }
})

function toCamelCase(str) {
  return str.replace(/_([a-z])/g, (_, c) => c.toUpperCase())
}

function camelizeKeys(obj) {
  if (Array.isArray(obj)) return obj.map(camelizeKeys)
  if (obj && typeof obj === 'object' && !(obj instanceof Date)) {
    return Object.fromEntries(
      Object.entries(obj).map(([k, v]) => [toCamelCase(k), camelizeKeys(v)])
    )
  }
  return obj
}

client.interceptors.response.use(
  (res) => {
    const data = res.data
    if (data && typeof data === 'object' && 'data' in data) {
      return camelizeKeys(data.data)
    }
    return camelizeKeys(data)
  },
  (err) => {
    const msg = err.response?.data?.detail || err.message || '请求失败'
    return Promise.reject(new Error(msg))
  }
)

export function getQuote(symbol, market) {
  return client.get(`/stocks/quote/${symbol}`, { params: { market } })
}

export function getIntradayData(symbol, market) {
  return client.get(`/stocks/intraday/${symbol}`, { params: { market } })
}

export function getKlineData(symbol, period = 'daily', startDate = '', endDate = '', market) {
  return client.get(`/stocks/kline/${symbol}`, {
    params: { period, start: startDate, end: endDate, market }
  })
}

export function getMacdData(symbol, period = 'daily', startDate = '', endDate = '', market) {
  return client.get(`/stocks/macd/${symbol}`, {
    params: { period, start: startDate, end: endDate, market }
  })
}

export function getIntradayMacd(symbol, market) {
  return client.get(`/stocks/intraday-macd/${symbol}`, { params: { market } })
}

/** Batch quotes: symbols = "000001@SH,399006@SZ" */
export function getBatchQuotes(symbols) {
  return client.get('/stocks/batch-quotes', { params: { symbols } })
}

export function getWatchlist() {
  return client.get('/watchlist')
}

export function addToWatchlist(codes) {
  return client.post('/watchlist/batch', { codes })
}

export function removeFromWatchlist(symbol, market) {
  return client.delete(`/watchlist/${symbol}`, { params: { market } })
}

// ---- Annotations ----
export function getAnnotations(symbol, market) {
  return client.get(`/annotations/${symbol}`, { params: { market } })
}

export function addAnnotation({ symbol, market, time, price, text }) {
  return client.post('/annotations', { symbol, market, time, price, text })
}

export function deleteAnnotation(id) {
  return client.delete(`/annotations/${id}`)
}

export function searchStocks(q) {
  return client.get('/stocks/search', { params: { q } })
}

