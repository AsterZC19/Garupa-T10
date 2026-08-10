<template>
  <div class="flex items-center gap-2">
    <MdSelect
      :options="selectOptions"
      v-model="value"
      class="w-full max-w-[300px] sm:max-w-sm"
      placeholder="选择活动"
    />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import MdSelect from './MdSelect.vue'
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

const selectOptions = computed(() =>
  (props.events || []).map(e => ({
    value: e.event_id,
    label: `${e.event_id} - ${e.name} (${formatTs(e.start_at)})`,
  }))
)
</script>
