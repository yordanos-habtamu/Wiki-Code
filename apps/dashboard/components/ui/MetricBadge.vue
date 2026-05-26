<template>
  <span :class="[baseClasses, variantClasses, sizeClasses]">
    {{ label }}
  </span>
</template>

<script setup lang="ts">
const props = defineProps<{
  label: string
  variant: 'critical' | 'high' | 'medium' | 'low' | 'isolated'
  size?: 'sm' | 'md'
}>()

const baseClasses = 'inline-flex items-center rounded-full font-medium border'

const variantClasses = computed(() => {
  const variants = {
    critical: 'bg-error/10 text-error border-error/20',
    high: 'bg-warning/10 text-warning border-warning/20',
    medium: 'bg-info/10 text-info border-info/20',
    low: 'bg-success/10 text-success border-success/20',
    isolated: 'bg-success/10 text-success border-success/20'
  }
  return variants[props.variant]
})

const sizeClasses = computed(() => {
  return props.size === 'sm' 
    ? 'px-2 py-0.5 text-xs' 
    : 'px-3 py-1 text-sm'
})
</script>
