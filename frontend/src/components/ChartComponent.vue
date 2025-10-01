<template>
  <div class="relative w-full" style="aspect-ratio: 2/1; min-height: 400px;">
    <div class="flex justify-end gap-2 mb-2">
      <button @click="hideAll" class="px-2 py-1 text-xs border rounded bg-gray-100 hover:bg-gray-200">隐藏所有</button>
      <button @click="showAll" class="px-2 py-1 text-xs border rounded bg-gray-100 hover:bg-gray-200">显示所有</button>
    </div>
    <canvas ref="canvasRef" class="w-full h-full"></canvas>
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

const draw = () => {
  if (!canvasRef.value || !props.currentEvent) return
  if (chart) {
    chart.destroy()
  }

  const datasets = props.series ? Object.keys(props.series).map((uid) => {
    const userSeries = props.series[uid]
    return {
      label: userSeries.name || uid,
      data: userSeries.points.map(p => ({ x: p.t, y: p.pt })),
      tension: 0.1,
      pointRadius: 1, // Make points smaller
      pointHoverRadius: 4, // Enlarge points on hover
      borderWidth: 2
    }
  }) : []

  chart = new Chart(canvasRef.value.getContext('2d'), {
    type: 'line',
    data: {
      datasets
    },
    options: {
      interaction: {
        mode: 'nearest',
        intersect: false
      },
      plugins: {
        legend: {
          position: 'top'
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
