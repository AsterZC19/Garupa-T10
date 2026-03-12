<template>
  <!-- 页面容器：最小高度撑满屏幕，flex 布局 -->
  <div class="min-h-screen flex flex-col bg-gray-50">

    <!-- 主体内容 -->
    <main class="flex-1 p-4 sm:p-6 max-w-10xl mx-auto w-full">

      <!-- 搜索框 -->
      <div class="max-w-sm mx-auto mb-8">
        <h1 class="text-center text-3xl font-bold mb-6 text-gray-800">玩家查询</h1>
        <PlayerSearch v-model="inputUid" @search="handleSearch" />
      </div>

      <!-- 加载状态 -->
      <div v-if="isLoading" class="text-center py-12">
        <p class="text-lg text-gray-600">加载中...</p>
      </div>

      <!-- 查到玩家 -->
      <div
        v-else-if="playerData && playerData.profile"
        class="bg-white shadow-xl rounded-lg overflow-hidden w-full md:max-w-[70vw] mx-auto"
      >
        <div class="lg:flex">

          <!-- 左列：头像、基础信息、称号、自我介绍 -->
          <div class="lg:w-1/2 p-4 sm:p-6 space-y-4">

            <!-- 头像 -->
            <div v-if="leaderCardIllustUrl" class="relative">
              <img
                :src="leaderCardIllustUrl"
                alt="Player Illustration"
                class="w-full h-auto object-cover rounded-lg shadow-sm"
              />
            </div>

            <!-- 基本资料 -->
            <div class="text-center">
              <h2 class="text-3xl sm:text-4xl font-bold text-gray-800">
                {{ playerData.profile.userName || '&nbsp;' }}
              </h2>
              <div class="flex items-center justify-center text-gray-500 mt-1 text-sm font-medium">
                <span>UID: {{ playerData.profile.publishUserIdFlg ? playerData.profile.userId : 'ID未公开' }}</span>
                <span class="mx-2 opacity-30">|</span>
                <span>等级 {{ playerData.profile.rank }}</span>
              </div>
            </div>

            <!-- 称号 -->
            <div
              v-if="playerData.profile.userProfileDegreeMap && playerData.profile.userProfileDegreeMap.entries && allDegreesData"
              class="pb-1 overflow-hidden w-full"
            >
              <div class="flex flex-nowrap justify-center items-center space-x-1 sm:space-x-2 scale-[0.55] sm:scale-75 origin-center w-full">
                <div
                  v-for="degree in playerData.profile.userProfileDegreeMap.entries"
                  :key="degree.degreeId"
                  class="flex-shrink-0"
                >
                  <div class="h-8 flex items-center">
                    <DegreeDisplay :degreeId="degree.degreeId" :allDegreesData="allDegreesData" />
                  </div>
                </div>
              </div>
            </div>

            <!-- 自使介绍 -->
            <div class="text-center px-4 py-2 bg-gray-50 rounded-lg italic border border-gray-100">
              <p class="text-sm text-gray-600">
                "{{ playerData.profile.introduction || '' }}"
              </p>
            </div>
          </div>

          <!-- 右列：T10 记录、主乐队、综合力、乐队等级、角色等级 -->
          <div class="lg:w-1/2 p-4 sm:p-6 space-y-6 border-t lg:border-t-0 lg:border-l">

            <!-- T10 记录 -->
            <div class="pt-2 border-b pb-6">
              <h3 class="text-lg font-bold text-gray-800 mb-4 text-center">T10 记录</h3>
              <div v-if="earnedDegrees && earnedDegrees.length > 0" class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                <div
                  v-for="degree in earnedDegrees"
                  :key="degree.event_id"
                  class="p-2 bg-gray-50 hover:bg-indigo-50 rounded-lg transition-all duration-200 flex flex-col items-center border border-gray-100 hover:border-indigo-200"
                >
                  <router-link :to="'/' + degree.event_id" class="text-center mb-1">
                    <p class="font-bold text-indigo-600 text-[10px]">
                      EVENT #{{ degree.event_id }}
                    </p>
                    <p class="text-[11px] text-gray-600 font-medium">
                      RANK <span class="text-indigo-700 font-black">{{ degree.rank }}</span>
                    </p>
                  </router-link>
                  <div class="transform scale-[0.65] h-8 flex items-center">
                    <DegreeDisplay :rank="degree.rank" :event_id="degree.event_id" />
                  </div>
                </div>
              </div>
              <div v-else class="text-center py-8">
                <p class="text-gray-400 text-sm">该玩家暂无 T10 记录。</p>
              </div>
            </div>

            <!-- 主乐队 -->
            <div v-if="sortedCards" class="pb-4 overflow-hidden w-full">
              <h3 class="text-lg font-bold text-gray-800 mb-4 text-center">主乐队</h3>
              <div class="flex flex-nowrap justify-center items-center gap-1 sm:gap-2 scale-[0.85] sm:scale-100 origin-center w-full">
                <div
                  v-for="card in sortedCards"
                  :key="card.situationId"
                  class="flex-shrink-0"
                >
                  <CardIcon 
                    :cardId="card.situationId" 
                    :isTrained="card.trainingStatus"
                    :rarity="card.rarity"
                    :attribute="card.attribute"
                    :bandId="card.bandId"
                    :resourceSetName="card.resourceSetName"
                    :ripId="card.rip_id"
                    :skillLevel="card.skillLevel"
                    :limitBreakRank="card.limitBreakRank"
                    :size="65"
                  />
                </div>
              </div>
            </div>

            <!-- 综合力 (Ultra Compact) - Moved below Main Band -->
            <div v-if="playerData.bp" class="flex flex-col items-center gap-1 py-2 px-4 bg-indigo-50/50 rounded-xl border border-indigo-100 mx-auto w-fit min-w-[240px] mb-6 shadow-sm">
              <div class="flex items-center justify-between w-full border-b border-indigo-200 pb-1 mb-1">
                <span class="text-[10px] font-black text-indigo-400 uppercase tracking-widest">Team Power</span>
                <span class="text-sm font-black text-indigo-600">{{ playerData.bp.total.toLocaleString() }}</span>
              </div>
              <div class="flex gap-4 w-full justify-between">
                <div class="flex items-center gap-1.5 flex-1">
                  <div class="w-1 h-3 bg-pink-400 rounded-full"></div>
                  <span class="text-[9px] font-bold text-gray-500">{{ Math.round(playerData.bp.performance/1000) }}k</span>
                </div>
                <div class="flex items-center gap-1.5 flex-1">
                  <div class="w-1 h-3 bg-blue-400 rounded-full"></div>
                  <span class="text-[9px] font-bold text-gray-500">{{ Math.round(playerData.bp.technique/1000) }}k</span>
                </div>
                <div class="flex items-center gap-1.5 flex-1">
                  <div class="w-1 h-3 bg-orange-400 rounded-full"></div>
                  <span class="text-[9px] font-bold text-gray-500">{{ Math.round(playerData.bp.visual/1000) }}k</span>
                </div>
              </div>
            </div>

            <div class="border-b w-full"></div>

            <!-- 乐队等级 -->
            <div v-if="playerData.profile.bandRankMap && playerData.profile.bandRankMap.entries" class="pb-6 border-b">
              <h3 class="text-lg font-bold text-gray-800 mb-4 text-center">乐队等级</h3>
              <div class="flex flex-wrap justify-center gap-x-5 gap-y-3">
                <div
                  v-for="(rank, bandId) in playerData.profile.bandRankMap.entries"
                  :key="bandId"
                  class="flex flex-col items-center"
                >
                  <img
                    :src="`https://bestdori.com/res/icon/band_${bandId}.svg`"
                    :alt="`Band ${bandId}`"
                    class="h-8 w-8 mb-1"
                  />
                  <span class="text-xs font-black text-gray-700">{{ rank }}</span>
                </div>
              </div>
            </div>

            <!-- 角色等级 -->
            <div
              v-if="playerData.profile.userCharacterRankMap && playerData.profile.userCharacterRankMap.entries"
            >
              <h3 class="text-lg font-bold text-gray-800 mb-4 text-center">角色等级</h3>
              <div class="grid grid-cols-5 sm:grid-cols-7 md:grid-cols-10 gap-2 text-center">
                <div
                  v-for="(char, charId) in playerData.profile.userCharacterRankMap.entries"
                  :key="charId"
                  class="flex flex-col items-center"
                >
                  <div class="h-7 w-7 rounded-full overflow-hidden border border-gray-200 mb-1 shadow-sm flex-shrink-0">
                    <img
                      :src="`https://bestdori.com/res/icon/chara_icon_${charId}.png`"
                      :alt="`Character ${charId}`"
                      class="w-full h-full object-cover"
                    />
                  </div>
                  <span class="text-[9px] font-black text-gray-500 leading-none">{{ char.rank }}</span>
                </div>
              </div>
            </div>

          </div>
        </div>
      </div>

      <!-- 未找到玩家 -->
      <div v-else-if="searchedUid && !isLoading" class="text-center py-12">
        <p class="text-2xl font-bold text-red-500">未能找到玩家</p>
        <p class="text-gray-600 mt-2">UID: {{ searchedUid }}</p>
      </div>

      <!-- 初始提示 -->
      <div v-else class="text-center py-12">
        <p class="text-gray-500">请输入玩家 UID 以查询玩家信息和 T10 记录。</p>
      </div>
    </main>

    <!-- 页脚 -->
    <footer class="mt-10 text-center text-xs text-gray-400 py-4 border-t">
      由 <span class="text-cyan-400">🎵</span>构建 /
      <a
        href="https://github.com/AsterZC19/Garupa-T10"
        target="_blank"
        rel="noopener"
        class="underline hover:text-blue-500"
      >GitHub</a>
    </footer>
  </div>
