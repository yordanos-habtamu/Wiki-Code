<template>
  <div class="space-y-1.5">
    <label v-if="label" class="block text-sm font-medium text-gray-300">{{ label }}</label>
    <div class="relative">
      <input
        :type="inputType"
        :value="modelValue"
        @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
        class="w-full rounded-lg bg-gray-950 border border-gray-800 text-white px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-500/50 focus:border-blue-500 transition-colors"
        :class="{ 'border-error/50': error }"
        :placeholder="placeholder"
      />
      <button 
        v-if="type === 'password'"
        @click="showPassword = !showPassword"
        class="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
        type="button"
      >
        {{ showPassword ? '👁️' : '🕶️' }}
      </button>
    </div>
    <p v-if="error" class="text-xs text-error">{{ error }}</p>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  modelValue: string
  type?: 'text' | 'password'
  label?: string
  placeholder?: string
  error?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const showPassword = ref(false)
const inputType = computed(() => {
  if (props.type === 'password' && showPassword.value) return 'text'
  return props.type || 'text'
})
</script>
