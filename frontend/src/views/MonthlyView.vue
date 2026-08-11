<template>
  <div class="p-4 sm:p-6 max-w-7xl mx-auto">
    <!-- 顶部：切换 + 月榜选择 + 刷新 -->
    <header class="flex items-center justify-between mb-4 gap-2">
      <div class="flex items-center gap-3 min-w-0">
        <ModeToggle model-value="monthly" @update:model-value="goEvent" />
        <MdSelect
          :options="monthlyOptions"
          v-model="selectedMonthlyId"
          class="w-full max-w-[300px] sm:max-w-sm"
          placeholder="选择月榜"
        />
      </div>
      <button @click="forceRefresh" :disabled="isRefreshing || isUpcoming" class="md-filled-button flex-shrink-0 min-w-28">
        <span>{{ refreshButtonText }}</span>
      </button>
    </header>

    <!-- 月榜信息卡 -->
    <section v-if="currentMonthly" class="mb-6" :class="{ 'opacity-50': isRefreshing }">
      <div class="md-elevated-card p-5 flex flex-col-reverse md:flex-row items-center md:items-stretch justify-between gap-5">
        <div class="flex-grow flex flex-col text-center min-w-0">
          <div class="flex flex-col justify-center flex-1">
            <h1 class="text-2xl font-bold mb-2 event-title bg-clip-text text-transparent bg-gradient-to-r from-sky-400 to-pink-400 hover:scale-105 transition-transform">
              {{ currentMonthly.name || '月榜' }}
            </h1>
            <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-md-on-surface-variant justify-center mb-2">
              <span class="md-chip md-chip--primary">月榜</span>
              <span>开始: {{ formatTs(currentMonthly.start_at) }}</span>
              <span>结束: {{ formatTs(currentMonthly.end_at) }}</span>
              <span v-if="isUpcoming" class="md-chip">⏳ 未开始</span>
            </div>
          </div>
          <div class="text-center text-xs text-md-on-surface-variant mt-3">
            月榜数据由
            <a href="https://bestdori.com" target="_blank" rel="noopener" class="underline hover:text-md-primary">Bestdori</a>
            官方游戏接口提供
          </div>
        </div>
        <div v-if="currentMonthly.banner_url" class="flex-shrink-0 flex items-center max-w-full">
          <img :src="currentMonthly.banner_url" alt="Monthly Ranking Banner" class="max-w-full h-auto rounded-xl" />
        </div>
      </div>
    </section>

    <main class="space-y-8">
      <!-- T10 时速 + 热力图 -->
      <div v-if="!isUpcoming" :class="{ 'opacity-50': isRefreshing }">
        <h3 class="md-section-title mb-3">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 md-section-title-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          月榜 T10 时速
        </h3>
        <TopPlayersTable :players="topPlayers" :heatmap-data="heatmapData" />
      </div>

      <!-- 月榜曲线 -->
      <div v-if="!isUpcoming">
        <div class="flex items-center justify-between mb-4">
          <h3 class="md-section-title">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 md-section-title-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M3 13h2l3-8 4 12 3-6 2 2h4" />
            </svg>
            月榜 PT 曲线
          </h3>
        </div>
        <div class="md-elevated-card p-4">
          <div v-if="isChartLoading" class="h-[700px] sm:h-[800px] md:h-[900px] flex items-center justify-center text-md-on-surface-variant">
            <span class="animate-pulse">图表加载中...</span>
          </div>
          <ChartComponent v-else :series="chartSeries" :current-event="chartEvent" />
        </div>
      </div>

      <!-- 未开始占位 -->
      <div v-if="isUpcoming" class="md-elevated-card p-10 text-center">
        <div class="text-2xl font-bold mb-2">📅 本月榜暂未开始</div>
        <div class="text-sm text-md-on-surface-variant mb-4">距离开始还有</div>
        <div class="text-5xl font-bold tabular-nums text-md-primary">{{ countdownText }}</div>
      </div>

      <!-- 页脚 -->
      <footer class="pt-6 text-center text-xs text-md-on-surface-variant">
        由 <span>🎵</span> 构建 /
        <a href="https://github.com/AsterZC19/Garupa-T10" target="_blank" rel="noopener" class="underline hover:text-md-primary">
          GitHub
        </a>
      </footer>
    </main>
  </div>
