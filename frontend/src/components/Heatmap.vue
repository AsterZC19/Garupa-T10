<template>
  <div class="heatmap">
    <!-- 标签 + 格子整组：左「现在」右「48h前」，与 LiveBoost hourly 时速榜布局一致 -->
    <div class="flex items-center gap-1.5">
      <span class="heatmap-edge-label flex-shrink-0">{{ t('heatmap.now') }}</span>

      <!-- 格子区：桌面铺满，窄屏最小格宽保证可读，超出横向滚动 -->
      <div class="flex-1 min-w-0 overflow-x-auto heatmap-scroll">
        <div class="heatmap-grid" :style="{ gridTemplateColumns: `repeat(${hours}, minmax(14px, 1fr))` }">
          <div
            v-for="cell in cells"
            :key="cell.index"
            class="heatmap-cell"
            :style="cellStyle(cell)"
            :title="cellTitle(cell)"
          >
            {{ cell.value > 0 ? cell.value : '' }}
          </div>
        </div>
      </div>

      <span class="heatmap-edge-label flex-shrink-0">{{ t('heatmap.ago48h') }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { heatColor } from '../utils.js'
import { isDark } from '../theme.js'
import { useI18n } from '../i18n.js'

const { t } = useI18n()

const props = defineProps({
  counts: { type: Array, default: () => [] },   // index 0 最旧
  refTs: { type: [Number, null], default: null }, // 最新格子的起始 UTC 毫秒，用于本地时区换算
  globalMax: { type: Number, default: 0 },
})

const hours = computed(() => props.counts.length)

// 最新在左、最旧在右（与 LiveBoost 一致）
const cells = computed(() => {
  const arr = []
  for (let i = hours.value - 1; i >= 0; i--) {
    arr.push({ index: i, value: props.counts[i] ?? 0 })
  }
  return arr
})

function cellStyle(cell) {
  const intensity = props.globalMax > 0 ? cell.value / props.globalMax : 0
  const { bg, fg } = heatColor(intensity, isDark.value)
  return { backgroundColor: bg, color: fg }
}

// 每个格子的墙钟标签：用 refTs 换算成浏览器本地时区，与「时速曲线」图一致
function localHourLabel(i) {
  const startUtcMs = props.refTs - (hours.value - 1 - i) * 3600000
  const d = new Date(startUtcMs)
  const pad = n => String(n).padStart(2, '0')
  return `${pad(d.getMonth() + 1)}/${pad(d.getDate())} ${pad(d.getHours())}:00`
}

function cellTitle(cell) {
  const label = localHourLabel(cell.index)
  return t(cell.value === 1 ? 'heatmap.cellTooltipOne' : 'heatmap.cellTooltip', { label, count: cell.value })
}
</script>

<style scoped>
.heatmap-scroll {
  scrollbar-width: thin;
}

.heatmap-grid {
  display: grid;
  gap: 1.5px;
  width: 100%;
  min-width: max-content;
}

.heatmap-cell {
  aspect-ratio: 2.4 / 1; /* 扁色条，但比 3:1 稍高，保证可读 */
  border-radius: 2px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 7px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  line-height: 1;
  cursor: default;
  transition: filter 0.1s ease;
  min-width: 14px;
}

.heatmap-cell:hover {
  filter: brightness(1.15);
  position: relative;
}

.heatmap-edge-label {
  font-size: 9px;
  color: var(--md-sys-color-on-surface-variant);
  white-space: nowrap;
}
</style>
