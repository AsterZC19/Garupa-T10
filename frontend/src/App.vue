<template>
  <div id="app-container" class="flex min-h-screen md-surface-container">
    <!-- MD3 导航抽屉 -->
    <Sidebar :is-open="sidebarOpen" @close="sidebarOpen = false" />

    <!-- 移动端遮罩 -->
    <div
      v-if="sidebarOpen"
      @click="sidebarOpen = false"
      class="fixed inset-0 bg-black opacity-40 z-30 sm:hidden"
    ></div>

    <div
      class="flex-1 flex flex-col transition-all duration-300 min-w-0"
      :class="{ 'sm:ml-60': sidebarOpen }"
    >
      <!-- 顶栏（Top App Bar） -->
      <header class="sticky top-0 z-20 md-surface shadow-md-elevation-1">
        <div class="mx-auto px-3 sm:px-6">
          <div class="flex items-center h-16">
            <!-- 汉堡按钮 -->
            <button
              @click="sidebarOpen = !sidebarOpen"
              :aria-label="t('app.toggleNav')"
              class="md-icon-button focus:outline-none"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>

            <!-- 标题 -->
            <router-link to="/" class="ml-2 sm:ml-4 flex items-center gap-2 group">
              <h1 class="text-lg sm:text-xl font-semibold text-md-on-surface group-hover:text-md-primary transition-colors">
                {{ t('app.title') }}
              </h1>
            </router-link>

            <!-- 顶栏右侧：语言切换 + 日/夜间模式切换 -->
            <div class="ml-auto flex items-center gap-1">
              <LanguageSwitcher />
              <ThemeToggle />
            </div>
          </div>
        </div>
      </header>

      <!-- 页面内容 -->
      <main class="flex-1">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import Sidebar from './components/Sidebar.vue';
import ThemeToggle from './components/ThemeToggle.vue';
import LanguageSwitcher from './components/LanguageSwitcher.vue';
import { useI18n } from './i18n.js';

const { t } = useI18n();
const sidebarOpen = ref(false);
</script>

<style>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
