<template>
  <div class="degree-shell flex-shrink-0 overflow-visible" :style="degreeStyle">
    <div class="degree-container relative w-[230px] h-[50px] origin-top-left" :style="innerStyle">
      <img
        v-if="baseImageUrl"
        :src="baseImageUrl"
        alt="Degree Base"
        class="absolute top-0 left-0 max-w-none"
      >
      <img
        v-if="frameImageUrl"
        :src="frameImageUrl"
        alt="Degree Frame"
        class="absolute top-0 left-0 max-w-none"
      >
      <img
        v-if="iconImageUrl"
        :src="iconImageUrl"
        alt="Degree Icon"
        class="absolute top-0 left-0 max-w-none"
      >
    </div>
  </div>
</template>


<script setup>
import { defineProps, computed } from 'vue';

const props = defineProps({
  // Old mode props
  degreeId: {
    type: Number,
    required: false
  },
  allDegreesData: {
    type: Object,
    required: false
  },
  // New mode props for event degrees
  rank: {
    type: Number,
    required: false
  },
  event_id: {
    type: String,
    required: false
  },
  displayWidth: {
    type: [Number, String],
    default: 230
  }
});

const Bestdoriurl = 'https://bestdori.com';
const originalWidth = 230;
const originalHeight = 50;

const displayWidthNumber = computed(() => {
  if (typeof props.displayWidth === 'number') return props.displayWidth;
  const parsed = Number.parseFloat(props.displayWidth);
  return Number.isFinite(parsed) ? parsed : originalWidth;
});

const scaleValue = computed(() => displayWidthNumber.value / originalWidth);

const degreeStyle = computed(() => ({
  width: `${displayWidthNumber.value}px`,
  height: `${originalHeight * scaleValue.value}px`
}));

const innerStyle = computed(() => ({
  transform: `scale(${scaleValue.value})`
}));

// Helper to determine the rank suffix for URL construction
const getRankSuffix = (rank) => {
  if (rank === 1 || rank === 2 || rank === 3) {
    return rank.toString();
  }
  if ((rank >= 4 && rank <= 10) || rank === 0) {
    return '10';
  }
  return null;
};

const isNewMode = computed(() => props.rank !== undefined && props.event_id !== undefined);

const baseImageUrl = computed(() => {
  if (isNewMode.value) {
    return `${Bestdoriurl}/assets/jp/thumb/degree_rip/degree_event${props.event_id}_point.png`;
  }
  // --- Old Mode Logic ---
  if (props.degreeId && props.allDegreesData) {
    const degreeData = props.allDegreesData[props.degreeId.toString()];
    if (!degreeData || !degreeData.baseImageName) return null;
    const baseName = degreeData.baseImageName[0];
    if (baseName.startsWith("ani_")) return null; // Animation not supported
    return `${Bestdoriurl}/assets/jp/thumb/degree_rip/${baseName}.png`;
  }
  return null;
});

const frameImageUrl = computed(() => {
  if (isNewMode.value) {
    const rankSuffix = getRankSuffix(props.rank);
    if (!rankSuffix) return null;
    return `${Bestdoriurl}/assets/jp/thumb/degree_rip/event_point_${rankSuffix}.png`;
  }
  // --- Old Mode Logic ---
  if (props.degreeId && props.allDegreesData) {
    const degreeData = props.allDegreesData[props.degreeId.toString()];
    if (!degreeData || !degreeData.degreeType || !degreeData.rank) return null;
    const degreeType = degreeData.degreeType[0];
    const rank = degreeData.rank[0];
    if (degreeType === "normal" || degreeType === null || rank === 'none') return null;
    const frameName = `${degreeType}_${rank}`;
    return `${Bestdoriurl}/assets/jp/thumb/degree_rip/${frameName}.png`;
  }
  return null;
});

const iconImageUrl = computed(() => {
  if (isNewMode.value) {
    const rankSuffix = getRankSuffix(props.rank);
    if (!rankSuffix) return null;
    return `${Bestdoriurl}/assets/jp/thumb/degree_rip/event_point_icon_${rankSuffix}.png`;
  }
  // --- Old Mode Logic ---
  if (props.degreeId && props.allDegreesData) {
    const degreeData = props.allDegreesData[props.degreeId.toString()];
    if (!degreeData || !degreeData.iconImageName || !degreeData.rank) return null;
    const iconName = degreeData.iconImageName[0];
    const degreeType = degreeData.degreeType[0];
    if (iconName === "none" || degreeType === "try_clear") return null;
    const rank = degreeData.rank[0];
    const fullIconName = `${iconName}_${rank}`;
    return `${Bestdoriurl}/assets/jp/thumb/degree_rip/${fullIconName}.png`;
  }
  return null;
});

</script>

<style scoped>
.degree-container {
  /* You might need to adjust width/height based on actual degree image sizes */
  /* The example code used 230x50 for the canvas */
}
</style>