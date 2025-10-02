<template>
  <div class="p-4 sm:p-6 max-w-4xl mx-auto">
    <div class="max-w-sm mx-auto mb-8">
      <h1 class="text-center text-3xl font-bold mb-6 text-gray-800">玩家查询</h1>
      <PlayerSearch v-model="inputUid" @search="handleSearch" />
    </div>

    <div v-if="isLoading" class="text-center py-12">
      <p class="text-lg text-gray-600">加载中...</p>
    </div>

    <div v-else-if="playerData && playerData.profile" class="bg-white shadow-xl rounded-lg overflow-hidden max-w-4xl mx-auto">
      <!-- Main Illustration Section -->
      <div v-if="leaderCardInfo" class="relative bg-gray-200">
        <img 
          :src="leaderCardInfo.illustUrl"
          alt="Player Illustration"
          class="w-full h-auto object-cover"
        />
        <div class="absolute bottom-0 left-0 w-full p-6 bg-gradient-to-t from-black/70 to-transparent">
          <h2 class="text-3xl sm:text-4xl font-bold text-white shadow-lg">{{ playerData.profile.userName || '&nbsp;' }}</h2>
          <div class="flex items-center text-gray-200 mt-2">
            <img src="https://bestdori.com/res/icon/server_jp.png" alt="JP Server" class="h-5 w-5 mr-2">
            <span class="text-lg">UID: {{ playerData.profile.publishUserIdFlg ? playerData.profile.userId : 'ID未公开' }}</span>
          </div>
          <p class="text-lg text-gray-200 mt-1">等级 {{ playerData.profile.rank }}</p>
        </div>
      </div>

      <!-- Player Details Block -->
      <div class="p-4 sm:p-6 space-y-6">
        
        <!-- Introduction -->
        <div class="text-center p-4 border-b">
          <p class="text-lg text-gray-700 italic">"{{ playerData.profile.introduction || '' }}"</p>
        </div>

        <!-- Degrees -->
        <div v-if="playerData.profile.userProfileDegreeMap && playerData.profile.userProfileDegreeMap.entries">
          <h3 class="text-xl font-semibold text-gray-800 mb-4 text-center">称号</h3>
          <div class="flex flex-wrap justify-center gap-2">
            <div v-for="degree in playerData.profile.userProfileDegreeMap.entries" :key="degree.degreeId">
              <img :src="`
https://bestdori.com/assets/jp/thumb/degree_rip/degree${degree.degreeId}.png`" :alt="`Degree ${degree.degreeId}`" class="h-12"/>
            </div>
          </div>
        </div>

        <!-- Main Deck -->
        <div v-if="playerData.profile.mainDeckUserSituations && playerData.profile.mainDeckUserSituations.entries">
          <h3 class="text-xl font-semibold text-gray-800 mb-4 text-center">主乐队</h3>
          <div class="flex flex-wrap justify-center gap-2">
            <div v-for="card in playerData.profile.mainDeckUserSituations.entries" :key="card.situationId">
              <img :src="`https://bestdori.com/res/card/icon/${card.situationId}.png`" :alt="`Card ${card.situationId}`" class="h-16 w-16 rounded-full border-2 border-gray-300"/>
            </div>
          </div>
        </div>

        <!-- Band Ranks -->
        <div v-if="playerData.profile.bandRankMap && playerData.profile.bandRankMap.entries">
          <h3 class="text-xl font-semibold text-gray-800 my-4 text-center">乐队等级</h3>
          <div class="flex flex-wrap justify-center gap-4">
            <div v-for="(rank, bandId) in playerData.profile.bandRankMap.entries" :key="bandId" class="flex flex-col items-center">
              <img :src="`https://bestdori.com/res/icon/band_${bandId}.svg`" :alt="`Band ${bandId}`" class="h-12 w-12 mb-1">
              <span class="font-semibold">Rank {{ rank }}</span>
            </div>
          </div>
        </div>

        <!-- Character Ranks -->
        <div v-if="playerData.profile.userCharacterRankMap && playerData.profile.userCharacterRankMap.entries">
          <h3 class="text-xl font-semibold text-gray-800 my-4 text-center">角色等级</h3>
          <div class="grid grid-cols-5 sm:grid-cols-7 md:grid-cols-10 gap-4 text-center">
            <div v-for="(char, charId) in playerData.profile.userCharacterRankMap.entries" :key="charId" class="flex flex-col items-center">
              <img :src="`https://bestdori.com/res/icon/chara_icon_${charId}.png`" :alt="`Character ${charId}`" class="h-12 w-12 rounded-full mb-1 border-2 border-gray-200">
              <span class="font-semibold">{{ char.rank }}</span>
            </div>
          </div>
        </div>

        <!-- T10 Records -->
        <div class="pt-4 border-t">
          <div v-if="playerData.t10_events && playerData.t10_events.length > 0">
            <h3 class="text-xl font-semibold text-gray-800 mb-4 text-center">T10 记录</h3>
            <ul class="space-y-3 max-w-md mx-auto">
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
          <div v-else class="text-center py-8">
            <p class="text-gray-500">该玩家暂无 T10 记录。</p>
          </div>
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
import { ref, watch, computed } from 'vue';
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

const leaderCardInfo = computed(() => {
  if (!playerData.value || !playerData.value.profile) return null;

  const profile = playerData.value.profile;
  const leaderId = profile.mainUserDeck?.leader;
  if (!leaderId) return null;

  const leaderCard = profile.mainDeckUserSituations?.entries.find(s => s.situationId === leaderId);
  if (!leaderCard) return null;

  const isTrained = leaderCard.trainingStatus === 'done';
  return {
    illustUrl: `https://bestdori.com/res/card/${leaderCard.situationId}_rip/card_trim${isTrained ? '_after_training' : ''}.png`,
  };
});

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
