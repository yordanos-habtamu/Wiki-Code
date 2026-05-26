<template>
  <div class="relative w-full">
    <!-- Loading State -->
    <div v-if="loading" class="flex items-center justify-center h-96 bg-gray-900 border border-gray-800 rounded-xl">
      <div class="text-center">
        <div class="text-4xl mb-2">🌐</div>
        <div class="text-gray-400">Initializing topology graph...</div>
      </div>
    </div>

    <!-- Canvas Container -->
    <div 
      v-show="!loading"
      ref="canvasContainer"
      class="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden"
      :style="{ height: canvasHeight + 'px' }"
    >
      <slot :dimensions="canvasDimensions"></slot>
    </div>
  </div>
</template>

<script setup lang="ts">
const canvasContainer = ref<HTMLElement | null>(null)
const loading = ref(true)
const canvasHeight = ref(500)
const canvasDimensions = reactive({ width: 800, height: 500 })
const resizeObserver = ref<ResizeObserver | null>(null)

function updateDimensions() {
  if (!canvasContainer.value) return
  const rect = canvasContainer.value.getBoundingClientRect()
  canvasDimensions.width = rect.width
  canvasDimensions.height = canvasHeight.value
  loading.value = false
}

// Update dimensions on mount and resize
onMounted(() => {
  // Try to capture initial DOM size immediately
  updateDimensions()

  // Observe container resize for accurate dimension changes
  if (window.ResizeObserver && canvasContainer.value) {
    resizeObserver.value = new ResizeObserver(() => {
      updateDimensions()
    })
    resizeObserver.value.observe(canvasContainer.value)
  }

  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  if (resizeObserver.value && canvasContainer.value) {
    resizeObserver.value.unobserve(canvasContainer.value)
    resizeObserver.value.disconnect()
  }
})

function handleResize() {
  updateDimensions()
}
</script>
