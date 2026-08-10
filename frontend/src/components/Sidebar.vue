<template>
  <!-- MD3 导航抽屉（Modal navigation drawer） -->
  <aside
    class="md-surface w-60 min-h-full p-3 fixed top-0 left-0 h-full z-40 transform transition-transform"
    :class="{ '-translate-x-full': !isOpen }"
  >
    <!-- 抽屉头部 -->
    <div class="flex items-center gap-3 px-4 h-16 mb-2">
      <span class="flex items-center justify-center h-9 w-9 rounded-full bg-md-primary-container text-md-on-primary-container text-lg">🎵</span>
      <div class="leading-tight">
        <div class="font-semibold text-md-on-surface text-sm">Garupa T10</div>
        <div class="text-xs text-md-on-surface-variant">日服 T10 追踪</div>
      </div>
    </div>

    <nav>
      <ul class="space-y-1">
        <li>
          <router-link to="/" @click="close" class="md-nav-item">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M3 12l9-9 9 9M5 10v10a1 1 0 001 1h3a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1h3a1 1 0 001-1V10" />
            </svg>
            活动
          </router-link>
        </li>
        <li>
          <router-link to="/player" @click="close" class="md-nav-item">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
            玩家查询
          </router-link>
        </li>
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
