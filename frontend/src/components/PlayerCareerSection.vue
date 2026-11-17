<template>
  <div v-if="trendEvents.length > 0 || monthlyRecords.length > 0" class="space-y-6">
    <!-- 历届活动 PT 曲线 -->
    <section v-if="trendEvents.length > 0" class="md-elevated-card p-4 sm:p-6">
      <div class="flex flex-wrap items-center justify-between gap-2 mb-4">
        <h3 class="md-section-title">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 md-section-title-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M3 17l6-6 4 4 8-8m0 0h-5m5 0v5" />
          </svg>
          <span>{{ t('player.eventTrends') }}</span>
        </h3>
        <span class="text-xs text-md-on-surface-variant tabular-nums">
          {{ trendEvents.length }}
        </span>
      </div>

      <!-- 多期个人曲线对比面板（勾选 >= 1 个有曲线的活动后展示） -->
      <div
        v-if="compareEventIds.length > 0"
        class="mb-5 rounded-2xl bg-md-surface-container-low border border-md-outline-variant p-4"
      >
        <div class="flex flex-wrap items-center justify-between gap-2 mb-3">
          <div>
            <h4 class="text-sm font-bold text-md-on-surface">{{ t('player.compareTitle') }}</h4>
            <p v-if="compareEventIds.length < 2" class="text-xs text-md-on-surface-variant mt-0.5">
              {{ t('player.compareHint') }}
            </p>
          </div>
          <button
            type="button"
            @click="compareEventIds = []"
            class="md-text-button h-7 px-3 text-xs border border-md-outline-variant/80"
          >
            {{ t('player.compareClear') }}
          </button>
        </div>

        <div v-if="isCompareLoading" class="h-56 flex items-center justify-center text-xs text-md-on-surface-variant animate-pulse">
          {{ t('player.detailLoading') }}
        </div>
        <PlayerCareerChart
          v-else-if="compareDatasets.length > 0"
          mode="compare"
          :datasets="compareDatasets"
          height-class="h-60 sm:h-72"
        />
        <div v-else class="py-6 text-center text-xs text-md-on-surface-variant">
          {{ t('player.noCurveData') }}
        </div>
      </div>

      <!-- 活动曲线卡片网格 -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <article
          v-for="ev in trendEvents"
          :key="ev.event_id"
          class="rounded-2xl bg-md-surface-container-low/70 border border-md-outline-variant/80 p-4 flex flex-col gap-3 transition-colors hover:border-md-outline"
          :class="{ 'lg:col-span-2': expandedEvents[ev.event_id] }"
        >
          <!-- 头部：期数 + 类型 + 标题 + 跳转 -->
          <div class="flex flex-wrap items-start justify-between gap-2">
            <div class="min-w-0 flex-1 space-y-1">
              <div class="flex flex-wrap items-center gap-1.5">
                <span class="px-2 py-0.5 rounded-full text-[11px] font-bold bg-md-primary-container text-md-on-primary-container tabular-nums">
                  #{{ ev.event_id }}
                </span>
                <span v-if="ev.event_type" class="md-chip text-[11px]">
                  {{ eventTypeLabel(ev.event_type) }}
                </span>
                <span class="md-chip md-chip--outlined text-[11px] font-semibold tabular-nums">
                  {{ t('player.rankPlace', { rank: ev.rank }) }}
                </span>
              </div>
              <h4 class="font-bold text-base text-md-on-surface leading-snug break-words">
                {{ ev.event_name || t('player.eventNum', { id: ev.event_id }) }}
              </h4>
              <div v-if="ev.start_at" class="text-[11px] text-md-on-surface-variant tabular-nums">
                {{ formatTs(ev.start_at) }} ~ {{ formatTs(ev.end_at) }}
              </div>
            </div>

            <router-link
              :to="`/${ev.event_id}`"
              class="md-text-button h-7 px-2.5 text-xs border border-md-outline-variant/70 flex-shrink-0"
            >
              {{ t('player.viewEventPage') }}
            </router-link>
          </div>

          <!-- PT 与分差 -->
          <div v-if="ev.pt !== null && ev.pt !== undefined" class="flex flex-wrap items-baseline justify-between gap-2 pt-1">
            <div class="tabular-nums">
              <span class="text-xl font-black text-md-pt leading-tight">
                {{ ev.pt.toLocaleString() }}
              </span>
              <span class="text-[11px] font-semibold text-md-on-surface-variant ml-1">PT</span>
            </div>
            <div class="text-[11px] font-medium space-x-2 tabular-nums">
              <span v-if="ev.rank === 1 && ev.lead_to_second !== null" class="text-md-increment">
                {{ t('player.leadBy', { pt: ev.lead_to_second.toLocaleString() }) }}
              </span>
              <template v-else>
                <span v-if="ev.gap_to_first > 0" class="text-md-on-surface-variant">
                  {{ t('player.gapToFirst', { pt: ev.gap_to_first.toLocaleString() }) }}
                </span>
                <span
                  v-if="ev.gap_to_prev !== null && ev.gap_to_prev !== ev.gap_to_first"
                  class="text-md-on-surface-variant"
                >
                  {{ t('player.gapToPrev', { pt: ev.gap_to_prev.toLocaleString() }) }}
                </span>
              </template>
            </div>
          </div>

          <!-- 当时冲榜名字与签名（呼应改名历史） -->
          <div
            v-if="ev.has_local_detail && (ev.name_used || ev.signature)"
            class="rounded-xl bg-md-surface-container-lowest/90 border border-md-outline-variant/60 px-3 py-2 space-y-1 text-xs"
          >
            <div v-if="ev.name_used" class="flex flex-wrap items-center gap-1.5">
              <span class="font-medium text-md-on-surface">{{ ev.name_used }}</span>
              <span
                v-if="currentName && ev.name_used !== currentName"
                class="px-1.5 py-0.5 rounded bg-md-secondary-container text-md-on-secondary-container text-[10px] font-semibold"
              >
                {{ t('player.nameUsedAtEvent', { name: ev.name_used }) }}
              </span>
            </div>
            <p v-if="ev.signature" class="text-md-on-surface-variant italic break-words">
              {{ ev.signature }}
            </p>
          </div>

          <!-- 交互控制栏 -->
          <div
            v-if="ev.has_local_detail && ev.has_chart"
            class="flex flex-wrap items-center justify-between gap-2 pt-2 border-t md-divider/60"
          >
            <button
              type="button"
              @click="toggleEventDetail(ev)"
              class="md-text-button h-8 px-3 text-xs border border-md-outline-variant/80"
            >
              <span>{{ expandedEvents[ev.event_id] ? t('player.collapseDetail') : t('player.expandDetail') }}</span>
              <svg
                xmlns="http://www.w3.org/2000/svg"
                class="h-3.5 w-3.5 transition-transform duration-200"
                :class="{ 'rotate-180': expandedEvents[ev.event_id] }"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                stroke-width="2"
              >
                <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            <label class="inline-flex items-center gap-1.5 text-xs text-md-on-surface-variant cursor-pointer select-none px-2 py-1 rounded-full hover:bg-md-surface-container-high">
              <input
                type="checkbox"
                :checked="compareEventIds.includes(ev.event_id)"
                @change="toggleCompare(ev.event_id)"
                class="rounded accent-current text-md-primary"
              />
              <span>{{ t('player.compareCheckbox') }}</span>
            </label>
          </div>

          <!-- 展开详情：个人 PT 曲线 + 同场参考线 -->
          <div
            v-if="expandedEvents[ev.event_id]"
            class="pt-3 border-t md-divider/60 space-y-3"
          >
            <div v-if="loadingEvents[ev.event_id]" class="py-8 text-center text-xs text-md-on-surface-variant animate-pulse">
              {{ t('player.detailLoading') }}
            </div>

            <template v-else>
              <div v-if="singleEventDatasets(ev).length > 0" class="space-y-2">
                <div class="flex flex-wrap items-center justify-end gap-2">
                  <label class="inline-flex items-center gap-1.5 text-xs text-md-on-surface-variant cursor-pointer select-none">
                    <input
                      type="checkbox"
                      v-model="showRefsMap[ev.event_id]"
                      class="rounded accent-current text-md-primary"
                    />
                    <span>{{ t('player.showRefs') }}</span>
                  </label>
                </div>
                <PlayerCareerChart
                  mode="single"
                  :datasets="singleEventDatasets(ev)"
                  :x-min="ev.start_at || null"
                  :x-max="ev.end_at || null"
                  height-class="h-56 sm:h-64"
                />
              </div>
              <div v-else class="py-4 text-center text-xs text-md-on-surface-variant">
                {{ t('player.noCurveData') }}
              </div>
            </template>
          </div>
        </article>
      </div>
    </section>

    <!-- 月榜 PT 曲线（本地月榜有记录时展示） -->
    <section v-if="monthlyRecords.length > 0" class="md-elevated-card p-4 sm:p-6">
      <div class="flex flex-wrap items-center justify-between gap-2 mb-4">
        <h3 class="md-section-title">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 md-section-title-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
          <span>{{ t('player.monthlyTrends') }}</span>
        </h3>
        <span class="text-xs text-md-on-surface-variant tabular-nums">{{ monthlyRecords.length }}</span>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <article
          v-for="m in monthlyRecords"
          :key="m.monthly_id"
          class="rounded-2xl bg-md-surface-container-low/70 border border-md-outline-variant/80 p-4 flex flex-col gap-3"
          :class="{ 'lg:col-span-2': expandedMonthly[m.monthly_id] }"
        >
          <div class="flex flex-wrap items-start justify-between gap-2">
            <div class="min-w-0 flex-1 space-y-1">
              <div class="flex flex-wrap items-center gap-1.5">
                <span class="px-2 py-0.5 rounded-full text-[11px] font-bold bg-md-primary-container text-md-on-primary-container tabular-nums">
                  {{ t('player.monthlyNum', { id: m.monthly_id }) }}
                </span>
                <span class="md-chip md-chip--outlined text-[11px] font-semibold tabular-nums">
                  {{ t('player.rankPlace', { rank: m.rank }) }}
                </span>
              </div>
              <h4 class="font-bold text-base text-md-on-surface leading-snug break-words">
                {{ m.name || t('player.monthlyNum', { id: m.monthly_id }) }}
              </h4>
              <div v-if="m.start_at" class="text-[11px] text-md-on-surface-variant tabular-nums">
                {{ formatTs(m.start_at) }} ~ {{ m.end_at ? formatTs(m.end_at) : '-' }}
              </div>
            </div>

            <router-link
              :to="`/monthly/${m.monthly_id}`"
              class="md-text-button h-7 px-2.5 text-xs border border-md-outline-variant/70 flex-shrink-0"
            >
              {{ t('player.viewMonthlyPage') }}
            </router-link>
          </div>

          <div class="flex flex-wrap items-center justify-between gap-3">
            <DegreeDisplay
              v-if="m.degree_id && allDegreesData"
              :degreeId="m.degree_id"
              :allDegreesData="allDegreesData"
              :displayWidth="136"
            />
            <div class="text-right tabular-nums ml-auto">
              <div class="text-xl font-black text-md-pt leading-tight">
                {{ m.pt.toLocaleString() }}
                <span class="text-[11px] font-semibold text-md-on-surface-variant">PT</span>
              </div>
              <div class="text-[11px] font-medium mt-0.5 space-x-2">
                <span v-if="m.rank === 1 && m.lead_to_second !== null" class="text-md-increment">
                  {{ t('player.leadBy', { pt: m.lead_to_second.toLocaleString() }) }}
                </span>
                <template v-else>
                  <span v-if="m.gap_to_first > 0" class="text-md-on-surface-variant">
                    {{ t('player.gapToFirst', { pt: m.gap_to_first.toLocaleString() }) }}
                  </span>
                  <span
                    v-if="m.gap_to_prev !== null && m.gap_to_prev !== m.gap_to_first"
                    class="text-md-on-surface-variant"
                  >
                    {{ t('player.gapToPrev', { pt: m.gap_to_prev.toLocaleString() }) }}
                  </span>
                </template>
              </div>
            </div>
          </div>

          <div
            v-if="m.name_used || m.signature"
            class="rounded-xl bg-md-surface-container-lowest/90 border border-md-outline-variant/60 px-3 py-2 space-y-1 text-xs"
          >
            <div v-if="m.name_used" class="flex flex-wrap items-center gap-1.5">
              <span class="font-medium text-md-on-surface">{{ m.name_used }}</span>
              <span
                v-if="currentName && m.name_used !== currentName"
                class="px-1.5 py-0.5 rounded bg-md-secondary-container text-md-on-secondary-container text-[10px] font-semibold"
              >
                {{ t('player.nameUsedAtEvent', { name: m.name_used }) }}
              </span>
            </div>
            <p v-if="m.signature" class="text-md-on-surface-variant italic break-words">
              {{ m.signature }}
            </p>
          </div>

          <div
            v-if="m.has_chart"
            class="flex items-center justify-between pt-2 border-t md-divider/60"
          >
            <button
              type="button"
              @click="toggleMonthlyDetail(m)"
              class="md-text-button h-8 px-3 text-xs border border-md-outline-variant/80"
            >
              <span>{{ expandedMonthly[m.monthly_id] ? t('player.collapseDetail') : t('player.expandDetail') }}</span>
              <svg
                xmlns="http://www.w3.org/2000/svg"
                class="h-3.5 w-3.5 transition-transform duration-200"
                :class="{ 'rotate-180': expandedMonthly[m.monthly_id] }"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                stroke-width="2"
              >
                <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </button>
          </div>

          <div v-if="expandedMonthly[m.monthly_id]" class="pt-3 border-t md-divider/60 space-y-3">
            <div v-if="loadingMonthly[m.monthly_id]" class="py-8 text-center text-xs text-md-on-surface-variant animate-pulse">
              {{ t('player.detailLoading') }}
            </div>
            <div v-else-if="singleMonthlyDatasets(m).length > 0" class="space-y-2">
              <div class="flex flex-wrap items-center justify-end gap-2">
                <label class="inline-flex items-center gap-1.5 text-xs text-md-on-surface-variant cursor-pointer select-none">
                  <input
                    type="checkbox"
                    v-model="showMonthlyRefsMap[m.monthly_id]"
                    class="rounded accent-current text-md-primary"
                  />
                  <span>{{ t('player.showRefs') }}</span>
                </label>
              </div>
              <PlayerCareerChart
                mode="single"
                :datasets="singleMonthlyDatasets(m)"
                :x-min="m.start_at || null"
                :x-max="m.end_at || null"
                height-class="h-56 sm:h-64"
              />
            </div>
            <div v-else class="py-4 text-center text-xs text-md-on-surface-variant">
              {{ t('player.noCurveData') }}
            </div>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue';
