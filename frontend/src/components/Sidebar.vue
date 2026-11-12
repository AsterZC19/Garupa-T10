<template>
  <!-- MD3 导航抽屉（Modal navigation drawer） -->
  <aside
    class="md-surface w-60 min-h-full p-3 fixed top-0 left-0 h-full z-40 transform transition-transform"
    :class="{ '-translate-x-full': !isOpen }"
  >
    <!-- 抽屉头部 -->
    <div class="flex items-center gap-3 px-4 h-16 mb-2">
      <div class="leading-tight">
        <div class="font-semibold text-md-on-surface text-sm">Garupa T10</div>
        <div class="text-xs text-md-on-surface-variant">{{ t('app.title') }}</div>
      </div>
    </div>

    <nav>
      <ul class="space-y-1">
        <li>
          <router-link to="/" @click="close" class="md-nav-item">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M3 12l9-9 9 9M5 10v10a1 1 0 001 1h3a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1h3a1 1 0 001-1V10" />
            </svg>
            {{ t('nav.events') }}
          </router-link>
        </li>
        <li>
          <router-link to="/monthly" @click="close" class="md-nav-item">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            {{ t('nav.monthly') }}
          </router-link>
        </li>
        <li>
          <router-link to="/player" @click="close" class="md-nav-item">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
            {{ t('nav.playerSearch') }}
          </router-link>
        </li>
      </ul>
    </nav>
  </aside>
</template>

<script setup>
import { useI18n } from '../i18n.js';

const { t } = useI18n();

const props = defineProps({
  isOpen: Boolean
});

const emit = defineEmits(['close']);

const close = () => {
  emit('close');
}
</script>
