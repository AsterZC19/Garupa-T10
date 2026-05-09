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
        class="bg-white shadow-xl rounded-lg overflow-hidden w-full lg:max-w-[70vw] mx-auto"
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
              class="pb-2 w-full overflow-visible"
            >
              <div class="flex flex-wrap justify-center items-center gap-2 sm:gap-3 w-full">
                <DegreeDisplay
                  v-for="degree in playerData.profile.userProfileDegreeMap.entries"
                  :key="degree.degreeId"
                  :degreeId="degree.degreeId"
                  :allDegreesData="allDegreesData"
                  displayWidth="clamp(126px, 18vw, 173px)"
                />
              </div>
            </div>

            <!-- 签名 -->
            <div class="text-center px-4 py-2 bg-gray-50 rounded-lg italic border border-gray-100">
              <p class="text-sm text-gray-600">
                {{ playerData.profile.introduction || '' }}
              </p>
            </div>
          </div>

          <!-- 右列：T10 记录、主乐队、综合力、乐队等级、角色等级 -->
          <div class="lg:w-1/2 p-4 sm:p-6 space-y-6 border-t lg:border-t-0 lg:border-l">

            <!-- T10 记录 -->
            <div class="pt-2 border-b pb-6">
              <h3 class="text-lg font-bold text-gray-800 mb-4 text-center">T10 记录</h3>

              <div
                v-if="earnedDegrees && earnedDegrees.length > 0"
                class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-3 gap-2"
              >
                <div
                  v-for="degree in earnedDegrees"
                  :key="degree.event_id"
                  class="p-2 bg-gray-50 hover:bg-indigo-50 rounded-lg transition-all duration-200 flex flex-col items-center border border-gray-100 hover:border-indigo-200"
                >
                  <!-- 活动信息 -->
                  <router-link :to="'/' + degree.event_id" class="text-center mb-1">
                    <p class="font-bold text-indigo-600 text-[10px]">
                      活动 #{{ degree.event_id }}
                    </p>
                    <p class="text-[11px] text-gray-600 font-medium">
                      <span class="text-indigo-700 font-black">{{ degree.rank }}</span> 位
                    </p>
                  </router-link>

                  <!-- 称号 -->
                  <div class="w-full min-h-6 flex justify-center items-center overflow-visible">
                    <DegreeDisplay
                      :rank="degree.rank"
                      :event_id="degree.event_id"
                      :displayWidth="104"
                    />
                  </div>
                </div>
              </div>

              <!-- 无记录 -->
              <div v-else class="text-center py-8">
                <p class="text-gray-400 text-sm">该玩家暂无 T10 记录。</p>
              </div>
            </div>

            <!-- 主乐队 (Responsive Scaling) -->
            <div v-if="sortedCards" class="pb-2 overflow-hidden w-full">
              <h3 class="text-lg font-bold text-gray-800 mb-4 text-center">主乐队</h3>
              <div class="flex flex-nowrap justify-center items-center 
                          gap-0.5 sm:gap-1 md:gap-2
                          scale-[0.7] xs:scale-[0.8] sm:scale-[0.9] md:scale-100 
                          transition-transform duration-300 origin-center w-full">
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

            <!-- 综合力 -->
            <div v-if="playerData.bp" class="mt-2 pb-2 overflow-hidden w-full">

              <h3 class="text-base font-bold text-gray-700 mb-2 text-center">
                综合力
              </h3>

              <!-- 内容区（和主乐队同结构，但稍微窄一点） -->
              <div class="flex flex-nowrap justify-center items-center scale-[0.8] sm:scale-[0.95] origin-center w-full">

                <div class="w-full max-w-[420px]">

                  <!-- 总数 -->
                  <div class="flex justify-between items-end mb-2">
                    <span class="text-[10px] font-bold text-indigo-300 uppercase tracking-widest">
                      TOTAL
                    </span>
                    <span class="text-xl font-black text-indigo-600 tabular-nums">
                      {{ playerData.bp.total.toLocaleString() }}
                    </span>
                  </div>

                  <!-- 三属性 -->
                  <div class="grid grid-cols-3 gap-3">

                    <!-- Performance -->
                    <div>
                      <div class="flex justify-between text-[10px] font-bold mb-1">
                        <span class="text-pink-400">PERF</span>
                        <span class="text-gray-600 tabular-nums">
                          {{ Math.round(playerData.bp.performance).toLocaleString() }}
                        </span>
                      </div>

                      <div class="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          class="h-full bg-pink-400 transition-all duration-1000"
                          :style="{ width: (playerData.bp.performance / (playerData.bp.total * 0.45) * 100) + '%' }"
                        ></div>
                      </div>
                    </div>

                    <!-- Technique -->
                    <div>
                      <div class="flex justify-between text-[10px] font-bold mb-1">
                        <span class="text-blue-400">TECH</span>
                        <span class="text-gray-600 tabular-nums">
                          {{ Math.round(playerData.bp.technique).toLocaleString() }}
                        </span>
                      </div>

                      <div class="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          class="h-full bg-blue-400 transition-all duration-1000"
                          :style="{ width: (playerData.bp.technique / (playerData.bp.total * 0.45) * 100) + '%' }"
                        ></div>
                      </div>
                    </div>

                    <!-- Visual -->
                    <div>
                      <div class="flex justify-between text-[10px] font-bold mb-1">
                        <span class="text-orange-400">VIS</span>
                        <span class="text-gray-600 tabular-nums">
                          {{ Math.round(playerData.bp.visual).toLocaleString() }}
                        </span>
                      </div>

                      <div class="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          class="h-full bg-orange-400 transition-all duration-1000"
                          :style="{ width: (playerData.bp.visual / (playerData.bp.total * 0.45) * 100) + '%' }"
                        ></div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div class="border-b w-full pt-2"></div>

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
    const trainingString = isTrained ? '_after_training' : '_normal';
    let cardDetails = newPlayerData.enriched_cards?.find(card => card.situationId === cardId);

    if (!cardDetails?.resourceSetName) {
      try {
        const res = await api.get(`/api/cards/${cardId}`);
        cardDetails = res.data;
      } catch (error) {
        cardDetails = null;
      }
    }

    if (cardDetails?.resourceSetName) {
      leaderCardIllustUrl.value = `https://bestdori.com/assets/jp/characters/resourceset/${cardDetails.resourceSetName}_rip/trim${trainingString}.png`;
    } else {
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
    const [res, degreesRes] = await Promise.all([
      api.get(`/api/player/${playerUid}`),
      api.get(`/api/degrees/player/${playerUid}/all_degrees`)
    ]);
    playerData.value = res.data;
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
