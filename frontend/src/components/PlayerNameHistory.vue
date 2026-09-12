<template>
  <button
    ref="trigger"
    type="button"
    title="曾用名"
    aria-label="查看曾用名"
    aria-haspopup="dialog"
    :aria-expanded="isOpen"
    :aria-controls="popupId"
    class="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-md-on-surface-variant hover:bg-md-surface-container-high hover:text-md-primary transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-md-primary"
    @click="toggle"
  >
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" class="h-4 w-4">
      <path d="M3 11a9 9 0 1 1 2.6 7M3 5v6h6" stroke-linecap="round" stroke-linejoin="round" />
      <path d="M12 7v5l3 2" stroke-linecap="round" stroke-linejoin="round" />
    </svg>
  </button>
  <div
    :id="popupId"
    ref="popup"
    popover="auto"
    role="dialog"
    :aria-labelledby="popupId + '-title'"
    :style="position"
    class="fixed m-0 box-border rounded-2xl border border-md-outline-variant bg-md-surface-container-high p-3 text-left text-md-on-surface shadow-xl"
    @toggle="isOpen = $event.newState === 'open'"
  >
    <div class="flex items-center justify-between gap-3 mb-2">
      <h3 :id="popupId + '-title'" class="text-xs font-semibold">曾用名</h3>
      <button type="button" aria-label="关闭曾用名" class="flex h-6 w-6 items-center justify-center rounded-full text-md-on-surface-variant hover:bg-md-surface-container-highest focus-visible:outline focus-visible:outline-md-primary" @click="close">
        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" class="h-3.5 w-3.5"><path d="m6 6 12 12M18 6 6 18" stroke-linecap="round" /></svg>
      </button>
    </div>
    <p class="mb-2 text-[10px] leading-4 text-md-on-surface-variant">最后记录时间 · 本地时间</p>
    <ul v-if="entries?.length" class="max-h-48 overflow-y-auto overscroll-contain divide-y divide-md-outline-variant">
      <li v-for="entry in entries" :key="entry.name" class="py-2 first:pt-0 last:pb-0">
        <p class="whitespace-pre-wrap break-all text-xs leading-4">{{ entry.name }}</p>
        <time :datetime="new Date(entry.last_seen).toISOString()" class="mt-0.5 block text-[10px] leading-4 tabular-nums text-md-on-surface-variant">{{ new Date(entry.last_seen).toLocaleString('zh-CN', { hour12: false }) }}</time>
      </li>
    </ul>
    <p v-else class="text-xs text-md-on-surface-variant">暂无用户名记录。</p>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';

const props = defineProps(['uid', 'entries']);
const popupId = computed(() => 'player-name-history-' + props.uid);
const trigger = ref(null);
const popup = ref(null);
const isOpen = ref(false);
const position = ref({});

function close() {
  popup.value?.hidePopover();
}

function toggle() {
  if (popup.value.matches(':popover-open')) {
    close();
    return;
  }
  const anchor = trigger.value.getBoundingClientRect();
  const width = Math.min(280, window.innerWidth - 32);
  position.value = {
    width: width + 'px',
    left: Math.max(16, Math.min(anchor.right - width, window.innerWidth - width - 16)) + 'px',
    top: Math.max(16, Math.min(anchor.bottom + 8, window.innerHeight - 296)) + 'px',
    maxHeight: 'calc(100dvh - 32px)',
    overflowY: 'auto',
  };
  popup.value.showPopover();
}

onMounted(() => {
  window.addEventListener('resize', close);
  window.addEventListener('scroll', close);
});
onBeforeUnmount(() => {
  window.removeEventListener('resize', close);
  window.removeEventListener('scroll', close);
});
</script>
