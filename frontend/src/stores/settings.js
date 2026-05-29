import { defineStore } from 'pinia'
import { ref, watch, computed } from 'vue'

const STORAGE_KEY = 'stock-alert-settings'

export const useSettingsStore = defineStore('settings', () => {
  // 'cn' = 红涨绿跌,  'intl' = 绿涨红跌
  const theme = ref('cn')
  const fastRefresh = ref(true)  // 交易时段快速刷新
  const alertMode = ref('beep')  // off | beep | voice

  // ---- load from localStorage ----
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}')
    if (saved.theme) theme.value = saved.theme
    if (saved.fastRefresh !== undefined) fastRefresh.value = saved.fastRefresh
    if (saved.alertMode) alertMode.value = saved.alertMode
  } catch {}

  // ---- persist ----
  watch(alertMode, (v) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ theme: theme.value, fastRefresh: fastRefresh.value, alertMode: v }))
  })

  watch(theme, (v) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ theme: theme.value, fastRefresh: fastRefresh.value, alertMode: alertMode.value }))
    applyTheme(v)
  }, { immediate: true })

  function applyTheme(t) {
    const root = document.documentElement
    if (t === 'cn') {
      root.style.setProperty('--price-up', '#f85149')    // red
      root.style.setProperty('--price-down', '#3fb950')  // green
    } else {
      root.style.setProperty('--price-up', '#3fb950')    // green
      root.style.setProperty('--price-down', '#f85149')  // red
    }
  }

  // ---- trading hours helper ----
  function isTradingHours() {
    const now = new Date()
    const day = now.getDay()
    if (day === 0 || day === 6) return false  // weekend
    const h = now.getHours()
    const m = now.getMinutes()
    const mins = h * 60 + m
    // 9:15 - 11:30, 13:00 - 15:00
    return (mins >= 9 * 60 + 15 && mins <= 11 * 60 + 30) ||
           (mins >= 13 * 60 && mins <= 15 * 60)
  }

  /** Refresh interval in ms based on trading hours */
  const refreshInterval = computed(() => (fastRefresh.value && isTradingHours()) ? 5000 : 30000)

  return { theme, fastRefresh, alertMode, refreshInterval, isTradingHours }
})
