<template>
  <button
    type="button"
    @click="toggleTheme"
    :title="buttonTitle"
    :aria-label="buttonTitle"
    class="md-icon-button focus:outline-none"
  >
    <!-- 日间模式图标（太阳） -->
    <svg
      v-if="!isDark"
      xmlns="http://www.w3.org/2000/svg"
      class="h-5 w-5"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
    >
      <circle cx="12" cy="12" r="4" />
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        d="M12 2v2m0 16v2M4.93 4.93l1.41 1.41m11.32 11.32l1.41 1.41M2 12h2m16 0h2M4.93 19.07l1.41-1.41m11.32-11.32l1.41-1.41"
      />
    </svg>

    <!-- 夜间模式图标（月亮） -->
    <svg
      v-else
      xmlns="http://www.w3.org/2000/svg"
      class="h-5 w-5"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
    >
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"
      />
    </svg>
  </button>
</template>

<script setup>
import { computed } from 'vue'
import { useTheme } from '../theme.js'

const { themeMode, isDark, toggleTheme } = useTheme()

const buttonTitle = computed(() => {
  const modeLabel = isDark.value ? '夜间模式' : '日间模式'
  const autoSuffix = themeMode.value === 'system' ? '（跟随系统）' : ''
  const nextLabel = isDark.value ? '日间模式' : '夜间模式'
  return `当前：${modeLabel}${autoSuffix}，点击切换至${nextLabel}`
})
</script>
