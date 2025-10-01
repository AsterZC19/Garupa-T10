<template>
  <div class="p-4">
    <h1 class="text-2xl font-bold mb-4">玩家查询</h1>
    <div class="flex gap-2">
      <input v-model="uid" @keyup.enter="search" class="border p-2 rounded w-full" placeholder="输入玩家 UID" />
      <button @click="search" class="bg-blue-500 text-white px-4 py-2 rounded">查询</button>
    </div>
    <div v-if="searchedUid" class="mt-4">
      <h2 class="text-xl">查询的UID: {{ searchedUid }}</h2>
      <p>(这里将来会显示玩家的数据)</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';

const uid = ref('');
const searchedUid = ref('');
const router = useRouter();
const route = useRoute();

const search = () => {
  if (uid.value) {
    router.push({ path: `/player/${uid.value}` });
  }
};

onMounted(() => {
  if (route.params.uid) {
    uid.value = route.params.uid;
    searchedUid.value = route.params.uid;
  }
});

watch(() => route.params.uid, (newUid) => {
  if (newUid) {
    uid.value = newUid;
    searchedUid.value = newUid;
  } else {
    uid.value = '';
    searchedUid.value = '';
  }
});
</script>
