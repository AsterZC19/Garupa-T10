<template>
  <div>
    <h3 class="text-lg font-bold text-md-on-surface mb-4 text-center">{{ t('player.t10Records') }}</h3>

    <div v-if="records.length > 0" :class="gridClass">
      <div
        v-for="degree in records"
        :key="degree.event_id"
        class="p-2 bg-md-surface-container-high hover:bg-md-surface-container-highest rounded-xl transition-all duration-200 flex flex-col items-center border border-transparent hover:border-md-primary"
      >
        <router-link :to="'/' + degree.event_id" class="text-center mb-1">
          <p class="font-bold text-md-primary text-[10px]">
            {{ t('player.eventNum', { id: degree.event_id }) }}
          </p>
          <p class="text-[11px] text-md-on-surface-variant font-medium">
            {{ t('player.rankPlace', { rank: degree.rank }) }}
          </p>
        </router-link>

        <div class="w-full min-h-6 flex justify-center items-center overflow-visible">
          <DegreeDisplay
            :rank="Number(degree.rank)"
            :event_id="String(degree.event_id)"
            :displayWidth="104"
          />
        </div>
      </div>
    </div>

    <div v-else class="text-center py-8">
      <p class="text-md-on-surface-variant text-sm">{{ t('player.noT10Records') }}</p>
    </div>
  </div>
</template>

<script setup>
import DegreeDisplay from './DegreeDisplay.vue';
import { useI18n } from '../i18n.js';

const { t } = useI18n();

defineProps({
  records: { type: Array, default: () => [] },
  gridClass: { type: String, default: 'grid grid-cols-2 md:grid-cols-3 lg:grid-cols-3 gap-2' },
});
</script>
