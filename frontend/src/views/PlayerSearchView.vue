<template>
  <div class="p-4 sm:p-6 max-w-4xl mx-auto">
    <div class="max-w-sm mx-auto mb-8">
      <h1 class="text-center text-3xl font-bold mb-6 text-gray-800">玩家查询</h1>
      <PlayerSearch v-model="inputUid" @search="handleSearch" />
    </div>

    <div v-if="isLoading" class="text-center py-12">
      <p class="text-lg text-gray-600">加载中...</p>
    </div>

    <div v-else-if="playerData" class="bg-white shadow-xl rounded-lg overflow-hidden">
      <div class="bg-gray-800 text-white p-4 sm:p-6">
        <h2 class="text-2xl sm:text-3xl font-bold">{{ playerData.name || 'N/A' }}</h2>
        <p class="text-sm text-gray-300 mt-1">UID: {{ playerData.uid }}</p>
      </div>
      
      <div class="p-4 sm:p-6 space-y-6">
        <div>
          <h3 class="text-lg font-semibold text-gray-700 mb-2">基本信息</h3>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
            <div class="flex items-center">
              <span class="font-semibold text-gray-500 w-24">最后更新:</span>
              <span class="text-gray-800">{{ formatTime(playerData.last_updated) }}</span>
            </div>
            <div class="flex items-center">
              <span class="font-semibold text-gray-500 w-24">玩家等级:</span>
              <span class="text-gray-800">{{ playerData.profile?.user?.rank ?? 'N/A' }}</span>
            </div>
          </div>
        </div>

        <div v-if="playerData.profile?.bandRankMap?.entries">
          <h3 class="text-lg font-semibold text-gray-700 mb-3 pt-4 border-t">乐团等级</h3>
          <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4 text-center">
            <div v-for="(rank, bandId) in playerData.profile.bandRankMap.entries" :key="bandId" class="p-2 bg-gray-50 rounded-lg">
              <p class="font-semibold text-sm">Band {{ bandId }}</p>
              <p class="text-lg font-bold text-blue-600">Lv. {{ rank }}</p>
            </div>
          </div>
        </div>

        <div v-if="playerData.t10_events && playerData.t10_events.length > 0">
          <h3 class="text-lg font-semibold text-gray-700 mb-3 pt-4 border-t">T10 记录</h3>
          <ul class="space-y-3">
            <li v-for="event in playerData.t10_events" :key="event.event_id" class="p-3 bg-gray-50 hover:bg-gray-100 rounded-md transition-colors duration-200">
              <router-link :to="'/' + event.event_id" class="flex justify-between items-center group">
                <div>
                  <p class="font-semibold text-indigo-600 group-hover:underline">活动 #{{ event.event_id }}</p>
                  <p class="text-sm text-gray-600">排名: <span class="font-medium">{{ event.rank }}</span></p>
                </div>
                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-gray-400 group-hover:text-indigo-600 transition-transform duration-200 transform group-hover:translate-x-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                </svg>
              </router-link>
            </li>
          </ul>
        </div>
        <div v-else class="text-center py-8 border-t">
           <p class="text-gray-500">该玩家暂无 T10 记录。</p>
        </div>
      </div>
    </div>
    
    <div v-else-if="searchedUid && !isLoading" class="text-center py-12">
      <p class="text-2xl font-bold text-red-500">未能找到玩家</p>
      <p class="text-gray-600 mt-2">UID: {{ searchedUid }}</p>
    </div>
     <div v-else class="text-center py-12">
      <p class="text-gray-500">请输入玩家 UID 以查询玩家信息和 T10 记录。</p>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import api from '../api';
import PlayerSearch from '../components/PlayerSearch.vue';

const route = useRoute();
const router = useRouter();

// Ref for the input box, used with v-model
const inputUid = ref(''); 

// Ref for the UID that has been searched
const searchedUid = ref(''); 

const playerData = ref(null);
const isLoading = ref(false);

const handleSearch = () => {
  if (inputUid.value) {
    router.push({ path: `/player/${inputUid.value}` });
  }
};

const fetchPlayerData = async (playerUid) => {
  if (!playerUid) return;
  isLoading.value = true;
  playerData.value = null;
  searchedUid.value = playerUid;
  try {
    const res = await api.get(`/api/player/${playerUid}`);
    playerData.value = res.data;
  } catch (error) {
    console.error('获取玩家数据失败:', error);
    playerData.value = null;
  } finally {
    isLoading.value = false;
  }
};

const formatTime = (timestamp) => {
  if (!timestamp) return 'N/A';
  return new Date(timestamp * 1000).toLocaleString('zh-CN', { hour12: false });
}

watch(() => route.params.uid, (newUid) => {
  if (newUid) {
    inputUid.value = newUid;
    fetchPlayerData(newUid);
  } else {
    inputUid.value = '';
    searchedUid.value = '';
    playerData.value = null;
  }
}, { immediate: true });
</script>
