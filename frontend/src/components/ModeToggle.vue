<template>
  <!-- 活动榜 / 月榜 切换（MD3 分段按钮） -->
  <div class="md-segmented" role="tablist">
    <button
      v-for="opt in options"
      :key="opt.value"
      type="button"
      role="tab"
      :aria-selected="modelValue === opt.value"
      class="md-segmented-btn"
      :class="{ 'is-active': modelValue === opt.value }"
      @click="select(opt.value)"
    >
      {{ opt.label }}
    </button>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from '../i18n.js'

const { t } = useI18n()

const props = defineProps({
  modelValue: { type: String, default: 'event' },   // 'event' | 'monthly'
})

const emit = defineEmits(['update:modelValue'])

const options = computed(() => [
  { value: 'event', label: t('mode.event') },
  { value: 'monthly', label: t('mode.monthly') },
])

function select(value) {
  if (value !== props.modelValue) {
    emit('update:modelValue', value)
  }
}
</script>

<style scoped>
.md-segmented {
  display: inline-flex;
  padding: 3px;
  border-radius: 9999px;
  background-color: var(--md-sys-color-surface-container-high);
  gap: 2px;
  flex-shrink: 0;
}

.md-segmented-btn {
  padding: 0.375rem 0.9rem;
  border-radius: 9999px;
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--md-sys-color-on-surface-variant);
  transition: background-color 0.15s ease, color 0.15s ease;
  white-space: nowrap;
}

.md-segmented-btn:hover {
  background-color: color-mix(in srgb, var(--md-sys-color-on-surface) 8%, transparent);
}

.md-segmented-btn.is-active {
  background-color: var(--md-sys-color-primary);
  color: var(--md-sys-color-on-primary);
  box-shadow: var(--md-elevation-1);
}
</style>
