<template>
  <div ref="wrap" class="relative">
    <button
      type="button"
      @click="toggle"
      :title="t('lang.switchLabel')"
      :aria-label="t('lang.switchLabel')"
      aria-haspopup="listbox"
      :aria-expanded="open"
      class="inline-flex items-center gap-1.5 h-9 px-2.5 rounded-full text-xs font-medium text-md-on-surface-variant hover:bg-md-surface-container-high hover:text-md-on-surface transition-colors focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-md-primary"
    >
      <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 21a9 9 0 100-18 9 9 0 000 18z" />
        <path stroke-linecap="round" stroke-linejoin="round" d="M3.6 9h16.8M3.6 15h16.8M12 3a14.5 14.5 0 010 18M12 3a14.5 14.5 0 000 18" />
      </svg>
      <span>{{ currentShort }}</span>
      <svg
        class="h-3.5 w-3.5 transition-transform duration-200"
        :class="{ 'rotate-180': open }"
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <path d="M6 9l6 6 6-6" />
      </svg>
    </button>

    <transition name="lang-pop">
      <div
        v-if="open"
        role="listbox"
        class="lang-menu absolute right-0 mt-1.5 w-36 rounded-xl border border-md-outline-variant p-1.5 z-50"
      >
        <button
          v-for="opt in LOCALE_OPTIONS"
          :key="opt.value"
          type="button"
          role="option"
          :aria-selected="locale === opt.value"
          @click="selectLocale(opt.value)"
          class="w-full px-2.5 py-2 rounded-lg text-xs flex items-center justify-between gap-2 transition-colors text-left hover:bg-md-surface-container-high focus:outline-none"
          :class="locale === opt.value ? 'text-md-primary font-semibold' : 'text-md-on-surface'"
        >
          <span>{{ opt.label }}</span>
          <svg
            v-if="locale === opt.value"
            class="h-3.5 w-3.5 flex-shrink-0"
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2.5"
            stroke-linecap="round"
            stroke-linejoin="round"
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
import { useI18n } from '../i18n.js'

const { locale, LOCALE_OPTIONS, setLocale, t } = useI18n()

const wrap = ref(null)
const open = ref(false)

const currentShort = computed(() => {
  const hit = LOCALE_OPTIONS.find(opt => opt.value === locale.value)
  return hit ? hit.short : '简中'
})

function toggle() {
  open.value = !open.value
}

function selectLocale(val) {
  setLocale(val)
  open.value = false
}

function onDocumentClick(e) {
  if (open.value && wrap.value && !wrap.value.contains(e.target)) {
    open.value = false
  }
}

function onKeydown(e) {
  if (e.key === 'Escape' && open.value) {
    open.value = false
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
.lang-menu {
  background-color: var(--md-sys-color-surface-container-lowest);
  box-shadow: var(--md-elevation-2);
}

.lang-pop-enter-active,
.lang-pop-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
  transform-origin: top right;
}

.lang-pop-enter-from,
.lang-pop-leave-to {
  opacity: 0;
  transform: scaleY(0.95) translateY(-4px);
}
</style>
