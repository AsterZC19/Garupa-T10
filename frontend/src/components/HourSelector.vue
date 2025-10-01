<template>
  <div class="flex items-center gap-2">
    <select v-model="value" class="px-3 py-1 border rounded">
      <option v-for="h in hours" :key="h.value" :value="h.value">
        {{ h.label }}
      </option>
    </select>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  hours: Array,
  modelValue: [String, Number]
})

const emit = defineEmits(['update:modelValue'])

const value = computed({
  get() {
    return props.modelValue
  },
  set(value) {
    emit('update:modelValue', value)
  }
})
</script>