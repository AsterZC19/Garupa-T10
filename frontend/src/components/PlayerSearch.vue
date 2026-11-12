<template>
  <div class="relative">
    <input
      :value="modelValue"
      @input="$emit('update:modelValue', $event.target.value)"
      @keyup.enter="performSearch"
      class="w-full p-3 pr-24 rounded-full border-2 bg-md-surface text-md-on-surface placeholder:text-md-on-surface-variant border-md-outline-variant focus:border-md-primary focus:outline-none transition-colors"
      :placeholder="t('player.inputPlaceholder')"
    />
    <button
      @click="performSearch"
      class="absolute inset-y-1.5 right-1.5 px-5 rounded-full bg-md-primary text-md-on-primary font-semibold hover:brightness-105 transition focus:outline-none"
    >
      {{ t('player.searchBtn') }}
    </button>
  </div>
</template>

<script setup>
import { useI18n } from '../i18n.js';

const { t } = useI18n();

// Support v-model
defineProps(['modelValue']);
const emit = defineEmits(['update:modelValue', 'search']);

const performSearch = () => {
  // Emit search event without payload, parent has the value via v-model
  emit('search');
};
</script>
