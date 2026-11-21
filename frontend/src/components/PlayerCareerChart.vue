<template>
  <div class="relative w-full" :class="heightClass">
    <canvas ref="canvasRef" class="w-full h-full block"></canvas>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import {
  Chart,
  LineController,
  LineElement,
  PointElement,
  TimeScale,
  LinearScale,
  Legend,
  Tooltip,
} from 'chart.js';
import 'chartjs-adapter-date-fns';
import { zhCN, ja, enUS } from 'date-fns/locale';
import { isDark } from '../theme.js';
import { useI18n } from '../i18n.js';

Chart.register(LineController, LineElement, PointElement, TimeScale, LinearScale, Legend, Tooltip);

const { locale, t } = useI18n();

const props = defineProps({
  mode: { type: String, default: 'single' }, // 'single' | 'compare'
  datasets: { type: Array, default: () => [] }, // [{ label, points: [{x, y}], isRef }]
  xMin: { type: Number, default: null },
  xMax: { type: Number, default: null },
  heightClass: { type: String, default: 'h-56 sm:h-64' },
});

const canvasRef = ref(null);
let chart = null;

const lightPalette = ['#4d6584', '#e05a9a', '#2b8a6e', '#d97706', '#7c3aed', '#0284c7'];
const darkPalette = ['#8ca6c6', '#ff85c2', '#72b388', '#f5b76b', '#b88CFF', '#5cd6ff'];

const chartDateLocale = computed(() => {
  if (locale.value === 'ja') return ja;
  if (locale.value === 'en') return enUS;
  return zhCN;
});

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || null;
}

function buildChartDatasets() {
  const palette = isDark.value ? darkPalette : lightPalette;
  let mainIdx = 0;
  return props.datasets.map((ds) => {
    const isRef = Boolean(ds.isRef);
    const color = isRef
      ? (ds.refRole === 'top1'
          ? (isDark.value ? '#e5b869' : '#c78a20')
          : (isDark.value ? '#8e99ad' : '#6c7689'))
      : palette[(mainIdx++) % palette.length];
    return {
      label: ds.label,
      data: ds.points || [],
      borderColor: color,
      backgroundColor: `${color}22`,
      borderWidth: isRef ? 1.5 : 2.5,
      borderDash: isRef ? [5, 4] : [],
      pointRadius: (ds.points?.length || 0) <= 1 ? 3 : 0,
      pointHoverRadius: 4,
      tension: 0.12,
    };
  });
}

function renderChart() {
  if (!canvasRef.value) return;
  if (chart) {
    chart.destroy();
    chart = null;
  }
  const built = buildChartDatasets();
  if (built.length === 0) return;

  const gridColor = cssVar('--md-sys-color-outline-variant') || '#d0d5dd';
  const tickColor = cssVar('--md-sys-color-on-surface-variant') || '#667085';
  const labelColor = cssVar('--md-sys-color-on-surface') || '#1e2229';
  const tooltipOpts = {
    backgroundColor: cssVar('--md-sys-color-surface') || '#ffffff',
    titleColor: labelColor,
    bodyColor: labelColor,
    borderColor: gridColor,
    borderWidth: 1,
    padding: 10,
    cornerRadius: 8,
    boxPadding: 4,
  };

  const isCompare = props.mode === 'compare';
  const xScale = isCompare
    ? {
        type: 'linear',
        min: 0,
        grid: { color: gridColor },
        ticks: {
          color: tickColor,
          stepSize: 24,
          callback: (val) => `${val}h`,
        },
        title: {
          display: true,
          text: t('player.compareHoursLabel'),
          color: tickColor,
          font: { size: 11 },
        },
      }
    : {
        type: 'time',
        min: props.xMin ?? undefined,
        max: props.xMax ?? undefined,
        adapters: { date: { locale: chartDateLocale.value } },
        time: {
          tooltipFormat: 'MM/dd HH:mm',
          displayFormats: { hour: 'MM/dd HH:mm', day: 'MM/dd' },
        },
        grid: { color: gridColor },
        ticks: { color: tickColor, maxRotation: 0, autoSkipPadding: 14 },
      };

  chart = new Chart(canvasRef.value.getContext('2d'), {
    type: 'line',
    data: { datasets: built },
    options: {
      maintainAspectRatio: false,
      responsive: true,
      animation: false,
      interaction: { mode: 'nearest', axis: 'x', intersect: false },
      plugins: {
        legend: {
          position: 'top',
          labels: { boxWidth: 12, font: { size: 11 }, color: labelColor },
        },
        tooltip: {
          ...tooltipOpts,
          callbacks: isCompare
            ? {
                title: (items) => {
                  const x = items?.[0]?.parsed?.x;
                  return typeof x === 'number' ? `+${x.toFixed(1)}h` : '';
                },
                label: (ctx) => `${ctx.dataset.label}: ${Math.round(ctx.parsed.y).toLocaleString()} PT`,
              }
            : {
                label: (ctx) => `${ctx.dataset.label}: ${Math.round(ctx.parsed.y).toLocaleString()} PT`,
              },
        },
      },
      scales: {
        x: xScale,
        y: {
          min: 0,
          grid: { color: gridColor },
          ticks: {
            color: tickColor,
            callback: (val) => {
              if (val >= 1000000) return `${(val / 1000000).toFixed(1)}M`;
              if (val >= 1000) return `${Math.round(val / 1000)}K`;
              return val;
            },
          },
        },
      },
    },
  });
}

onMounted(renderChart);
watch(
  [() => props.datasets, () => props.mode, () => props.xMin, () => props.xMax, isDark, locale],
  renderChart,
  { flush: 'post' },
);
onBeforeUnmount(() => {
  chart?.destroy();
  chart = null;
});
</script>
