<template>
  <div id="app-container" class="flex min-h-screen bg-gray-50">
    <Sidebar :is-open="sidebarOpen" @close="sidebarOpen = false" />

    <!-- Mobile Overlay -->
    <div 
      v-if="sidebarOpen" 
      @click="sidebarOpen = false" 
      class="fixed inset-0 bg-black opacity-50 z-30 sm:hidden"
    ></div>

    <!-- Sidebar Toggle Button -->
    <button 
      @click="sidebarOpen = !sidebarOpen"
      class="fixed top-4 p-2 rounded-md text-gray-600 bg-white shadow-md hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-indigo-500 z-50 transition-all duration-300"
      :class="sidebarOpen ? 'left-60' : 'left-4'"
    >

      <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
      </svg>
    </button>

    <div class="flex-1 flex flex-col transition-all duration-300 min-w-0" :class="{'ml-0 sm:ml-56': sidebarOpen}">
      <header class="sticky top-0 bg-white/80 backdrop-blur-lg shadow-sm z-30">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div class="flex items-center justify-between h-16">
            <div class="flex items-center pl-16">

              <!-- 标题 -->
              <router-link to="/" class="ml-4">
                <h1 class="text-xl font-semibold text-gray-800 hover:text-indigo-500 transition-colors">
                  日服 T10 追踪
                </h1>
              </router-link>
            </div>
          </div>
        </div>
      </header>
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
