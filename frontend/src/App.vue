<template>
  <div class="p-6 max-w-6xl mx-auto">
    <header class="flex items-center justify-between mb-4 gap-4">
      <div class="flex items-center gap-2">
        <EventSelector :events="events" v-model="selectedEventId" />
      </div>
      <button @click="forceRefresh" :disabled="isRefreshing" class="px-3 py-1 border rounded bg-gray-100 hover:bg-gray-200 disabled:bg-gray-300 disabled:cursor-not-allowed">
        {{ isRefreshing ? '刷新中...' : '刷新' }}
      </button>
    </header>

    <!-- Event Name and Banner Section -->
    <section v-if="currentEvent" class="flex flex-col-reverse md:flex-row items-center md:items-stretch justify-between mb-6 gap-6" :class="{ 'opacity-50': isRefreshing }">
      <!-- Event Name and Details (now first for large screen row layout) -->
      <div class="flex-grow flex flex-col h-full text-center">
        <div class="flex flex-col justify-center flex-1">
          <h1 class="text-2xl font-bold mb-2 event-title bg-clip-text text-transparent bg-gradient-to-r from-sky-400 to-pink-400 hover:scale-105 transition-transform">{{ eventName }}</h1>
          <div class="flex gap-4 text-sm text-gray-700 justify-center mb-2">
            <div>类型: {{ eventTypeZh(currentEvent.type) }}</div>
            <div>开始: {{ formatTs(currentEvent.start_at) }}</div>
            <div>结束: {{ formatTs(currentEvent.end_at) }}</div>
          </div>
          <p v-if="!isCurrent" class="text-yellow-600 mt-2">当前未有进行中的活动（显示最近活动）</p>
        </div>
        <div class="text-center text-xs text-gray-400 mb-2 mt-4">
          感谢
          <a href="https://bestdori.com" target="_blank" rel="noopener" class="underline hover:text-blue-500">Bestdori</a>
          提供数据
        </div>
      </div>
      <!-- Banner Image (now second for large screen row layout, but appears first on mobile due to flex-col-reverse) -->
      <div v-if="currentEvent.banner_url" class="flex-shrink-0 flex items-center mb-4 md:mb-0">
        <img :src="currentEvent.banner_url" alt="Event Banner" class="max-w-full h-auto" />
      </div>
    </section>

    <main class="space-y-6 transition-opacity" :class="{ 'opacity-50 pointer-events-none': isRefreshing }">
      <div>
        <h3 class="font-semibold mb-2 text-center">档位时速 (Top 10)</h3>
        <TopPlayersTable :players="topPlayers" />
      </div>
      <div>
        <h3 class="font-semibold mb-2 text-center">时速曲线</h3>
        <ChartComponent :series="series" :current-event="currentEvent" />
      </div>
    </main>
  </div>
</template>

<script setup>
import api from './api'
import EventSelector from './components/EventSelector.vue'
import HourSelector from './components/HourSelector.vue'
import TopPlayersTable from './components/TopPlayersTable.vue'
import ChartComponent from './components/ChartComponent.vue'
import { ref, onMounted, watch, computed } from 'vue'
import { formatTs } from './utils.js'

const events = ref([])
const selectedEventId = ref(null)
const selectedHour = ref(null)
const currentEvent = ref(null)
const isCurrent = ref(true)
const scores = ref([])
const topPlayers = ref([])
const series = ref({})

const eventName = computed(() => currentEvent.value ? currentEvent.value.name : '加载中...')

const isEventActive = computed(() => {
  if (!currentEvent.value) return false
  const now = Date.now()
  return now >= currentEvent.value.start_at && now <= currentEvent.value.end_at
})

const hours = computed(() => {
  if (!currentEvent.value) return []

  const hourOptions = []
  let current = new Date(currentEvent.value.start_at)
  const end = new Date(currentEvent.value.end_at)

  current.setMinutes(0, 0, 0)

  while (current < end) {
    const hourStart = new Date(current)
    const hourEnd = new Date(current.getTime() + 3600 * 1000)
    hourOptions.push({
      value: hourStart.getTime(),
      label: `${hourStart.getHours()}:00 - ${hourEnd.getHours()}:00`
    })
    current.setHours(current.getHours() + 1)
  }

  return hourOptions
})

const isRefreshing = ref(false)

async function loadEventData(eid, hour, force = false) {
  if (!eid) return
  
  try {
    const eventParams = new URLSearchParams();
    if (force) {
      eventParams.append('force', 'true');
    }
    const eventRes = await api.get(`/api/events/${eid}?${eventParams.toString()}`)
    currentEvent.value = eventRes.data
  } catch (error) {
    console.error('获取活动详情失败:', error)
    currentEvent.value = { event_id: eid, name: `活动 ${eid}`, start_at: 0, end_at: 0 }
  }

  try {
    const params = new URLSearchParams()
    if (hour !== null) {
      params.append('hour', hour)
    }

    const [scoresRes, seriesRes, topPlayersRes] = await Promise.all([
      api.get(`/api/events/${eid}/scores?limit=50&${params.toString()}`),
      api.get(`/api/events/${eid}/chart?${params.toString()}`),
      api.get(`/api/events/${eid}/top_players?limit=10&${params.toString()}`) 
    ])
    
    scores.value = scoresRes.data
    topPlayers.value = topPlayersRes.data
    const newSeries = seriesRes.data || {}
    
    for (const uid in newSeries) {
      const found = scores.value.find(s => s.uid === uid)
      if (found) newSeries[uid].name = found.name
    }
    series.value = newSeries
  } catch (error) {
    console.error('获取活动数据失败:', error)
    scores.value = []
    series.value = {}
    topPlayers.value = []
  }
}

async function forceRefresh() {
  if (selectedEventId.value && !isRefreshing.value) {
    isRefreshing.value = true;
    try {
      await loadEventData(selectedEventId.value, selectedHour.value, true);
    } finally {
      isRefreshing.value = false;
    }
  }
}

async function loadInitialSetup() {
  try {
    const res = await api.get('/api/events/')
    events.value = res.data
    
    let eventIdToLoad = null
    try {
      const cur = await api.get('/api/events/current')
      if (cur.status === 200 && cur.data.event) {
        currentEvent.value = cur.data.event
        isCurrent.value = cur.data.is_current
        eventIdToLoad = currentEvent.value.event_id
      } else {
        throw new Error('没有当前活动')
      }
    } catch (error) {
      if (events.value.length > 0) {
        eventIdToLoad = events.value[0].event_id
      }
    }

    if (eventIdToLoad) {
      selectedEventId.value = eventIdToLoad
    }
  } catch (error) {
    console.error('获取活动列表失败:', error)
  }
}

watch(selectedEventId, (newId) => {
  if (newId) {
    selectedHour.value = null
    loadEventData(newId, selectedHour.value)
  }
})

watch(selectedHour, (newHour) => {
  if (selectedEventId.value) {
    loadEventData(selectedEventId.value, newHour)
  }
})

onMounted(() => {
  loadInitialSetup()
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
  text-shadow: 0 0 1px rgba(0,0,0,0.1);
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