import api from '../api';
import DegreeDisplay from './DegreeDisplay.vue';
import PlayerCareerChart from './PlayerCareerChart.vue';
import { formatTs } from '../utils.js';
import { useI18n } from '../i18n.js';

const { t } = useI18n();

const props = defineProps({
  uid: { type: [String, Number], required: true },
  currentName: { type: String, default: '' },
  mergedEvents: { type: Array, default: () => [] },
  monthlyRecords: { type: Array, default: () => [] },
  allDegreesData: { type: Object, default: null },
});

const expandedEvents = reactive({});
const loadingEvents = reactive({});
const eventChartCache = reactive({});
const showRefsMap = reactive({});

const expandedMonthly = reactive({});
const loadingMonthly = reactive({});
const monthlyChartCache = reactive({});
const showMonthlyRefsMap = reactive({});

const compareEventIds = ref([]);
const isCompareLoading = ref(false);

const trendEvents = computed(() =>
  (props.mergedEvents || []).filter((ev) => ev.has_local_detail || ev.has_chart)
);

function eventTypeLabel(type) {
  const key = `event.type.${type}`;
  const translated = t(key);
  return translated === key ? type : translated;
}

function resetLocalCaches() {
  for (const obj of [
    expandedEvents, loadingEvents, eventChartCache, showRefsMap,
    expandedMonthly, loadingMonthly, monthlyChartCache, showMonthlyRefsMap,
  ]) {
    Object.keys(obj).forEach((k) => delete obj[k]);
  }
  compareEventIds.value = [];
}

