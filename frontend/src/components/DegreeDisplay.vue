<template>
  <div class="degree-container relative w-[230px] h-[50px]">
    <img
      v-if="baseImageUrl"
      :src="baseImageUrl"
      alt="Degree Base"
      class="absolute top-0 left-0"
    >
    <img
      v-if="frameImageUrl"
      :src="frameImageUrl"
      alt="Degree Frame"
      class="absolute top-0 left-0"
    >
    <img
      v-if="iconImageUrl"
      :src="iconImageUrl"
      alt="Degree Icon"
      class="absolute top-0 left-0"
    >
  </div>
</template>


<script setup>
import { defineProps, computed } from 'vue';

const props = defineProps({
  degreeId: {
    type: Number,
    required: true
  },
  allDegreesData: {
    type: Object,
    required: true
  }
});

const Bestdoriurl = 'https://bestdori.com'; // Assuming Bestdoriurl is constant

const degreeData = computed(() => {
  return props.allDegreesData[props.degreeId.toString()];
});

const baseImageUrl = computed(() => {
  if (!degreeData.value || !degreeData.value.baseImageName) return null;
  const baseName = degreeData.value.baseImageName[0]; // Assuming server 'jp' is index 0
  if (baseName.startsWith("ani_")) {
    // For animated degrees, we'll just use a static fallback for now
    // or the first frame if a static representation is available.
    // Bestdori often has a static version like 'degreeXXX.png'
    // For simplicity, we'll try to construct a static URL if possible,
    // otherwise, this will be null.
    // This part needs more sophisticated logic if animated degrees are to be fully supported.
    // For now, we'll return null for animated degrees, or a placeholder.
    return null; // Or a placeholder image URL
  }
  return `${Bestdoriurl}/assets/jp/thumb/degree_rip/${baseName}.png`;
});

const frameImageUrl = computed(() => {
  if (!degreeData.value || !degreeData.value.degreeType || !degreeData.value.rank) return null;
  const degreeType = degreeData.value.degreeType[0]; // Assuming server 'jp' is index 0
  const rank = degreeData.value.rank[0]; // Assuming server 'jp' is index 0

  if (degreeType === "normal" || degreeType === null || rank === 'none') {
    return null;
  }
  const frameName = `${degreeType}_${rank}`;
  return `${Bestdoriurl}/assets/jp/thumb/degree_rip/${frameName}.png`;
});

const iconImageUrl = computed(() => {
  if (!degreeData.value || !degreeData.value.iconImageName || !degreeData.value.rank) return null;
  const iconName = degreeData.value.iconImageName[0]; // Assuming server 'jp' is index 0
  const degreeType = degreeData.value.degreeType[0]; // Assuming server 'jp' is index 0
  const rank = degreeData.value.rank[0]; // Assuming server 'jp' is index 0

  if (iconName === "none" || degreeType === "try_clear") { // "try_clear" degrees don't have an icon on the left
    return null;
  }
  const fullIconName = `${iconName}_${rank}`;
  return `${Bestdoriurl}/assets/jp/thumb/degree_rip/${fullIconName}.png`;
});
</script>

<style scoped>
.degree-container {
  /* You might need to adjust width/height based on actual degree image sizes */
  /* The example code used 230x50 for the canvas */
}
</style>