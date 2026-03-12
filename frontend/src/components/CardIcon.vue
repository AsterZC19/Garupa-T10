<template>
  <div class="relative inline-block" :style="{ width: size + 'px', height: size + 'px' }">
    <!-- Card Image (Thumbnail) -->
    <img
      :src="cardImageUrl"
      class="absolute inset-0 w-full h-full object-cover rounded-[10%]"
      @error="handleError"
    />
    
    <!-- Frame -->
    <img
      v-if="frameUrl"
      :src="frameUrl"
      class="absolute inset-0 w-full h-full pointer-events-none"
    />

    <!-- Attribute Icon -->
    <img
      v-if="attributeIconUrl"
      :src="attributeIconUrl"
      class="absolute top-[2%] right-[2%] w-[25%] h-[25%] pointer-events-none"
    />

    <!-- Band Icon -->
    <img
      v-if="bandIconUrl"
      :src="bandIconUrl"
      class="absolute top-[2%] left-[2%] w-[25%] h-[25%] pointer-events-none"
    />

    <!-- Stars (Vertical on the left) -->
    <div class="absolute bottom-[5%] left-[5%] flex flex-col-reverse space-y-reverse space-y-[-0%] pointer-events-none">
      <img
        v-for="i in rarity"
        :key="i"
        :src="starUrl"
        class="w-[26%] h-auto"
      />
    </div>

    <!-- Master Rank (Limit Break Rank) -->
    <div v-if="limitBreakRank > 0" class="absolute top-[28%] right-[2%] flex flex-col items-end pointer-events-none">
       <div class="relative flex items-center justify-center w-[25%] h-[25%]">
          <img src="https://bestdori.com/res/icon/master.svg" class="w-full h-full" v-if="1" />
          <div v-else class="w-full h-full bg-gray-800 bg-opacity-70 rounded-full border border-gray-400"></div>
          <span class="absolute text-[10px] font-black text-white outline-black">{{ limitBreakRank }}</span>
       </div>
    </div>

    <!-- Skill Level (Red Box) -->
    <div v-if="skillLevel" class="absolute top-[72%] right-[2%] flex flex-col items-end pointer-events-none">
      <div class="bg-red-600 px-1 py-0.5 rounded-sm border border-white shadow-sm flex items-center justify-center w-[50%] h-[50%]">
        <span class="text-[10px] font-black text-white leading-none">{{ skillLevel }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  cardId: [Number, String],
  isTrained: Boolean,
  rarity: {
    type: Number,
    default: 0
  },
  attribute: String,
  bandId: [Number, String],
  resourceSetName: String,
  ripId: String,
  skillLevel: Number,
  limitBreakRank: Number,
  size: {
    type: Number,
    default: 80
  }
});

const cardImageUrl = computed(() => {
  const trainingString = props.isTrained ? '_after_training' : '_normal';
  if (!props.resourceSetName || !props.ripId) {
     return `https://bestdori.com/res/card/icon/${props.cardId}${trainingString}.png`;
  }
  // Use thumb URL as requested
  return `https://bestdori.com/assets/jp/thumb/chara/card00${props.ripId}_rip/${props.resourceSetName}${trainingString}.png`;
});

const frameUrl = computed(() => {
  if (!props.rarity) return null;
  if (props.rarity === 1) {
    return `https://bestdori.com/res/image/card-1-${props.attribute}.png`;
  }
  return `https://bestdori.com/res/image/card-${props.rarity}.png`;
});

const attributeIconUrl = computed(() => {
  if (!props.attribute) return null;
  return `https://bestdori.com/res/icon/${props.attribute}.svg`;
});

const bandIconUrl = computed(() => {
  if (!props.bandId) return null;
  return `https://bestdori.com/res/icon/band_${props.bandId}.svg`;
});

const starUrl = computed(() => {
  return props.isTrained 
    ? 'https://bestdori.com/res/icon/star_trained.png'
    : 'https://bestdori.com/res/icon/star.png';
});

const handleError = (e) => {
  if (e.target.src.includes('/assets/jp/thumb/')) {
    const trainingString = props.isTrained ? '_after_training' : '_normal';
    e.target.src = `https://bestdori.com/res/card/icon/${props.cardId}${trainingString}.png`;
  } else if (props.isTrained && e.target.src.includes('_after_training')) {
    e.target.src = `https://bestdori.com/res/card/icon/${props.cardId}_normal.png`;
  }
};
</script>
