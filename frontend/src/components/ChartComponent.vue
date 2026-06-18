<template>
  <div class="relative w-full h-[800px] sm:h-[900px] md:h-[1000px] lg:h-[1100px]">
    <div class="flex justify-end gap-2 mb-2">
      <button @click="hideAll" class="px-2 py-1 text-xs border rounded bg-gray-100 hover:bg-gray-200">隐藏所有</button>
      <button @click="showAll" class="px-2 py-1 text-xs border rounded bg-gray-100 hover:bg-gray-200">显示所有</button>
    </div>
    <canvas ref="canvasRef" class="w-full h-full block"></canvas>
    <div ref="controlsRef" class="absolute flex items-start gap-2" style="left: -9999px; top: 0;">
      <div class="flex flex-col gap-1">
        <button @click="zoomIn" class="w-6 h-6 flex items-center justify-center text-sm border rounded-full bg-gray-100/50 hover:bg-gray-100 backdrop-blur-sm">+</button>
        <button @click="zoomOut" class="w-6 h-6 flex items-center justify-center text-sm border rounded-full bg-gray-100/50 hover:bg-gray-100 backdrop-blur-sm">-</button>
        <button @click="resetZoom" class="w-6 h-6 flex items-center justify-center text-sm border rounded-full bg-gray-100/50 hover:bg-gray-100 backdrop-blur-sm">↺</button>
      </div>
      <div class="grid grid-cols-3 gap-1">
        <button @click="panChart(0, 50)" class="w-6 h-6 flex items-center justify-center text-sm border rounded-full bg-gray-100/50 hover:bg-gray-100 backdrop-blur-sm col-start-2">↑</button>
        <button @click="panChart(50, 0)" class="w-6 h-6 flex items-center justify-center text-sm border rounded-full bg-gray-100/50 hover:bg-gray-100 backdrop-blur-sm col-start-1 row-start-2">←</button>
        <button @click="panChart(-50, 0)" class="w-6 h-6 flex items-center justify-center text-sm border rounded-full bg-gray-100/50 hover:bg-gray-100 backdrop-blur-sm col-start-3 row-start-2">→</button>
        <button @click="panChart(0, -50)" class="w-6 h-6 flex items-center justify-center text-sm border rounded-full bg-gray-100/50 hover:bg-gray-100 backdrop-blur-sm col-start-2 row-start-3">↓</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, onBeforeUnmount, watch, ref } from 'vue'
import { Chart, registerables } from 'chart.js'
import 'chartjs-adapter-date-fns';
import { zhCN } from 'date-fns/locale';
import zoomPlugin from 'chartjs-plugin-zoom';
Chart.register(...registerables, zoomPlugin);

const props = defineProps({
  series: Object,
  currentEvent: Object
})

const canvasRef = ref(null)
const controlsRef = ref(null)
let chart = null
let lastEventId = null
const MAX_POINTS_PER_DATASET = 500

function hideAll() {
  if (!chart) return;
  chart.data.datasets.forEach((_, i) => {
    chart.hide(i);
  });
}

function showAll() {
  if (!chart) return;
  chart.data.datasets.forEach((_, i) => {
    chart.show(i);
  });
}

function resetZoom() {
  if (!chart) return;
  chart.resetZoom();
}

function zoomIn() {
  if (!chart) return;
  chart.zoom(1.1);
}

function zoomOut() {
  if (!chart) return;
  chart.zoom(0.9);
}

function panChart(x, y) {
  if (!chart) return;
  chart.pan({ x, y }, undefined, 'default');
}

const colorPalette = [
  '#5B8FF9', // Light Blue
  '#FF69B4', // Hot Pink
  '#6A0DAD', // Purple
  '#00BFFF', // Deep Sky Blue
  '#FF1493', // Deep Pink
  '#8A2BE2', // Blue Violet
  '#4169E1', // Royal Blue
  '#C71585', // Medium Violet Red
  '#9370DB', // Medium Purple
  '#1E90FF', // Dodger Blue
  '#FFB6C1', // Light Pink
  '#483D8B', // Dark Slate Blue
  '#F08080', // Light Coral (as a warm contrast)
  '#ADD8E6', // Light Blue
  '#DA70D6', // Orchid
  '#00008B', // Dark Blue
  '#FFC0CB', // Pink
  '#7B68EE', // Medium Slate Blue
  '#20B2AA', // Light Sea Green (as a cool contrast)
  '#BA55D3'  // Medium Orchid
];

