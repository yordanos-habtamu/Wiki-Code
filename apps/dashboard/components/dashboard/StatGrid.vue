<template>
  <div class="grid grid-cols-3 gap-3">
    <div class="bg-gradient-to-b from-gray-900 to-gray-950 border border-gray-800 rounded-xl p-4 hover:border-blue-500/20 transition-colors">
      <div class="flex items-center justify-between mb-2">
        <span class="text-xs font-medium text-gray-400 uppercase tracking-wider">Files</span>
        <span class="text-xs text-gray-500">SCANNED</span>
      </div>
      <div class="text-2xl font-bold text-gray-100">{{ stats.files || '—' }}</div>
    </div>

    <div class="bg-gradient-to-b from-gray-900 to-gray-950 border border-gray-800 rounded-xl p-4 hover:border-blue-500/20 transition-colors">
      <div class="flex items-center justify-between mb-2">
        <span class="text-xs font-medium text-gray-400 uppercase tracking-wider">Dependencies</span>
        <span class="text-xs text-gray-500">MAPPED</span>
      </div>
      <div class="text-2xl font-bold text-gray-100">{{ stats.deps || '—' }}</div>
    </div>

    <div class="bg-gradient-to-b from-gray-900 to-gray-950 border border-gray-800 rounded-xl p-4 hover:border-blue-500/20 transition-colors">
      <div class="flex items-center justify-between mb-2">
        <span class="text-xs font-medium text-gray-400 uppercase tracking-wider">Languages</span>
        <span class="text-xs text-gray-500">DETECTED</span>
      </div>
      <div class="text-2xl font-bold text-gray-100">{{ stats.languages || '—' }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  stats: {
    files: number
    deps: number
    languages: number
    symbols: number
  }
}>()
</script>
