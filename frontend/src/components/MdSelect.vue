<template>
  <div ref="wrap" class="md-select-wrap relative">
    <!-- 触发器 -->
    <button
      type="button"
      class="md-select-trigger"
      :class="{ 'is-open': open }"
      @click="toggle"
      @keydown.down.prevent="focusNext(1)"
      @keydown.up.prevent="focusNext(-1)"
      aria-haspopup="listbox"
      :aria-expanded="open"
    >
      <span class="truncate">{{ selectedLabel }}</span>
      <svg
        class="md-select-chevron flex-shrink-0"
        :class="{ 'rotate-180': open }"
        xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
        stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
      >
        <path d="M6 9l6 6 6-6" />
      </svg>
    </button>

    <!-- 下拉菜单 -->
    <transition name="md-pop">
      <div v-if="open" class="md-select-menu" role="listbox">
        <button
          v-for="opt in options"
          :key="opt.value"
          type="button"
          role="option"
          :aria-selected="opt.value === modelValue"
          class="md-select-item"
          :class="{ 'is-selected': opt.value === modelValue }"
          @click="select(opt)"
          @mouseenter="focusIndex = -1"
        >
          <span class="truncate">{{ opt.label }}</span>
          <svg
            v-if="opt.value === modelValue"
            class="md-select-check flex-shrink-0"
            xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"
          >
            <path d="M20 6L9 17l-5-5" />
          </svg>
        </button>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps({
  options: { type: Array, default: () => [] },   // [{ value, label }]
  modelValue: [String, Number],
  placeholder: { type: String, default: '请选择' },
})

const emit = defineEmits(['update:modelValue'])

const wrap = ref(null)
const open = ref(false)
const focusIndex = ref(-1)

const selectedLabel = computed(() => {
  const hit = props.options.find(opt => opt.value === props.modelValue)
  return hit ? hit.label : props.placeholder
})

function toggle() {
  open.value = !open.value
}

function select(opt) {
  emit('update:modelValue', opt.value)
  open.value = false
}

function focusNext(dir) {
  if (!open.value) {
    open.value = true
    return
  }
  const menu = wrap.value?.querySelector('.md-select-menu')
  if (!menu) return
  const items = [...menu.querySelectorAll('.md-select-item')]
  focusIndex.value = (focusIndex.value + dir + items.length) % items.length
  items[focusIndex.value]?.focus()
}

function onDocumentClick(e) {
  if (open.value && wrap.value && !wrap.value.contains(e.target)) {
    open.value = false
  }
}

function onKeydown(e) {
  if (e.key === 'Escape' && open.value) {
    open.value = false
    wrap.value?.querySelector('.md-select-trigger')?.focus()
  }
}

onMounted(() => {
  document.addEventListener('click', onDocumentClick)
  document.addEventListener('keydown', onKeydown)
})
onBeforeUnmount(() => {
  document.removeEventListener('click', onDocumentClick)
  document.removeEventListener('keydown', onKeydown)
})
</script>

<style scoped>
.md-select-trigger {
  width: 100%;
  height: 2.5rem;
  padding: 0 0.9rem 0 1rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  background-color: var(--md-sys-color-surface-container-low);
  color: var(--md-sys-color-on-surface);
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: 10px;
  font-size: 0.875rem;
  text-align: left;
  transition: border-color 0.15s ease, background-color 0.15s ease, box-shadow 0.15s ease;
}
.md-select-trigger:hover {
  background-color: var(--md-sys-color-surface-container-high);
}
.md-select-trigger.is-open {
  border-color: var(--md-sys-color-primary);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--md-sys-color-primary) 18%, transparent);
}

.md-select-chevron {
  width: 18px;
  height: 18px;
  color: var(--md-sys-color-on-surface-variant);
  transition: transform 0.2s ease;
}

.md-select-menu {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  right: 0;
  z-index: 50;
  background-color: var(--md-sys-color-surface-container-lowest);
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: 12px;
  box-shadow: var(--md-elevation-2);
  max-height: 18rem;
  overflow-y: auto;
  padding: 6px;
}

.md-select-item {
  width: 100%;
  padding: 0.6rem 0.85rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  border-radius: 8px;
  font-size: 0.85rem;
  color: var(--md-sys-color-on-surface);
  text-align: left;
  transition: background-color 0.12s ease;
}
.md-select-item:hover,
.md-select-item:focus-visible {
  background-color: var(--md-sys-color-surface-container-high);
  outline: none;
}
.md-select-item.is-selected {
  color: var(--md-sys-color-primary);
  font-weight: 600;
}

.md-select-check {
  width: 16px;
  height: 16px;
}

/* 弹出动画 */
.md-pop-enter-active,
.md-pop-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
  transform-origin: top;
}
.md-pop-enter-from,
.md-pop-leave-to {
  opacity: 0;
  transform: scaleY(0.96) translateY(-4px);
}
</style>