function downsamplePoints(points, maxPoints) {
  if (!points || points.length <= maxPoints) return points
  const result = [points[0]]
  const inner = points.slice(1, -1)
  const bucketSize = Math.max(1, Math.floor(inner.length / (maxPoints - 2)))
  for (let i = 0; i < inner.length; i += bucketSize) {
    let best = inner[i]
    for (let j = i + 1; j < i + bucketSize && j < inner.length; j++) {
      if (inner[j].pt > best.pt) best = inner[j]
    }
    result.push(best)
  }
  result.push(points[points.length - 1])
  return result
}

function buildDatasets(series, event) {
  if (!series) return []
  return Object.keys(series).map((uid, index) => {
    const userSeries = series[uid]
    const color = colorPalette[index % colorPalette.length]
    const rawPoints = userSeries.points || []
    const sampled = downsamplePoints(rawPoints, MAX_POINTS_PER_DATASET)
    return {
      label: userSeries.name || uid,
      data: sampled.map(p => ({ x: p.t, y: p.pt })),
      tension: 0.1,
      pointRadius: 1,
      pointHoverRadius: 4,
      borderWidth: 2,
      borderColor: color,
      backgroundColor: color + '33'
    }
  })
}

const draw = () => {
  if (!canvasRef.value || !props.currentEvent) return

  const currentEventId = props.currentEvent.event_id
  const eventChanged = currentEventId !== lastEventId
  const datasets = buildDatasets(props.series, props.currentEvent)

  if (chart && !eventChanged) {
    // Same event, just update data in place
    chart.data.datasets = datasets
    chart.update('none')
    return
  }

  // Event changed or first render: full recreate needed
  if (chart) {
    chart.destroy()
    chart = null
  }

  // Don't create chart until we have actual data
  if (datasets.length === 0) return

  chart = new Chart(canvasRef.value.getContext('2d'), {
    type: 'line',
    data: { datasets },
    options: {
      maintainAspectRatio: false,
      responsive: true,
      animation: false,  // Disable animations for performance
      interaction: {
        mode: 'nearest',
        intersect: false
      },
      plugins: {
        legend: {
          position: 'top',
          fullSize: true,
          labels: {
            boxWidth: 12,
            font: { size: 12 }
          }
        },
        zoom: {
          limits: {
            x: {
              min: props.currentEvent.start_at,
              max: props.currentEvent.end_at,
            },
            y: {
              min: 0,
            }
          },
          pan: {
            enabled: false,
            mode: 'xy',
          },
          zoom: {
            wheel: { enabled: false },
            drag: { enabled: false },
            pinch: { enabled: false },
            mode: 'xy',
          }
        }
      },
      scales: {
        x: {
          type: 'time',
          min: props.currentEvent.start_at,
          max: props.currentEvent.end_at,
          adapters: {
            date: {
              locale: zhCN
            }
          },
          time: {
            unit: 'day',
            tooltipFormat: 'yyyy-MM-dd HH:mm',
            displayFormats: {
              day: 'MM-dd'
            }
          }
        },
        y: {
          beginAtZero: false
        }
      }
    }
  });

  lastEventId = currentEventId

  const calculatedMaxY = chart.scales.y.max
  chart.options.scales.y.max = calculatedMaxY
  chart.options.plugins.zoom.limits.y.max = calculatedMaxY
  chart.update('none')

  // Position controls inside the chart area
  if (controlsRef.value && chart.chartArea) {
    controlsRef.value.style.left = `${chart.chartArea.left + 0}px`
    controlsRef.value.style.top = `${chart.chartArea.top + 40}px`
  }
}

onMounted(draw)

onBeforeUnmount(() => {
  if (chart) {
    chart.destroy()
  }
})

// Shallow watch - only triggers when object references change
watch(() => props.series, draw)
watch(() => props.currentEvent, draw)
</script>