</template>

<script setup>
import api from '../api'
import ModeToggle from '../components/ModeToggle.vue'
import MdSelect from '../components/MdSelect.vue'
import TopPlayersTable from '../components/TopPlayersTable.vue'
import ChartComponent from '../components/ChartComponent.vue'
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { formatTs } from '../utils.js'

const route = useRoute()
const router = useRouter()

const monthlyList = ref([])
const selectedMonthlyId = ref(null)
const currentMonthly = ref(null)
const nowTs = ref(Date.now())
const topPlayers = ref([])
const chartSeries = ref({})
const heatmapData = ref({ ref_ts: null, global_max: 0, players: {} })
const lastTopPlayersContext = ref(null)
const isInitialLoad = ref(true)

const monthlyOptions = computed(() =>
  (monthlyList.value || []).map(m => ({
    value: String(m.monthly_id),  // 与 selectedMonthlyId（字符串）严格匹配，和活动选择器一致
    label: `${m.monthly_id} - ${m.name || ''} (${formatTs(m.start_at)})`,
  }))
)

const isUpcoming = computed(() => {
  if (!currentMonthly.value) return false
  return nowTs.value < currentMonthly.value.start_at
})

// ChartComponent 需要 currentEvent 来设置时间轴范围/缩放边界
const chartEvent = computed(() => {
  if (!currentMonthly.value) return null
  return {
    event_id: `monthly_${currentMonthly.value.monthly_id}`,
    start_at: currentMonthly.value.start_at,
    end_at: currentMonthly.value.end_at,
  }
})

const countdownText = computed(() => {
  if (!isUpcoming.value || !currentMonthly.value) return ''
  const ms = currentMonthly.value.start_at - nowTs.value
  if (ms <= 0) return '00 日 00 时 00 分 00 秒'
  const totalSec = Math.floor(ms / 1000)
  const d = Math.floor(totalSec / 86400)
  const h = Math.floor((totalSec % 86400) / 3600)
  const m = Math.floor((totalSec % 3600) / 60)
  const s = totalSec % 60
  const pad = n => String(n).padStart(2, '0')
  return `${pad(d)} 日 ${pad(h)} 时 ${pad(m)} 分 ${pad(s)} 秒`
})

const isRefreshing = ref(false)
const isChartLoading = ref(false)
const refreshInterval = ref(null)
const REFRESH_INTERVAL_SECONDS = 2 * 60
const countdown = ref(REFRESH_INTERVAL_SECONDS)

const refreshButtonText = computed(() => {
  if (isRefreshing.value) return '刷新中...'
  if (isChartLoading.value) return '图表加载中...'
  return `刷新 (${countdown.value}s)`
})

function goEvent() {
  router.push({ name: 'Home' })
}

async function loadChartDataAsync(mid, interval) {
  if (!mid) return
  isChartLoading.value = true
  try {
    const res = await api.get(`/api/monthly/${mid}/chart?interval=${interval}`)
    chartSeries.value = res.data
  } catch (error) {
    console.error('获取月榜图表数据失败:', error)
    chartSeries.value = {}
  } finally {
    isChartLoading.value = false
  }
}

async function loadHeatmapData(mid, uids = []) {
  if (!mid) return
  try {
    const params = new URLSearchParams()
    if (uids && uids.length) params.append('uids', uids.join(','))
    const res = await api.get(`/api/monthly/${mid}/heatmap?${params.toString()}`)
    heatmapData.value = res.data
  } catch (error) {
    console.error('获取月榜热力图数据失败:', error)
    heatmapData.value = { ref_ts: null, global_max: 0, players: {} }
  }
}

