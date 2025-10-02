<template>
  <aside class="bg-gray-800 text-white w-56 min-h-screen p-4 fixed top-0 left-0 h-full z-40 transform transition-transform" :class="{'-translate-x-full': !isOpen}">
    <!-- <h2 class="text-xl font-bold mb-4">导航</h2> -->
    <nav>
      <ul>
        <li><router-link to="/" @click="close" class="block py-2 px-4 rounded hover:bg-gray-700">活动</router-link></li>
        <li><router-link to="/player" @click="close" class="block py-2 px-4 rounded hover:bg-gray-700">玩家查询</router-link></li>
      </ul>
    </nav>
  </aside>
</template>

<script setup>
const props = defineProps({
  isOpen: Boolean
});

const emit = defineEmits(['close']);

const close = () => {
  emit('close');
}
</script>
