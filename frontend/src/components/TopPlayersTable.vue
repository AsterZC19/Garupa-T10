<template>
  <div>
    <!-- 表头更新时间（与原逻辑一致） -->
    <div class="mb-2 text-right text-[11px] text-md-on-surface-variant">
      {{ t('table.updatedAt', { time: latestUpdateTime }) }}
    </div>

    <!-- 十位玩家连成一张 MD3 卡片表格，每位玩家下方多一行热力图 -->
    <div class="md-elevated-card overflow-hidden">
      <div class="overflow-x-auto">
        <table class="min-w-full text-sm">
          <thead>
            <tr class="bg-md-surface-high text-md-on-surface-variant">
              <th class="px-3 py-2 text-center font-semibold whitespace-nowrap">{{ t('table.rank') }}</th>
              <th class="px-3 py-2 text-center font-semibold whitespace-nowrap">{{ t('table.uid') }}</th>
              <th class="px-3 py-2 text-center font-semibold whitespace-nowrap">{{ t('table.name') }}</th>
              <th class="px-3 py-2 text-center font-semibold whitespace-nowrap">{{ t('table.pt') }}</th>
              <th class="px-3 py-2 text-center font-semibold whitespace-nowrap">{{ t('table.gap') }}</th>
              <th class="px-3 py-2 text-center font-semibold whitespace-nowrap">{{ t('table.hourlySpeed') }}</th>
              <th class="px-3 py-2 text-center font-semibold whitespace-nowrap">{{ t('table.speedRank') }}</th>
              <th class="px-3 py-2 text-center font-semibold whitespace-nowrap">{{ t('table.runCount') }}</th>
              <th class="px-3 py-2 text-center font-semibold whitespace-nowrap">{{ t('table.avgPt') }}</th>
              <th class="px-3 py-2 text-center font-semibold whitespace-nowrap">{{ t('table.signature') }}</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="(p, idx) in rows" :key="p.uid">
              <!-- 玩家数据行 -->
              <tr class="hover:bg-md-surface-low transition-colors">
                <td class="px-3 py-1.5 text-center whitespace-nowrap tabular-nums">{{ p.rank || (idx + 1) }}</td>
                <td class="px-3 py-1.5 text-center whitespace-nowrap tabular-nums">
                  <router-link v-if="p.uid" :to="`/player/${p.uid}`" class="text-md-primary hover:underline">
                    {{ p.uid }}
                  </router-link>
                  <span v-else>-</span>
                </td>
                <td class="px-3 py-1.5 text-center whitespace-nowrap font-medium">{{ p.name }}</td>
                <td class="px-3 py-1.5 text-center whitespace-nowrap tabular-nums">
                  <div class="text-[20px] font-semibold text-md-pt leading-tight">
                    {{ typeof p.pt === 'number' ? p.pt.toLocaleString() : p.pt }}
                  </div>
                  <div
                    v-if="typeof p.ptIncrease === 'number' && p.ptIncrease >= 0"
                    class="mt-0.5 text-[10px] font-bold text-md-increment leading-none"
                  >
                    +{{ p.ptIncrease.toLocaleString() }}
                  </div>
                </td>
                <td class="px-3 py-1.5 text-center whitespace-nowrap tabular-nums text-[20px] font-semibold leading-tight">
                  {{ idx > 0 && typeof (rows[idx - 1].pt - p.pt) === 'number'
                      ? (rows[idx - 1].pt - p.pt).toLocaleString()
                      : '-' }}
                </td>
                <td class="px-3 py-1.5 text-center whitespace-nowrap tabular-nums text-[20px] font-semibold text-md-increment leading-tight">
                  {{ typeof p.hourly_speed === 'number' ? p.hourly_speed.toLocaleString() : p.hourly_speed }}
                </td>
                <td class="px-3 py-1.5 text-center whitespace-nowrap tabular-nums">
                  {{ p.hourly_speed > 0 ? p.speed_rank : '-' }}
                </td>
                <td class="px-3 py-1.5 text-center whitespace-nowrap tabular-nums">{{ p.run_count }}</td>
                <td class="px-3 py-1.5 text-center whitespace-nowrap tabular-nums">{{ p.average_pt }}</td>
                <td class="px-3 py-1.5 text-center whitespace-nowrap text-md-on-surface-variant">{{ p.signature }}</td>
              </tr>

              <!-- 该玩家下方的一行热力图：仅用极淡底色 + 小边距与上方玩家信息区分，不占多余空间 -->
              <tr class="bg-md-surface-low border-b border-md-outline-variant last:border-b-0">
                <td :colspan="10" class="px-4 py-0.5">
                  <Heatmap
                    v-if="p.heatmap"
                    :counts="p.heatmap.counts"
                    :ref-ts="heatmapRefTs"
                    :global-max="heatmapGlobalMax"
                  />
                  <div v-else class="text-center text-xs text-md-on-surface-variant py-0.5">{{ t('table.noHeatmap') }}</div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import Heatmap from './Heatmap.vue';
import { formatTs } from '../utils.js';
import { useI18n } from '../i18n.js';

const { t } = useI18n();

const props = defineProps({
  players: Array,
  // 热力图数据：{ ref_ts, global_max, players: { uid: { counts } } }
  heatmapData: { type: Object, default: () => ({ ref_ts: null, global_max: 0, players: {} }) },
})

const latestUpdateTime = computed(() => {
  const timestamps = (props.players || [])
    .map(player => player.score_updated_at)
    .filter(timestamp => typeof timestamp === 'number')
  if (!timestamps.length) return '-'
  return formatTs(Math.max(...timestamps))
})

// 预计算：把每个玩家与各自的热力图对象绑好，模板里只取一次
const rows = computed(() =>
  (props.players || []).map(p => ({
    ...p,
    heatmap: props.heatmapData?.players?.[p.uid] || null,
  }))
)

const heatmapRefTs = computed(() => props.heatmapData?.ref_ts ?? null)
const heatmapGlobalMax = computed(() => props.heatmapData?.global_max || 0)
</script>
