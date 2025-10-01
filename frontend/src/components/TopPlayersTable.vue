<template>
  <div class="overflow-x-auto">
    <table class="min-w-full bg-white border text-sm">
      <thead>
        <tr>
          <th class="p-2 border whitespace-nowrap">位次</th>
          <th class="p-2 border whitespace-nowrap">UID</th>
          <th class="p-2 border whitespace-nowrap">名字</th>
          <th class="p-2 border whitespace-nowrap">当前PT</th>
          <th class="p-2 border whitespace-nowrap">分差</th>
          <th class="p-2 border whitespace-nowrap">上一整点时速</th>
          <th class="p-2 border whitespace-nowrap">时速排名</th>
          <th class="p-2 border whitespace-nowrap">签名</th>
          <th class="p-2 border whitespace-nowrap">当前更新时间</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(p, idx) in players" :key="p.uid">
          <td class="p-2 border text-center whitespace-nowrap">{{ p.rank || (idx + 1) }}</td>
          <td class="p-2 border text-center whitespace-nowrap">{{ p.uid }}</td>
          <td class="p-2 border whitespace-nowrap">{{ p.name }}</td>
          <td class="p-2 border text-center whitespace-nowrap">
            {{ typeof p.pt === 'number' ? p.pt.toLocaleString() : p.pt }}
          </td>
          <td class="p-2 border text-center whitespace-nowrap">
            {{ idx > 0 && typeof (players[idx - 1].pt - p.pt) === 'number'
                ? (players[idx - 1].pt - p.pt).toLocaleString()
                : '-' }}
          </td>
          <td class="p-2 border text-center whitespace-nowrap">
            {{ typeof p.speed_last_hour === 'number' ? p.speed_last_hour.toLocaleString() : p.speed_last_hour }}
          </td>
          <td class="p-2 border text-center whitespace-nowrap">
            {{ p.speed_rank }}
          </td>
          <td class="p-2 border whitespace-nowrap">
            {{ p.signature }}
          </td>
          <td class="p-2 border text-center whitespace-nowrap">
            {{ formatTs(p.score_updated_at) }}
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { formatTs } from '../utils.js';

defineProps({
  players: Array
})
</script>
