<template>
  <div class="p-4 sm:p-6 max-w-7xl mx-auto">
    <!-- 顶部：活动选择 + 刷新 -->
    <header class="flex items-center justify-between mb-4 gap-2">
      <div class="flex-1 min-w-0">
        <EventSelector :events="events" v-model="selectedEventId" class="w-full" />
      </div>
      <button @click="forceRefresh" :disabled="isRefreshing || isUpcoming" class="md-filled-button flex-shrink-0 min-w-28">
        <span>{{ refreshButtonText }}</span>
      </button>
    </header>

    <!-- 活动信息卡 -->
    <section v-if="currentEvent" class="mb-6" :class="{ 'opacity-50': isRefreshing }">
      <div class="md-elevated-card p-5 flex flex-col-reverse md:flex-row items-center md:items-stretch justify-between gap-5">
        <div class="flex-grow flex flex-col text-center min-w-0">
          <div class="flex flex-col justify-center flex-1">
            <h1 class="text-2xl font-bold mb-2 event-title bg-clip-text text-transparent bg-gradient-to-r from-sky-400 to-pink-400 hover:scale-105 transition-transform">
              {{ eventName }}
            </h1>
            <div class="flex flex-wrap gap-x-4 gap-y-1 text-sm text-md-on-surface-variant justify-center mb-2">
              <span class="md-chip md-chip--primary">{{ eventTypeZh(currentEvent.type) }}</span>
              <span>开始: {{ formatTs(currentEvent.start_at) }}</span>
              <span>结束: {{ formatTs(currentEvent.end_at) }}</span>
              <span v-if="isUpcoming" class="md-chip">⏳ 未开始</span>
            </div>
            <p v-if="!isCurrent && !isUpcoming" class="text-sm mt-2 text-md-error">
              当前未有进行中的活动（显示最近活动）
            </p>
          </div>
          <div class="text-center text-xs text-md-on-surface-variant mt-3">
            感谢
            <a href="https://bestdori.com" target="_blank" rel="noopener" class="underline hover:text-md-primary">Bestdori</a>
            提供数据
          </div>
        </div>
        <div v-if="currentEvent.banner_url" class="flex-shrink-0 flex items-center max-w-full">
          <img :src="currentEvent.banner_url" alt="Event Banner" class="max-w-full h-auto rounded-xl" />
        </div>
      </div>
    </section>

    <main class="space-y-8">
      <!-- T10 时速 · 每位玩家一行 + 下方热力图，十人连成一张卡片 -->
      <div v-if="!isUpcoming" :class="{ 'opacity-50': isRefreshing }">
        <h3 class="md-section-title mb-3">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 md-section-title-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          T10 时速
        </h3>
        <TopPlayersTable :players="topPlayers" :heatmap-data="heatmapData" />
      </div>

      <!-- 时速曲线 -->
      <div v-if="!isUpcoming">
        <div class="flex items-center justify-between mb-4">
          <h3 class="md-section-title">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 md-section-title-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M3 13h2l3-8 4 12 3-6 2 2h4" />
            </svg>
            时速曲线
          </h3>
        </div>
        <div class="md-elevated-card p-4">
          <div v-if="isChartLoading" class="h-[700px] sm:h-[800px] md:h-[900px] flex items-center justify-center text-md-on-surface-variant">
            <span class="animate-pulse">图表加载中...</span>
          </div>
          <ChartComponent v-else :series="chartSeries" :current-event="currentEvent" />
        </div>
      </div>

      <!-- 活动暂未开始：数据区占位 + 倒计时 -->
      <div v-if="isUpcoming" class="md-elevated-card p-10 text-center">
        <div class="text-2xl font-bold mb-2">🎵 活动暂未开始</div>
        <div class="text-sm text-md-on-surface-variant mb-4">距离活动开始还有</div>
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
import EventSelector from '../components/EventSelector.vue'
import TopPlayersTable from '../components/TopPlayersTable.vue'
import ChartComponent from '../components/ChartComponent.vue'
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { formatTs } from '../utils.js'

const route = useRoute()
const router = useRouter()

const events = ref([])
const selectedEventId = ref(null)
const selectedHour = ref(null)
const currentEvent = ref(null)
const isCurrent = ref(true)
const nowTs = ref(Date.now())   // 每秒更新，用于「活动暂未开始」倒计时
const topPlayers = ref([])
const chartSeries = ref({})
const heatmapData = ref({ ref_ts: null, global_max: 0, players: {} })
const lastTopPlayersContext = ref(null)
const isInitialEventLoad = ref(true)

const eventName = computed(() => currentEvent.value ? currentEvent.value.name : '加载中...')

