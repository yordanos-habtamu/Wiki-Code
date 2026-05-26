<template>
  <div class="min-h-screen bg-gray-950">
    <NuxtPage />
  </div>
</template>

<script setup lang="ts">
// Root application component - handles global initialization
// Pages are auto-routed by Nuxt based on pages/ directory structure
// Note: Authentication is handled by individual pages, not here
</script>

<style>
/* Global styles - Dark theme defaults */
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  background-color: #030712; /* bg-gray-950 */
  color: #f9fafb; /* text-gray-50 */
}

/* Custom scrollbar for dark theme */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: #111827; /* bg-gray-900 */
}

::-webkit-scrollbar-thumb {
  background: #374151; /* bg-gray-700 */
  border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
  background: #4b5563; /* bg-gray-600 */
}
</style>