async function ensureEventChart(ev) {
  const eid = String(ev.event_id);
  if (!ev.has_chart || eventChartCache[eid]) return;

  loadingEvents[eid] = true;
  try {
    const res = await api.get(`/api/events/${eid}/chart?interval=15m`);
    eventChartCache[eid] = res.data || {};
  } catch (_) {
    // Keep cache empty so collapsing/re-expanding can retry transient failures.
  } finally {
    delete loadingEvents[eid];
  }
}

async function toggleEventDetail(ev) {
  const eid = String(ev.event_id);
  const next = !expandedEvents[eid];
  expandedEvents[eid] = next;
  if (next) {
    if (showRefsMap[eid] === undefined) showRefsMap[eid] = true;
    await ensureEventChart(ev);
  }
}

async function toggleCompare(eid) {
  const idStr = String(eid);
  if (compareEventIds.value.includes(idStr)) {
    compareEventIds.value = compareEventIds.value.filter((x) => x !== idStr);
    return;
  }
  compareEventIds.value = [...compareEventIds.value, idStr];
  const ev = trendEvents.value.find((item) => String(item.event_id) === idStr);
  if (ev && !eventChartCache[idStr]) {
    isCompareLoading.value = true;
    try {
      await ensureEventChart(ev);
    } finally {
      isCompareLoading.value = false;
    }
  }
}