// 该活动是否尚未开始（远端已给出新活动，但未到 start_at）
const isUpcoming = computed(() => {
  if (!currentEvent.value) return false
  return nowTs.value < currentEvent.value.start_at
})

// 距离活动开始的倒计时文本
const countdownText = computed(() => {
  if (!isUpcoming.value || !currentEvent.value) return ''
  const ms = currentEvent.value.start_at - nowTs.value
  if (ms <= 0) return '0 天 00:00:00'
  const totalSec = Math.floor(ms / 1000)
  const d = Math.floor(totalSec / 86400)
  const h = Math.floor((totalSec % 86400) / 3600)
  const m = Math.floor((totalSec % 3600) / 60)
  const s = totalSec % 60
  const pad = n => String(n).padStart(2, '0')
  return `${d} 天 ${pad(h)}:${pad(m)}:${pad(s)}`
})

const isRefreshing = ref(false)
const isChartLoading = ref(false)
const refreshInterval = ref(null)
const REFRESH_INTERVAL_SECONDS = 2 * 60; // 2 minutes
const countdown = ref(REFRESH_INTERVAL_SECONDS);

const refreshButtonText = computed(() => {
  if (isRefreshing.value) {
    return '刷新中...';
  }
  if (isChartLoading.value) {
    return '图表加载中...';
  }
  return `刷新 (${countdown.value}s)`;
});

async function loadChartDataAsync(eid, interval) {
  if (!eid) return
  isChartLoading.value = true
  try {
    const res = await api.get(`/api/events/${eid}/chart?interval=${interval}`)
    chartSeries.value = res.data
  } catch (error) {
    console.error(`获取图表数据失败 (interval: ${interval}):`, error)
    chartSeries.value = {}
  } finally {
    isChartLoading.value = false
  }
}

async function loadHeatmapData(eid, uids = []) {
  if (!eid) return
  try {
    // 传表格正在展示的玩家 uid，后端只返回这些玩家并据此归一化颜色
    const params = new URLSearchParams()
    if (uids && uids.length) {
      params.append('uids', uids.join(','))
    }
    const res = await api.get(`/api/events/${eid}/heatmap?${params.toString()}`)
    heatmapData.value = res.data
  } catch (error) {
    console.error('获取热力图数据失败:', error)
    heatmapData.value = { ref_ts: null, global_max: 0, players: {} }
  }
}

async function loadTableData(eid, hour, force = false, loadChart = true) {
  if (!eid) return
  isRefreshing.value = true
  try {
    const eventParams = new URLSearchParams();
    if (force) {
      eventParams.append('force', 'true');
    }
    const eventRes = await api.get(`/api/events/${eid}?${eventParams.toString()}`)
    currentEvent.value = eventRes.data
    const nowMs = Date.now()
    isCurrent.value = nowMs >= eventRes.data.start_at && nowMs <= eventRes.data.end_at

    // 未开始的活动：没有榜单/热力图/曲线数据，跳过后续请求（倒计时归零时再拉）
    if (isUpcoming.value) {
      topPlayers.value = []
      heatmapData.value = { ref_ts: null, global_max: 0, players: {} }
      chartSeries.value = {}
      return
    }

    const params = new URLSearchParams()
    if (hour !== null) {
      params.append('hour', hour)
    }

    const topPlayersParams = new URLSearchParams(params)
    topPlayersParams.set('limit', 10)
    topPlayersParams.set('interval', 60000)
    topPlayersParams.set('refresh', 'true')
    if (force) {
      topPlayersParams.set('force', 'true')
    }

    const topPlayersRes = await api.get(`/api/events/${eid}/top_players?${topPlayersParams.toString()}`)

    // 用表格正在展示的玩家 uid 去取热力图，保证热力图与展示行、颜色归一化一致
    const displayedUids = (topPlayersRes.data || []).map(player => player.uid)
    if (displayedUids.length > 0) {
      await loadHeatmapData(eid, displayedUids)
    } else {
      heatmapData.value = { ref_ts: null, global_max: 0, players: {} }
    }

    const contextKey = `${eid}-${hour ?? 'latest'}`
    const previousPlayers = lastTopPlayersContext.value === contextKey
      ? new Map(topPlayers.value.map(player => [player.uid, player]))
      : new Map()

    topPlayers.value = topPlayersRes.data.map(player => {
      const previousPlayer = previousPlayers.get(player.uid)
      const ptIncrease = previousPlayer
        && typeof player.pt === 'number' && typeof previousPlayer.pt === 'number'
        ? player.pt - previousPlayer.pt
        : null

      return {
        ...player,
        ptIncrease,
      }
    })
    lastTopPlayersContext.value = contextKey
  } catch (error) {
    console.error('获取活动数据失败:', error)
    topPlayers.value = []
  } finally {
    isRefreshing.value = false
    countdown.value = REFRESH_INTERVAL_SECONDS;
  }

  // Chart data loads after table is visible (slow, don't block UI)；
  // 未开始的活动没有图表数据，跳过
  if (loadChart && !isUpcoming.value) {
    loadChartDataAsync(eid, '15m')
  }
}

