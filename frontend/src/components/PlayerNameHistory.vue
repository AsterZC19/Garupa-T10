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
    class="fixed m-0 box-border rounded-2xl border border-md-outline-variant bg-md-surface-container-high p-4 sm:p-5 text-left text-md-on-surface shadow-xl"
    @toggle="isOpen = $event.newState === 'open'"
  >
    <div class="flex items-center justify-between gap-3 mb-2">
      <h3 :id="popupId + '-title'" class="text-xs font-semibold">曾用名</h3>
      <button type="button" aria-label="关闭曾用名" class="flex h-6 w-6 items-center justify-center rounded-full text-md-on-surface-variant hover:bg-md-surface-container-highest focus-visible:outline focus-visible:outline-md-primary" @click="close">
        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" class="h-3.5 w-3.5"><path d="m6 6 12 12M18 6 6 18" stroke-linecap="round" /></svg>
      </button>
    </div>
    <ul v-if="entries?.length" class="max-h-[min(20rem,calc(100dvh-10rem))] overflow-y-auto overscroll-contain divide-y divide-md-outline-variant">
      <li v-for="entry in entries" :key="entry.id" class="py-2 first:pt-0 last:pb-0">
        <p class="whitespace-pre-wrap break-all text-xs leading-4">{{ entry.name }}</p>
        <time v-if="entry.first_seen != null" :datetime="new Date(entry.first_seen).toISOString()" class="mt-0.5 block text-[10px] leading-4 tabular-nums text-md-on-surface-variant">{{ new Date(entry.first_seen).toLocaleString('zh-CN', { hour12: false }) }}</time>
        <span v-else class="mt-0.5 block text-[10px] leading-4 text-md-on-surface-variant">首次发现时间未知</span>
      </li>
    </ul>
    <p v-else class="text-xs text-md-on-surface-variant">暂无用户名记录。</p>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onBeforeUnmount } from 'vue';

const props = defineProps(['uid', 'entries', 'anchor']);
const popupId = computed(() => 'player-name-history-' + props.uid);
const trigger = ref(null);
const popup = ref(null);
const isOpen = ref(false);
const position = ref({});

function close() {
  popup.value?.hidePopover();
}

async function updatePosition() {
  const anchor = (props.anchor || trigger.value).getBoundingClientRect();
  const width = Math.min(360, window.innerWidth - 32);
  position.value = {
    width: width + 'px',
    left: Math.max(16, Math.min(anchor.left + (anchor.width - width) / 2, window.innerWidth - width - 16)) + 'px',
    top: '16px',
    maxHeight: 'calc(100dvh - 32px)',
    overflowY: 'auto',
  };
  await nextTick();
  const height = popup.value?.getBoundingClientRect().height || 0;
  const below = anchor.bottom + 8;
  const above = anchor.top - height - 8;
  position.value.top = Math.max(16, Math.min(
    below + height <= window.innerHeight - 16 ? below : above,
    window.innerHeight - height - 16,
  )) + 'px';
}

async function toggle() {
  if (popup.value.matches(':popover-open')) {
    close();
    return;
  }
  popup.value.showPopover();
  await updatePosition();
}

function handleResize() {
  if (popup.value?.matches(':popover-open')) updatePosition();
}

onMounted(() => {
  window.addEventListener('resize', handleResize);
  window.addEventListener('scroll', close);
});
onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize);
  window.removeEventListener('scroll', close);
});
</script>
