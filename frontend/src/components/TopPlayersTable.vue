<template>
  <div class="overflow-x-auto">
    <table class="min-w-full bg-white border text-sm">
      <thead>
        <tr>
          <th class="p-2 border whitespace-nowrap">位次</th>
          <th class="p-2 border whitespace-nowrap">UID</th>
          <th class="p-2 border whitespace-nowrap">名字</th>
          <th class="p-2 border whitespace-nowrap">当前PT</th>
          <th class="p-2 border whitespace-nowrap">当前分差</th>
          <th class="p-2 border whitespace-nowrap">上一整点时速</th>
          <th class="p-2 border whitespace-nowrap">时速排名</th>
          <th class="p-2 border whitespace-nowrap">周回次数</th>
          <th class="p-2 border whitespace-nowrap">平均PT</th>
          <th class="p-2 border whitespace-nowrap">签名</th>
          <th class="p-2 border whitespace-nowrap">当前更新时间</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(p, idx) in players" :key="p.uid">
          <td class="p-2 border text-center whitespace-nowrap">{{ p.rank || (idx + 1) }}</td>
          <td class="p-2 border text-center whitespace-nowrap">
            <router-link
              v-if="p.uid"
              :to="`/player/${p.uid}`"
              class="text-[#9999FF] hover:underline"
            >
              {{ p.uid }}
            </router-link>
            <span v-else>-</span>
          </td>

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
            {{ typeof p.hourly_speed === 'number' ? p.hourly_speed.toLocaleString() : p.hourly_speed }}
          </td>
          <td class="p-2 border text-center whitespace-nowrap">
            {{ p.hourly_speed > 0 ? p.speed_rank : '-' }}
          </td>
          <td class="p-2 border text-center whitespace-nowrap">
            {{ p.run_count }}
          </td>
          <td class="p-2 border text-center whitespace-nowrap">
            {{ p.average_pt }}
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
