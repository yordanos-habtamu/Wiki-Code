<template>
  <div class="space-y-3">
    <!-- Table Header -->
    <div class="flex items-center justify-between text-xs text-gray-500 px-3">
      <span>Code Quality Analysis</span>
      <span>{{ files.length }} files scanned</span>
    </div>

    <!-- Loading State -->
    <div v-if="files.length === 0" class="bg-gray-900 border border-gray-800 rounded-xl p-12 text-center">
      <div class="text-4xl mb-2">🛡️</div>
      <div class="text-gray-400">Loading quality data...</div>
    </div>

    <!-- Table -->
    <div v-else class="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
      <table class="w-full text-sm">
        <thead class="border-b border-gray-800 text-gray-400">
          <tr>
            <th class="text-left px-3 py-2 font-medium">File Path</th>
            <th class="text-left px-3 py-2 font-medium">Language</th>
            <th class="text-center px-3 py-2 font-medium">Score</th>
            <th class="text-center px-3 py-2 font-medium">Priority</th>
            <th class="text-right px-3 py-2 font-medium">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr 
            v-for="file in files" 
            :key="file.path"
            class="border-b border-gray-800/50 hover:bg-gray-800/60 transition-colors"
          >
            <td class="px-3 py-2 text-gray-100 font-mono text-xs">{{ file.path }}</td>
            <td class="px-3 py-2">
              <span :class="[
                'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
                getLanguageColor(file.language)
              ]">
                {{ file.language }}
              </span>
            </td>
            <td class="px-3 py-2 text-center">
              <span :class="getScoreColor(file.score)">
                {{ file.score.toFixed(1) }}
              </span>
            </td>
            <td class="px-3 py-2 text-center">
              <MetricBadge 
                :label="file.priority" 
                :variant="getPriorityVariant(file.priority)" 
                size="sm" 
              />
            </td>
            <td class="px-3 py-2 text-right">
              <button
                @click="$emit('inspect', file)"
                class="text-xs text-blue-400 hover:text-blue-300 transition-colors"
              >
                View Diagnostics
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
interface QualityFile {
  path: string
  language: string
  score: number
  priority: string
  smell_count: number
}

defineProps<{
  files: QualityFile[]
}>()

defineEmits<{
  'inspect': [file: QualityFile]
}>()

function getLanguageColor(lang: string): string {
  const colors: Record<string, string> = {
    'Go': 'bg-blue-500/10 text-blue-400',
    'PHP': 'bg-purple-500/10 text-purple-400',
    'TypeScript': 'bg-cyan-500/10 text-cyan-400',
    'Python': 'bg-yellow-500/10 text-yellow-400',
    'JavaScript': 'bg-yellow-500/10 text-yellow-400'
  }
  return colors[lang] || 'bg-gray-500/10 text-gray-400'
}

function getScoreColor(score: number): string {
  if (score >= 9.0) return 'text-success font-semibold'
  if (score >= 7.5) return 'text-success'
  if (score >= 6.0) return 'text-info'
  if (score >= 4.0) return 'text-warning'
  return 'text-error font-semibold'
}

function getPriorityVariant(priority: string): 'critical' | 'high' | 'medium' | 'low' | 'isolated' {
  const variants: Record<string, 'critical' | 'high' | 'medium' | 'low' | 'isolated'> = {
    'Critical': 'critical',
    'High': 'high',
    'Medium': 'medium',
    'Low': 'low',
    'Isolated': 'isolated'
  }
  return variants[priority] || 'medium'
}
</script>
