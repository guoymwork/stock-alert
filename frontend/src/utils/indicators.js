/**
 * 计算 EMA (指数移动平均)
 */
export function calculateEMA(data, period) {
  if (!data || data.length === 0) return []
  const k = 2 / (period + 1)
  const ema = [data[0]]
  for (let i = 1; i < data.length; i++) {
    ema.push(data[i] * k + ema[i - 1] * (1 - k))
  }
  return ema
}

/**
 * 计算 MACD
 * @param {number[]} closes - 收盘价数组
 * @param {number} fast - 快线周期 (默认 12)
 * @param {number} slow - 慢线周期 (默认 26)
 * @param {number} signal - 信号线周期 (默认 9)
 * @returns {{ dif: number[], dea: number[], macd: number[] }}
 */
export function calculateMACD(closes, fast = 12, slow = 26, signal = 9) {
  if (!closes || closes.length < slow) {
    return { dif: [], dea: [], macd: [] }
  }

  const emaFast = calculateEMA(closes, fast)
  const emaSlow = calculateEMA(closes, slow)

  const dif = emaFast.map((v, i) => v - emaSlow[i])
  const dea = calculateEMA(dif, signal)
  const macd = dif.map((v, i) => 2 * (v - dea[i]))

  return { dif, dea, macd }
}

/**
 * 检测 MACD 金叉/死叉
 * @param {{ time: string, dif: number, dea: number, macd: number }[]} macdData
 * @returns {'golden_cross' | 'death_cross' | 'none'}
 */
export function detectCrossover(macdData) {
  if (!macdData || macdData.length < 2) return 'none'

  const len = macdData.length
  const prev = macdData[len - 2]
  const curr = macdData[len - 1]

  if (!prev || !curr) return 'none'

  const prevDiff = prev.dif - prev.dea
  const currDiff = curr.dif - curr.dea

  // DIF 从下穿上 DEA → 金叉
  if (prevDiff <= 0 && currDiff > 0) return 'golden_cross'
  // DIF 从上穿下 DEA → 死叉
  if (prevDiff >= 0 && currDiff < 0) return 'death_cross'

  return 'none'
}