function buildSingleSeriesDatasets(seriesMap, includeRefs, top1Uid = null, top10Uid = null) {
  const uidStr = String(props.uid);
  const userEntry = seriesMap?.[uidStr];
  if (!userEntry || !Array.isArray(userEntry.points) || userEntry.points.length === 0) {
    return [];
  }

  const datasets = [{
    label: userEntry.name || props.currentName || uidStr,
    points: userEntry.points.map((p) => ({ x: p.t, y: p.pt })),
    isRef: false,
  }];

  if (includeRefs) {
    const sorted = Object.entries(seriesMap)
      .filter(([, entry]) => Array.isArray(entry?.points) && entry.points.length > 0)
      .map(([k, entry]) => ({
        uid: k,
        points: entry.points,
        lastPt: entry.points[entry.points.length - 1].pt || 0,
      }))
      .sort((a, b) => b.lastPt - a.lastPt);

    const top1Key = top1Uid ? String(top1Uid) : null;
    const top10Key = top10Uid ? String(top10Uid) : null;

    const top1 = (top1Key && seriesMap[top1Key]?.points?.length)
      ? { uid: top1Key, points: seriesMap[top1Key].points }
      : sorted[0];
    const top10 = (top10Key && seriesMap[top10Key]?.points?.length)
      ? { uid: top10Key, points: seriesMap[top10Key].points }
      : sorted[Math.min(9, sorted.length - 1)];

    if (top1 && top1.uid !== uidStr) {
      datasets.push({
        label: t('player.refTop1'),
        points: top1.points.map((p) => ({ x: p.t, y: p.pt })),
        isRef: true,
        refRole: 'top1',
      });
    }
    if (top10 && top10.uid !== uidStr && top10.uid !== top1?.uid) {
      datasets.push({
        label: t('player.refTop10'),
        points: top10.points.map((p) => ({ x: p.t, y: p.pt })),
        isRef: true,
        refRole: 'top10',
      });
    }
  }
  return datasets;
}

