<template>
  <div class="relative shadow-md rounded-md">
    <input 
      :value="modelValue"
      @input="$emit('update:modelValue', $event.target.value)"
      @keyup.enter="performSearch" 
      class="w-full p-3 pr-24 rounded-md border-gray-300 focus:ring-indigo-500 focus:border-indigo-500 transition"
      placeholder="输入玩家 UID" 
    />
    <button 
      @click="performSearch" 
      class="absolute inset-y-0 right-0 px-5 m-1 rounded-md bg-indigo-600 text-white font-semibold hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition-colors duration-200"
    >
      查询
    </button>
  </div>
</template>

<script setup>
// Support v-model
defineProps(['modelValue']);
const emit = defineEmits(['update:modelValue', 'search']);

const performSearch = () => {
  // Emit search event without payload, parent has the value via v-model
  emit('search');
};
</script>
