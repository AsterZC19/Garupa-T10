<template>
  <div class="flex items-center gap-2">
    <select v-model="value" class="px-3 py-1 border rounded">
      <option v-for="e in events" :key="e.event_id" :value="e.event_id">
        {{ e.event_id }} - {{ e.name }} ({{ formatTs(e.start_at) }})
      </option>
    </select>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { formatTs } from '../utils.js'

const props = defineProps({
  events: Array,
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