async function forceRefresh() {
  if (selectedEventId.value && !isRefreshing.value) {
    await loadTableData(selectedEventId.value, selectedHour.value, true);
  }
}

async function loadEventsList() {
  try {
    const res = await api.get('/api/events/')
    const sortedEvents = res.data.sort((a, b) => b.event_id - a.event_id)
    events.value = sortedEvents
    return sortedEvents
  } catch (error) {
    console.error('获取活动列表失败:', error)
    return []
  }
}

watch(selectedEventId, (newId) => {
  if (newId && newId !== String(route.params.eventId)) {
    router.push({ name: 'Event', params: { eventId: newId } })
  }
})

watch(() => route.params.eventId, (newId) => {
  // 统一用字符串存 selectedEventId，与 EventSelector 选项值（后端 event_id 为字符串）严格匹配
  const newEventId = newId ? String(newId) : null;
  selectedEventId.value = newEventId;
  if (newEventId) {
    const forceInitialRefresh = isInitialEventLoad.value;
    isInitialEventLoad.value = false;
    loadTableData(newEventId, selectedHour.value, forceInitialRefresh);
  }
}, { immediate: true });

// 倒计时归零那一刻（活动刚开始）立即拉一次数据；切换活动时的加载由 route watcher 负责
watch(isUpcoming, (up) => {
  if (up || !currentEvent.value) return
  const justStarted = nowTs.value - currentEvent.value.start_at < 5 * 60 * 1000
  if (justStarted && !isRefreshing.value && selectedEventId.value) {
    loadTableData(selectedEventId.value, selectedHour.value, true)
  }
})

function isEventEnded() {
  if (!currentEvent.value) return true
  const now = Date.now()
  return now > currentEvent.value.end_at + 3600000 // ended >1 hour ago
}

onMounted(async () => {
  const eventList = await loadEventsList();
  if (!route.params.eventId) {
    try {
      const cur = await api.get('/api/events/current')
      if (cur.status === 200 && cur.data.event) {
        router.replace({ name: 'Event', params: { eventId: cur.data.event.event_id } })
      } else if (eventList.length > 0) {
        router.replace({ name: 'Event', params: { eventId: eventList[0].event_id } })
      }
    } catch (error) {
      if (eventList.length > 0) {
        router.replace({ name: 'Event', params: { eventId: eventList[0].event_id } })
      }
    }
  }

  // Set up auto-refresh
  countdown.value = REFRESH_INTERVAL_SECONDS;
  refreshInterval.value = setInterval(() => {
    nowTs.value = Date.now(); // 驱动「活动暂未开始」倒计时
    if (isRefreshing.value) return;
    // Pause refresh when tab is hidden
    if (document.hidden) return;

    if (countdown.value > 0) {
      countdown.value--;
    } else {
      // 只有进行中的活动才自动刷新；未开始的靠倒计时归零触发，已结束的不再拉取
      if (!isEventEnded() && !isUpcoming.value) {
        loadTableData(selectedEventId.value, selectedHour.value, false, false);
      }
      countdown.value = REFRESH_INTERVAL_SECONDS;
    }
  }, 1000);

  // Use shorter interval when event is active (burst mode for the first 10s)
  if (!isEventEnded()) {
    countdown.value = 10; // Initial quick refresh
  }
})

function onVisibilityChange() {
  if (!document.hidden && !isEventEnded() && countdown.value === REFRESH_INTERVAL_SECONDS) {
    // Tab just became visible, quick table refresh
    countdown.value = 5;
  }
}

// Separate visibility listener - need to add/remove manually since we're in setup
const visHandler = () => onVisibilityChange()
document.addEventListener('visibilitychange', visHandler)

onUnmounted(() => {
  if (refreshInterval.value) {
    clearInterval(refreshInterval.value);
  }
  document.removeEventListener('visibilitychange', visHandler)
})

function eventTypeZh(type) {
  switch (type) {
    case "live_try": return "Live 试炼"
    case "challenge": return "挑战 Live"
    case "mission_live": return "任务 Live"
    case "versus": return "竞演 Live"
    case "medley": return "组曲"
    case "festival": return "5 v 5"
    default: return type
  }
}
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
