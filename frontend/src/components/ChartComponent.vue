<template>
  <div class="relative w-full h-[800px] sm:h-[900px] md:h-[1000px] lg:h-[1100px]">
    <div class="flex justify-end gap-2 mb-2">
      <button @click="hideAll" class="px-2 py-1 text-xs border rounded bg-gray-100 hover:bg-gray-200">隐藏所有</button>
      <button @click="showAll" class="px-2 py-1 text-xs border rounded bg-gray-100 hover:bg-gray-200">显示所有</button>
    </div>
    <canvas ref="canvasRef" class="w-full h-full block"></canvas>
  </div>
</template>

<script setup>
import { onMounted, onBeforeUnmount, watch, ref } from 'vue'
import { Chart, registerables } from 'chart.js'
import 'chartjs-adapter-date-fns';
import { zhCN } from 'date-fns/locale';
Chart.register(...registerables)

const props = defineProps({
  series: Object,
  currentEvent: Object
})

const canvasRef = ref(null)
let chart = null

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

const draw = () => {
  if (!canvasRef.value || !props.currentEvent) return
  if (chart) {
    chart.destroy()
  }

  const datasets = props.series ? Object.keys(props.series).map((uid, index) => {
    const userSeries = props.series[uid]
    const color = colorPalette[index % colorPalette.length];
    return {
      label: userSeries.name || uid,
      data: userSeries.points.map(p => ({ x: p.t, y: p.pt })),
      tension: 0.1,
      pointRadius: 1, // Make points smaller
      pointHoverRadius: 4, // Enlarge points on hover
      borderWidth: 2,
      borderColor: color,
      backgroundColor: color + '33' // Add some transparency to the fill/point color
    }
  }) : []

  chart = new Chart(canvasRef.value.getContext('2d'), {
    type: 'line',
    data: {
      datasets
    },
    options: {
      maintainAspectRatio: false, // 不维持固定宽高比
      responsive: true,  // 保持响应式
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
            font: { size: 12 } // 调小字体
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
  })
}

onMounted(draw)

onBeforeUnmount(() => {
  if (chart) {
    chart.destroy()
  }
})

watch(() => [props.series, props.currentEvent], draw, { deep: true })
</script>
