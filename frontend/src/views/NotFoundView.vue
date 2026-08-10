<template>
  <div class="p-4 sm:p-6 max-w-7xl mx-auto">
    <div class="md-elevated-card p-12 sm:p-16 text-center">
      <div class="text-6xl sm:text-7xl font-bold mb-4 bg-clip-text text-transparent bg-gradient-to-r from-sky-400 to-pink-400">
        404
      </div>
      <h1 class="text-2xl font-bold mb-2">页面不存在</h1>
      <p class="text-sm text-md-on-surface-variant mb-8">
        你要访问的活动不存在，可能已被删除，或链接有误
      </p>
      <router-link to="/" class="md-filled-button no-underline">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M3 12l9-9 9 9M5 10v10a1 1 0 001 1h3a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1h3a1 1 0 001-1V10" />
        </svg>
        返回首页
      </router-link>
    </div>
  </div>
</template>
