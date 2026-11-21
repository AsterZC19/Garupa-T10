<template>
  <div>
    <!-- 快照更新时间 -->
    <div class="mb-2 text-right text-[11px] text-md-on-surface-variant">
      {{ t('table.updatedAt', { time: latestUpdateTime }) }}
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="md-elevated-card p-10 text-center text-md-on-surface-variant">
      <span class="animate-pulse">{{ t('common.loading') }}</span>
    </div>

    <!-- 空状态 -->
    <div v-else-if="!entries || entries.length === 0" class="md-elevated-card p-10 text-center text-md-on-surface-variant text-sm">
      {{ t('songTable.noData') }}
    </div>

    <!-- 歌榜 T10 表格 -->
    <div v-else class="md-elevated-card overflow-hidden">
      <div class="overflow-x-auto">
        <table class="min-w-full text-sm">
          <thead>
            <tr class="bg-md-surface-high text-md-on-surface-variant">
              <th class="px-3 py-2 text-center font-semibold whitespace-nowrap">{{ t('table.rank') }}</th>
              <th class="px-3 py-2 text-center font-semibold whitespace-nowrap">{{ t('table.uid') }}</th>
              <th class="px-3 py-2 text-center font-semibold whitespace-nowrap">{{ t('table.name') }}</th>
              <th class="px-3 py-2 text-center font-semibold whitespace-nowrap">{{ t('songTable.score') }}</th>
              <th class="px-3 py-2 text-center font-semibold whitespace-nowrap">{{ t('songTable.scoreGap') }}</th>
              <th class="px-3 py-2 text-center font-semibold whitespace-nowrap">{{ t('table.signature') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(p, idx) in entries"
              :key="`${p.rank ?? idx}-${p.uid ?? idx}`"
              class="hover:bg-md-surface-low border-b border-md-outline-variant last:border-b-0 transition-colors"
            >
              <td class="px-3 py-2 text-center whitespace-nowrap tabular-nums">{{ p.rank || (idx + 1) }}</td>
              <td class="px-3 py-2 text-center whitespace-nowrap tabular-nums">
                <router-link v-if="p.uid" :to="`/player/${p.uid}`" class="text-md-primary hover:underline">
                  {{ p.uid }}
                </router-link>
                <span v-else>-</span>
              </td>
              <td class="px-3 py-2 text-center whitespace-nowrap font-medium">{{ p.name || '-' }}</td>
              <td class="px-3 py-2 text-center whitespace-nowrap tabular-nums">
                <span class="text-[20px] font-semibold text-md-pt leading-tight">
                  {{ typeof p.score === 'number' ? p.score.toLocaleString() : (p.score ?? '-') }}
                </span>
              </td>
              <td class="px-3 py-2 text-center whitespace-nowrap tabular-nums text-[20px] font-semibold leading-tight">
                {{ formatGap(idx) }}
              </td>
              <td class="px-3 py-2 text-center whitespace-nowrap text-md-on-surface-variant">
                {{ p.introduction || '' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { formatTs } from '../utils.js';
import { useI18n } from '../i18n.js';

const { t } = useI18n();

const props = defineProps({
  entries: { type: Array, default: () => [] },
  updatedAt: { type: Number, default: null },
  loading: { type: Boolean, default: false },
});

const latestUpdateTime = computed(() => {
  if (typeof props.updatedAt === 'number' && props.updatedAt > 0) {
    return formatTs(props.updatedAt);
  }
  return '-';
});

function formatGap(idx) {
  if (idx <= 0) return '-';
  const prev = props.entries[idx - 1];
  const curr = props.entries[idx];
  if (typeof prev?.score === 'number' && typeof curr?.score === 'number') {
    return (prev.score - curr.score).toLocaleString();
  }
  return '-';
}
</script>