function singleEventDatasets(ev) {
  const eid = String(ev.event_id);
  return buildSingleSeriesDatasets(
    eventChartCache[eid],
    Boolean(showRefsMap[eid]),
    ev.top1_uid,
    ev.top10_uid,
  );
}

const compareDatasets = computed(() => {
  const uidStr = String(props.uid);
  const out = [];
  for (const eid of compareEventIds.value) {
    const ev = trendEvents.value.find((item) => String(item.event_id) === eid);
    const seriesMap = eventChartCache[eid];
    const entry = seriesMap?.[uidStr];
    if (!ev || !entry || !Array.isArray(entry.points) || entry.points.length === 0) continue;
    const baseTs = ev.start_at || entry.points[0].t;
    const endCutoff = ev.end_at ? ev.end_at + 900000 : null;
    const labelName = ev.event_name ? `#${eid} ${ev.event_name}` : `#${eid}`;
    out.push({
      label: `${labelName} (#${ev.rank})`,
      points: entry.points
        .filter((p) => !endCutoff || p.t <= endCutoff)
        .map((p) => {
          const ts = ev.end_at ? Math.min(p.t, ev.end_at) : p.t;
          return { x: Math.max(0, (ts - baseTs) / 3600000), y: p.pt };
        }),
      isRef: false,
    });
  }
  return out;
});

async function toggleMonthlyDetail(m) {
  const mid = m.monthly_id;
  const next = !expandedMonthly[mid];
  expandedMonthly[mid] = next;
  if (next && showMonthlyRefsMap[mid] === undefined) {
    showMonthlyRefsMap[mid] = true;
  }
  if (!next || !m.has_chart || monthlyChartCache[mid]) return;

  loadingMonthly[mid] = true;
  try {
    const res = await api.get(`/api/monthly/${mid}/chart?interval=15m`);
    monthlyChartCache[mid] = res.data || {};
  } catch (_) {
    // Keep cache empty so collapsing/re-expanding can retry transient failures.
  } finally {
    delete loadingMonthly[mid];
  }
}

function singleMonthlyDatasets(m) {
  return buildSingleSeriesDatasets(
    monthlyChartCache[m.monthly_id],
    Boolean(showMonthlyRefsMap[m.monthly_id]),
    m.top1_uid,
    m.top10_uid,
  );
}

watch(() => props.uid, () => {
  resetLocalCaches();
});
</script>
