import { ref, computed, watchEffect } from 'vue'

const STORAGE_KEY = 'garupa-theme-mode'

// 'system' | 'light' | 'dark'
function getInitialMode() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved === 'light' || saved === 'dark' || saved === 'system') {
      return saved
    }
  } catch (_) {
    // ignore storage errors
  }
  return 'system'
}

const darkMedia =
  typeof window !== 'undefined' && window.matchMedia
    ? window.matchMedia('(prefers-color-scheme: dark)')
    : null

const systemDark = ref(darkMedia ? darkMedia.matches : false)
const themeMode = ref(getInitialMode())

export const isDark = computed(() => {
  if (themeMode.value === 'system') {
    return systemDark.value
  }
  return themeMode.value === 'dark'
})

function applyThemeToDom(dark) {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  root.classList.toggle('dark', dark)
  root.classList.toggle('light', !dark)
  root.dataset.theme = dark ? 'dark' : 'light'

  const metaThemeColor = document.querySelector('meta[name="theme-color"]')
  if (metaThemeColor) {
    metaThemeColor.setAttribute('content', dark ? '#1b1f2a' : '#f1f4f8')
  }
}

export function setThemeMode(mode) {
  themeMode.value = mode
  try {
    if (mode === 'system') {
      localStorage.removeItem(STORAGE_KEY)
    } else {
      localStorage.setItem(STORAGE_KEY, mode)
    }
  } catch (_) {
    // ignore storage errors
  }
  applyThemeToDom(isDark.value)
}

if (darkMedia) {
  const onSystemChange = (e) => {
    systemDark.value = e.matches
    // 系统日夜环境本身发生变化时，自动同步跟随系统
    setThemeMode('system')
  }
  if (darkMedia.addEventListener) {
    darkMedia.addEventListener('change', onSystemChange)
  } else if (darkMedia.addListener) {
    darkMedia.addListener(onSystemChange)
  }
}

watchEffect(() => {
  applyThemeToDom(isDark.value)
})

export function toggleTheme() {
  const nextDark = !isDark.value
  // 若手动切换后的状态与系统当前状态一致，则自动归回 'system' 模式
  if (nextDark === systemDark.value) {
    setThemeMode('system')
  } else {
    setThemeMode(nextDark ? 'dark' : 'light')
  }
}

export function useTheme() {
  return {
    themeMode,
    systemDark,
    isDark,
    setThemeMode,
    toggleTheme,
  }
}