async function loadMonthlyData(mid, force = false, loadChart = true) {
  if (!mid) return
  isRefreshing.value = true
  try {
    const eventParams = new URLSearchParams()
    if (force) eventParams.append('force', 'true')

    let detailRes
    try {
      detailRes = await api.get(`/api/monthly/${mid}`)
    } catch (error) {
      if (error?.response?.status === 404) {
        router.replace({ name: 'NotFound' })
        return
      }
      throw error
    }
    currentMonthly.value = detailRes.data

    if (isUpcoming.value) {
      topPlayers.value = []
      heatmapData.value = { ref_ts: null, global_max: 0, players: {} }
      chartSeries.value = {}
      return
    }

    const topPlayersParams = new URLSearchParams()
    topPlayersParams.set('limit', 10)
    topPlayersParams.set('refresh', 'true')
    if (force) topPlayersParams.set('force', 'true')

    const topPlayersRes = await api.get(`/api/monthly/${mid}/top_players?${topPlayersParams.toString()}`)

    const displayedUids = (topPlayersRes.data || []).map(p => p.uid)
    if (displayedUids.length > 0) {
      await loadHeatmapData(mid, displayedUids)
    } else {
      heatmapData.value = { ref_ts: null, global_max: 0, players: {} }
    }

    const contextKey = `monthly-${mid}`
    const previousPlayers = lastTopPlayersContext.value === contextKey
      ? new Map(topPlayers.value.map(p => [p.uid, p]))
      : new Map()

    topPlayers.value = topPlayersRes.data.map(player => {
      const prev = previousPlayers.get(player.uid)
      const ptIncrease = prev && typeof player.pt === 'number' && typeof prev.pt === 'number'
        ? player.pt - prev.pt
        : null
      return { ...player, ptIncrease }
    })
    lastTopPlayersContext.value = contextKey
  } catch (error) {
    console.error('获取月榜数据失败:', error)
    topPlayers.value = []
  } finally {
    isRefreshing.value = false
    countdown.value = REFRESH_INTERVAL_SECONDS
  }

  if (loadChart && !isUpcoming.value) {
    loadChartDataAsync(mid, '15m')
  }
}

async function forceRefresh() {
  if (selectedMonthlyId.value && !isRefreshing.value) {
    await loadMonthlyData(selectedMonthlyId.value, true)
  }
}

async function loadMonthlyList() {
  try {
    const res = await api.get('/api/monthly/')
    const list = res.data.sort((a, b) => b.monthly_id - a.monthly_id)
    monthlyList.value = list
    return list
  } catch (error) {
    console.error('获取月榜列表失败:', error)
    return []
  }
}

watch(selectedMonthlyId, (newId) => {
  // 用路径导航（/monthly/{id}），确保路由参数更新触发加载
  if (newId && String(newId) !== String(route.params.monthlyId)) {
    router.push(`/monthly/${String(newId)}`)
  }
})

watch(() => route.params.monthlyId, (newId) => {
  const newMid = newId ? String(newId) : null
  selectedMonthlyId.value = newMid
  if (newMid) {
    const force = isInitialLoad.value
    isInitialLoad.value = false
    loadMonthlyData(newMid, force)
  }
}, { immediate: true })

function isPeriodEnded() {
  if (!currentMonthly.value) return true
  return Date.now() > currentMonthly.value.end_at + 3600000
}

onMounted(async () => {
  const list = await loadMonthlyList()
  if (!route.params.monthlyId) {
    try {
      const cur = await api.get('/api/monthly/current')
      if (cur.status === 200 && cur.data.monthly_id) {
        router.replace(`/monthly/${cur.data.monthly_id}`)
      } else if (list.length > 0) {
        router.replace(`/monthly/${list[0].monthly_id}`)
      }
    } catch (error) {
      if (list.length > 0) {
        router.replace(`/monthly/${list[0].monthly_id}`)
      }
    }
  }

  countdown.value = REFRESH_INTERVAL_SECONDS
  refreshInterval.value = setInterval(() => {
    nowTs.value = Date.now()
    if (isRefreshing.value) return
    if (document.hidden) return
    if (countdown.value > 0) {
      countdown.value--
    } else {
      if (!isPeriodEnded() && !isUpcoming.value) {
        loadMonthlyData(selectedMonthlyId.value, false, false)
      }
      countdown.value = REFRESH_INTERVAL_SECONDS
    }
  }, 1000)

  if (!isPeriodEnded()) {
    countdown.value = 10
  }
})

onUnmounted(() => {
  if (refreshInterval.value) clearInterval(refreshInterval.value)
})
</script>

<style>
.event-title {
  text-shadow: 0 0 1px rgba(0, 0, 0, 0.1);
  animation: titleFade 0.5s ease-in-out;
}

@keyframes titleFade {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
