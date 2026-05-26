<template>
  <div class="flex min-h-screen">
    <!-- Sidebar Navigation -->
    <aside class="w-64 bg-white border-r border-gray-200 fixed h-full">
      <div class="p-6">
        <h1 class="text-2xl font-bold text-gray-900">WikiHub</h1>
        <p class="text-sm text-gray-500 mt-1">Code Intelligence Engine</p>
      </div>
      
      <nav class="mt-6">
        <NuxtLink 
          to="/" 
          class="flex items-center px-6 py-3 text-gray-700 hover:bg-gray-100 transition-colors"
          :class="{ 'bg-gray-100 border-r-4 border-primary-600': route.path === '/' }"
        >
          <svg class="w-5 h-5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
          </svg>
          Dashboard
        </NuxtLink>
        
        <NuxtLink 
          to="/analytics" 
          class="flex items-center px-6 py-3 text-gray-700 hover:bg-gray-100 transition-colors"
          :class="{ 'bg-gray-100 border-r-4 border-primary-600': route.path === '/analytics' }"
        >
          <svg class="w-5 h-5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          Token Analytics
        </NuxtLink>
        
        <NuxtLink 
          to="/quality" 
          class="flex items-center px-6 py-3 text-gray-700 hover:bg-gray-100 transition-colors"
          :class="{ 'bg-gray-100 border-r-4 border-primary-600': route.path === '/quality' }"
        >
          <svg class="w-5 h-5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Code Quality
        </NuxtLink>
      </nav>
      
      <!-- System Status -->
      <div class="absolute bottom-0 left-0 right-0 p-6 border-t border-gray-200">
        <div class="flex items-center text-sm">
          <div class="w-2 h-2 rounded-full bg-green-500 mr-2"></div>
          <span class="text-gray-600">MCP Server: Connected</span>
        </div>
        <div class="text-xs text-gray-500 mt-2">
          Indexed: {{ stats.files }} files, {{ stats.dependencies }} dependencies
        </div>
      </div>
    </aside>
    
    <!-- Main Content -->
    <main class="flex-1 ml-64">
      <slot />
    </main>
  </div>
</template>

<script setup lang="ts">
const route = useRoute()

// System stats (will be fetched from API)
const stats = ref({
  files: 4,
  dependencies: 10,
  lastIndexed: new Date().toISOString()
})
</script>
