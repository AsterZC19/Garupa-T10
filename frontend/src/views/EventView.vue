<template>
  <div class="p-4 sm:p-6 max-w-7xl mx-auto">
    <!-- 顶部：切换 + 刷新同一行；移动端活动选择框换行到下一行 -->
    <header class="flex flex-wrap items-center justify-between gap-2 mb-4">
      <ModeToggle model-value="event" @update:model-value="goMonthly" class="order-1" />
      <button @click="forceRefresh" :disabled="isRefreshing || isUpcoming" class="md-filled-button flex-shrink-0 min-w-28 order-2 md:order-3">
        <span>{{ refreshButtonText }}</span>
      </button>
      <EventSelector :events="events" v-model="selectedEventId" class="w-full order-3 md:order-2 md:w-auto md:flex-1" />
    </header>

    <!-- 活动信息卡 -->
    <section v-if="currentEvent" class="mb-6" :class="{ 'opacity-50': isRefreshing }">
      <div class="md-elevated-card p-5 flex flex-col-reverse md:flex-row items-center md:items-stretch justify-between gap-5">
        <div class="flex-grow flex flex-col text-center min-w-0">
          <div class="flex flex-col justify-center flex-1">
            <h1 class="text-2xl font-bold mb-2 event-title bg-clip-text text-transparent bg-gradient-to-r from-sky-400 to-pink-400 hover:scale-105 transition-transform">
              {{ eventName }}
            </h1>
            <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-md-on-surface-variant justify-center mb-2">
              <span class="md-chip md-chip--primary">{{ eventTypeLabel(currentEvent.type) }}</span>
              <span>{{ t('common.start') }}{{ formatTs(currentEvent.start_at) }}</span>
              <span>{{ t('common.end') }}{{ formatTs(currentEvent.end_at) }}</span>
              <span v-if="isUpcoming" class="md-chip">{{ t('common.upcomingChip') }}</span>
            </div>
          </div>
          <div class="text-center text-xs text-md-on-surface-variant mt-3">
            {{ t('event.bestdoriPrefix') }}
            <a href="https://bestdori.com" target="_blank" rel="noopener" class="underline hover:text-md-primary">Bestdori</a><template v-if="t('event.bestdoriSuffix')">{{ ' ' + t('event.bestdoriSuffix') }}</template>
          </div>
        </div>
        <div v-if="currentEvent.banner_url" class="flex-shrink-0 flex items-center max-w-full">
          <img :src="currentEvent.banner_url" alt="Event Banner" class="max-w-full h-auto rounded-xl" />
        </div>
      </div>
    </section>

    <main class="space-y-8">
      <!-- T10 时速 / 歌榜 T10 -->
      <div v-if="!isUpcoming" :class="{ 'opacity-50': isRefreshing }">
        <div class="flex flex-wrap items-center justify-between gap-2 mb-3 min-h-10">
          <div class="flex flex-wrap items-center gap-3">
            <h3 class="md-section-title">
              {{ rankingMode === 'song' ? t('event.songRankingTitle') : t('event.t10SpeedTitle') }}
            </h3>
            <div v-if="hasSongRanking" class="md-segmented" role="tablist">
              <button
                type="button"
                role="tab"
                :aria-selected="rankingMode === 'pt'"
                class="md-segmented-btn"
                :class="{ 'is-active': rankingMode === 'pt' }"
                @click="setRankingMode('pt')"
              >
                {{ t('event.tabPtRanking') }}
              </button>
              <button
                type="button"
                role="tab"
                :aria-selected="rankingMode === 'song'"
                class="md-segmented-btn"
                :class="{ 'is-active': rankingMode === 'song' }"
                @click="setRankingMode('song')"
              >
                {{ t('event.tabSongRanking') }}
              </button>
            </div>
          </div>

          <!-- 歌榜：单曲/组曲显示标签，多曲显示下拉选择 -->
          <div v-if="rankingMode === 'song' && hasSongRanking && !isSongRankingLoading" class="flex items-center gap-2">
            <MdSelect
              v-if="songOptions.length > 1"
              :options="songOptions"
              v-model="selectedSongId"
              class="w-56 sm:w-64"
              :placeholder="t('event.selectSongPlaceholder')"
            />
            <span v-else-if="activeSongLabel" class="md-chip md-chip--primary">
              {{ activeSongLabel }}
            </span>
          </div>
        </div>

        <TopPlayersTable v-if="rankingMode === 'pt'" :players="topPlayers" :heatmap-data="heatmapData" />
        <SongRankingTable
          v-else
          :entries="activeSong?.entries || []"
          :updated-at="activeSong?.updated_at ?? null"
          :loading="isSongRankingLoading"
        />
      </div>

      <!-- 时速曲线（仅肝榜模式显示） -->
      <div v-if="!isUpcoming && rankingMode === 'pt'">
        <div class="flex items-center justify-between mb-4">
          <h3 class="md-section-title">
            {{ t('event.speedCurveTitle') }}
          </h3>
        </div>
        <div class="md-elevated-card p-4">
          <div v-if="isChartLoading" class="h-[700px] sm:h-[800px] md:h-[900px] flex items-center justify-center text-md-on-surface-variant">
            <span class="animate-pulse">{{ t('common.chartLoading') }}</span>
          </div>
          <ChartComponent v-else :series="chartSeries" :current-event="currentEvent" />
        </div>
      </div>

      <!-- 活动暂未开始：数据区占位 + 倒计时 -->
      <div v-if="isUpcoming" class="md-elevated-card p-10 text-center">
        <div class="text-2xl font-bold mb-2">{{ t('event.upcomingTitle') }}</div>
        <div class="text-sm text-md-on-surface-variant mb-4">{{ t('event.upcomingSubtitle') }}</div>
        <div class="text-5xl font-bold tabular-nums text-md-primary">{{ countdownText }}</div>
      </div>

      <!-- 页脚 -->
      <footer class="pt-6 text-center text-xs text-md-on-surface-variant">
        {{ t('common.builtByPrefix') }}<span>Garupa T10</span>{{ t('common.builtBySuffix') }}
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
import MdSelect from '../components/MdSelect.vue'
import ModeToggle from '../components/ModeToggle.vue'
import TopPlayersTable from '../components/TopPlayersTable.vue'
import SongRankingTable from '../components/SongRankingTable.vue'
import ChartComponent from '../components/ChartComponent.vue'
import { shallowRef, ref, onMounted, onUnmounted, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { formatTs } from '../utils.js'
import { useI18n } from '../i18n.js'

const { t, formatCountdown } = useI18n()
const route = useRoute()
const router = useRouter()

function goMonthly() {
  router.push({ name: 'Monthly' })
}

const events = ref([])
const selectedEventId = ref(null)
const selectedHour = ref(null)
const currentEvent = ref(null)
const nowTs = ref(Date.now())   // 每秒更新，用于「活动暂未开始」倒计时
const topPlayers = ref([])
const chartSeries = shallowRef({})
const heatmapData = ref({ ref_ts: null, global_max: 0, players: {} })
const lastTopPlayersContext = ref(null)
const isInitialEventLoad = ref(true)

const SONG_RANKING_TYPES = new Set(['challenge', 'versus', 'medley'])
const rankingMode = ref('pt') // 'pt' | 'song'
const songRankingData = ref(null)
const isSongRankingLoading = ref(false)
const selectedSongId = ref(null)
let songRankingRequestId = 0

const hasSongRanking = computed(() => {
  if (!currentEvent.value) return false
  if (typeof currentEvent.value.has_song_ranking === 'boolean') {
    return currentEvent.value.has_song_ranking
  }
  return SONG_RANKING_TYPES.has(currentEvent.value.type)
})

function formatSongLabel(song) {
  if (!song) return ''
  if (song.is_medley_aggregate || song.music_id === -1) {
    return t('songTable.medleyAggregate')
  }
  return song.music_title || t('songTable.songLabel', { id: song.music_id })
}

const songList = computed(() => songRankingData.value?.songs || [])
const songOptions = computed(() =>
  songList.value.map(s => ({
    value: s.music_id,
    label: formatSongLabel(s),
  }))
)
const activeSong = computed(() => {
  if (!songList.value.length) return null
  return songList.value.find(s => s.music_id === selectedSongId.value) || songList.value[0]
})
const activeSongLabel = computed(() => formatSongLabel(activeSong.value))

const eventName = computed(() => currentEvent.value ? currentEvent.value.name : t('common.loading'))

// 该活动是否尚未开始（远端已给出新活动，但未到 start_at）
const isUpcoming = computed(() => {
  if (!currentEvent.value) return false
  return nowTs.value < currentEvent.value.start_at
})

// 距离活动开始的倒计时文本
const countdownText = computed(() => {
  if (!isUpcoming.value || !currentEvent.value) return ''
  return formatCountdown(currentEvent.value.start_at - nowTs.value)
})

const isRefreshing = ref(false)
const isChartLoading = ref(false)
const refreshInterval = ref(null)
const REFRESH_INTERVAL_SECONDS = 2 * 60; // 2 minutes
const countdown = ref(REFRESH_INTERVAL_SECONDS);

const refreshButtonText = computed(() => {
  if (isRefreshing.value) {
    return t('common.refreshing');
  }
  if (isChartLoading.value) {
    return t('common.chartLoading');
  }
  return t('common.refreshCountdown', { sec: countdown.value });
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

async function loadSongRanking(eid, force = false) {
  if (!eid) return
  const reqId = ++songRankingRequestId
  isSongRankingLoading.value = true
  try {
    const params = new URLSearchParams()
    if (force) params.append('force', 'true')
    const query = params.toString()
    const res = await api.get(`/api/events/${eid}/song_ranking${query ? `?${query}` : ''}`)
    if (reqId !== songRankingRequestId || String(selectedEventId.value) !== String(eid)) return
    songRankingData.value = res.data
    const songs = res.data?.songs || []
    if (songs.length > 0 && !songs.some(s => s.music_id === selectedSongId.value)) {
      selectedSongId.value = songs[0].music_id
    } else if (songs.length === 0) {
      selectedSongId.value = null
    }
  } catch (error) {
    if (reqId !== songRankingRequestId) return
    console.error('获取歌榜数据失败:', error)
    // Keep null so switching back to the song tab retries automatically.
    songRankingData.value = null
    selectedSongId.value = null
  } finally {
    if (reqId === songRankingRequestId) {
      isSongRankingLoading.value = false
    }
  }
}

function setRankingMode(mode) {
  if (mode === rankingMode.value) return
  rankingMode.value = mode
  if (mode === 'song' && selectedEventId.value && !songRankingData.value && !isSongRankingLoading.value) {
    loadSongRanking(selectedEventId.value)
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
    // 活动不存在（无效 ID / 已被删除）→ 跳转主题化 404 页面
    let eventRes
    try {
      eventRes = await api.get(`/api/events/${eid}?${eventParams.toString()}`)
    } catch (error) {
      if (error?.response?.status === 404) {
        router.replace({ name: 'NotFound' })
        return
      }
      throw error
    }
    currentEvent.value = eventRes.data

    if (!hasSongRanking.value) {
      rankingMode.value = 'pt'
      songRankingData.value = null
      selectedSongId.value = null
    }

    // 未开始的活动：没有榜单/热力图/曲线数据，跳过后续请求（倒计时归零时再拉）
    if (isUpcoming.value) {
      rankingMode.value = 'pt'
      songRankingData.value = null
      selectedSongId.value = null
      topPlayers.value = []
      heatmapData.value = { ref_ts: null, global_max: 0, players: {} }
      chartSeries.value = {}
      return
    }

    if (rankingMode.value === 'song' && hasSongRanking.value) {
      const shouldForceSong = force && (!isEventEnded() || !(songRankingData.value?.songs?.length))
      await loadSongRanking(eid, shouldForceSong)
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
  songRankingRequestId++;
  isSongRankingLoading.value = false;
  songRankingData.value = null;
  selectedSongId.value = null;
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

function eventTypeLabel(type) {
  const key = `event.type.${type}`
  const label = t(key)
  return label === key ? type : label
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

<style scoped>
.md-segmented {
  display: inline-flex;
  padding: 3px;
  border-radius: 9999px;
  background-color: var(--md-sys-color-surface-container-high);
  gap: 2px;
  flex-shrink: 0;
}

.md-segmented-btn {
  padding: 0.3rem 0.85rem;
  border-radius: 9999px;
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--md-sys-color-on-surface-variant);
  transition: background-color 0.15s ease, color 0.15s ease;
  white-space: nowrap;
}

.md-segmented-btn:hover {
  background-color: color-mix(in srgb, var(--md-sys-color-on-surface) 8%, transparent);
}

.md-segmented-btn.is-active {
  background-color: var(--md-sys-color-primary);
  color: var(--md-sys-color-on-primary);
  box-shadow: var(--md-elevation-1);
}
</style>