</template>

<script setup>
import { ref, watch, computed, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import api from '../api';
import PlayerSearch from '../components/PlayerSearch.vue';
import DegreeDisplay from '../components/DegreeDisplay.vue';
import CardIcon from '../components/CardIcon.vue';

const allDegreesData = ref(null);

onMounted(async () => {
  try {
    const response = await fetch('/api/degrees/all.3.json');
    allDegreesData.value = await response.json();
  } catch (error) {
    console.error('Failed to fetch degrees data:', error);
  }
});

const route = useRoute();
const router = useRouter();

const inputUid = ref(''); 
const searchedUid = ref(''); 
const playerData = ref(null);
const isLoading = ref(false);
const earnedDegrees = ref([]);
const leaderCardIllustUrl = ref(null);

watch(playerData, async (newPlayerData) => {
  if (!newPlayerData || !newPlayerData.profile) {
    leaderCardIllustUrl.value = null;
    return;
  }
  
  const profile = newPlayerData.profile;
  let cardId = null;
  let isTrained = false;

  if (profile.userProfileSituation) {
    cardId = profile.userProfileSituation.situationId;
    isTrained = profile.userProfileSituation.illust === 'after_training';
  } else if (profile.userIllust) {
    cardId = profile.userIllust.cardId;
    isTrained = !!profile.userIllust.trainingStatus;
  } else {
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
        leaderCardIllustUrl.value = `https://bestdori.com/assets/jp/characters/resourceset/${cardDetails.resourceSetName}_rip/trim${trainingString}.png`;
      } else {
        const trainingString = isTrained ? '_after_training' : '_normal';
        leaderCardIllustUrl.value = `https://bestdori.com/res/card/${cardId}_rip/trim${trainingString}.png`;
      }
    } catch (error) {
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
  earnedDegrees.value = [];
  searchedUid.value = playerUid;
  try {
    const res = await api.get(`/api/player/${playerUid}`);
    playerData.value = res.data;
    const degreesRes = await api.get(`/api/degrees/player/${playerUid}/all_degrees`);
    earnedDegrees.value = degreesRes.data;
  } catch (error) {
    console.error('获取玩家数据失败:', error);
    playerData.value = null;
  } finally {
    isLoading.value = false;
  }
};

const sortedCards = computed(() => {
  if (!playerData.value || !playerData.value.enriched_cards) return null;
  const cards = playerData.value.enriched_cards;
  if (cards.length !== 5) return cards;
  return [cards[3], cards[1], cards[0], cards[2], cards[4]];
});

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
