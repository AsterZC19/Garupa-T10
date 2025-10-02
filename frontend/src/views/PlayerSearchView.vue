<template>
  <div class="p-4 sm:p-6 max-w-10xl mx-auto">
    <div class="max-w-sm mx-auto mb-8">
      <h1 class="text-center text-3xl font-bold mb-6 text-gray-800">玩家查询</h1>
      <PlayerSearch v-model="inputUid" @search="handleSearch" />
    </div>

    <div v-if="isLoading" class="text-center py-12">
      <p class="text-lg text-gray-600">加载中...</p>
    </div>

    <div v-else-if="playerData && playerData.profile" class="bg-white shadow-xl rounded-lg overflow-hidden w-full md:max-w-[70vw] mx-auto">
      <div class="md:flex">
        <!-- Left Column: Illustration, Player Info, Degrees, Introduction -->
        <div class="md:w-1/2 p-4 sm:p-6 space-y-6">
          <!-- Main Illustration Section -->
          <div v-if="leaderCardIllustUrl" class="relative">
            <img 
              :src="leaderCardIllustUrl"
              alt="Player Illustration"
              class="w-full h-auto object-cover"
            />
          </div>

          <!-- Player Info -->
          <div class="text-center pb-6">
            <h2 class="text-3xl sm:text-4xl font-bold text-gray-800">{{ playerData.profile.userName || '&nbsp;' }}</h2>
            <div class="flex items-center justify-center text-gray-600 mt-2">
              <span class="text-lg">UID: {{ playerData.profile.publishUserIdFlg ? playerData.profile.userId : 'ID未公开' }}</span>
            </div>
            <p class="text-lg text-gray-600 mt-1">等级 {{ playerData.profile.rank }}</p>
          </div>
          
          <!-- Degrees -->
          <div v-if="playerData.profile.userProfileDegreeMap && playerData.profile.userProfileDegreeMap.entries && allDegreesData" class="pb-4">
                      <div v-if="playerData.profile.userProfileDegreeMap.entries.length === 1" class="flex justify-center">
                        <div v-for="degree in playerData.profile.userProfileDegreeMap.entries" :key="degree.degreeId">
                          <DegreeDisplay :degreeId="degree.degreeId" :allDegreesData="allDegreesData" />
                        </div>
                      </div>
                      <div v-else class="flex flex-wrap justify-center gap-2">
                        <div v-for="degree in playerData.profile.userProfileDegreeMap.entries" :key="degree.degreeId">
                          <DegreeDisplay :degreeId="degree.degreeId" :allDegreesData="allDegreesData" />
                        </div>
                      </div>          </div>

          <!-- Introduction -->
          <div class="text-center p-4">
            <p class="text-lg text-gray-700 italic">"{{ playerData.profile.introduction || '' }}"</p>
          </div>
        </div>

        <!-- Right Column: Main Deck, Band Ranks, Character Ranks, T10 Records -->
        <div class="md:w-1/2 p-4 sm:p-6 space-y-6 border-t md:border-t-0 md:border-l">
          <!-- Main Deck -->
           <!-- T10 Records -->
          <div class="pt-4 border-b">
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
              <p class="text-gray-500">该玩家暂无 T10 记录。（暂未实现）</p>
            </div>
          </div>
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
                <div class="h-12 w-12 rounded-full overflow-hidden border-2 border-gray-200 mb-1">
                  <img
                    :src="`https://bestdori.com/res/icon/chara_icon_${charId}.png`"
                    :alt="`Character ${charId}`"
                    class="w-full h-full object-cover"
                  />
                </div>
                <span class="font-semibold">{{ char.rank }}</span>
              </div>
            </div>
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
import { ref, watch, computed, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import api from '../api';
import PlayerSearch from '../components/PlayerSearch.vue';
import DegreeDisplay from '../components/DegreeDisplay.vue';

const allDegreesData = ref(null);

onMounted(async () => {
  try {
    const response = await fetch('/api/degrees/all.3.json'); // Changed URL
    allDegreesData.value = await response.json();
    console.log('Fetched allDegreesData:', allDegreesData.value);
  } catch (error) {
    console.error('Failed to fetch degrees data:', error);
  }
});

const route = useRoute();
const router = useRouter();

// Ref for the input box, used with v-model
const inputUid = ref(''); 

// Ref for the UID that has been searched
const searchedUid = ref(''); 

const playerData = ref(null);
const isLoading = ref(false);

const leaderCardIllustUrl = ref(null);

watch(playerData, async (newPlayerData) => {
  if (!newPlayerData || !newPlayerData.profile) {
    leaderCardIllustUrl.value = null;
    return;
  }
  
  const profile = newPlayerData.profile;
  let cardId = null;
  let isTrained = false;

  // Priority 1: Use userProfileSituation if it exists
  if (profile.userProfileSituation) {
    cardId = profile.userProfileSituation.situationId;
    isTrained = profile.userProfileSituation.illust === 'after_training';
  } else if (profile.userIllust) { // Priority 2: Use userIllust if it exists
    cardId = profile.userIllust.cardId;
    isTrained = !!profile.userIllust.trainingStatus;
  } else { // Fallback: Use the leader of the main deck
    const leaderId = profile.mainUserDeck?.leader;
    if (leaderId) {
      const leaderCard = profile.mainDeckUserSituations?.entries.find(s => s.situationId === leaderId);
      if (leaderCard) {
        cardId = leaderCard.situationId;
        isTrained = leaderCard.trainingStatus === 'done';
      }
    }
  }

  if (cardId) {
    try {
      const res = await api.get(`/api/cards/${cardId}`);
      const cardDetails = res.data;
      if (cardDetails && cardDetails.resourceSetName) {
        const trainingString = isTrained ? '_after_training' : '_normal';
        // Correct URL structure based on previous context
        // https://bestdori.com/assets/jp/characters/resourceset/res004075_rip/trim_after_training.png
        leaderCardIllustUrl.value = `https://bestdori.com/assets/jp/characters/resourceset/${cardDetails.resourceSetName}_rip/trim${trainingString}.png`;
      } else {
        // Fallback to old URL structure if API fails or resourceSetName is missing
        const trainingString = isTrained ? '_after_training' : '_normal';
        leaderCardIllustUrl.value = `https://bestdori.com/res/card/${cardId}_rip/trim${trainingString}.png`;
      }
    } catch (error) {
      console.error('Failed to get card details for illustration:', error);
      // Fallback to old URL structure on error
      const trainingString = isTrained ? '_after_training' : '_normal';
      leaderCardIllustUrl.value = `https://bestdori.com/res/card/${cardId}_rip/trim${trainingString}.png`;
    }
  } else {
    leaderCardIllustUrl.value = null;
  }
}, { immediate: true });

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
