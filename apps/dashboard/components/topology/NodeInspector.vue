<template>
  <transition 
    enter-active-class="transform transition ease-in-out duration-300"
    enter-from-class="translate-x-full"
    enter-to-class="translate-x-0"
    leave-active-class="transform transition ease-in-out duration-300"
    leave-from-class="translate-x-0"
    leave-to-class="translate-x-full"
  >
    <div 
      v-if="modelValue && file" 
      class="fixed inset-y-0 right-0 w-96 bg-gray-900 border-l border-gray-800 shadow-2xl overflow-y-auto"
      style="will-change: transform"
    >
      <!-- Header -->
      <div class="sticky top-0 bg-gray-900 border-b border-gray-800 p-4 z-10">
        <div class="flex items-center justify-between mb-2">
          <h3 class="text-lg font-bold text-gray-100">File Diagnostics</h3>
          <button 
            @click="$emit('update:modelValue', false)"
            class="text-gray-400 hover:text-gray-200 transition-colors"
          >
            ✕
          </button>
        </div>
        <div class="font-mono text-sm text-blue-400">{{ file.path }}</div>
      </div>

      <!-- Content -->
      <div class="p-4 space-y-6">
        <!-- Quality Score -->
        <div class="bg-gradient-to-b from-gray-900 to-gray-950 border border-gray-800 rounded-xl p-4">
          <div class="text-xs text-gray-500 uppercase tracking-wider mb-2">Quality Score</div>
          <div class="flex items-baseline gap-2">
            <span :class="['text-3xl font-bold', getScoreColor(file.score), auditLoading ? 'animate-pulse' : '']">
              {{ auditLoading ? '—' : file.score.toFixed(1) }}
            </span>
            <span class="text-gray-500">/ 10.0</span>
          </div>
          <!-- Audit Loading Indicator -->
          <div v-if="auditLoading" class="mt-2 text-xs text-blue-400">
            <span class="inline-block animate-spin mr-1">⟳</span>
            {{ auditMessage || 'Running audit pipeline...' }}
          </div>
        </div>

        <!-- Metadata Grid -->
        <div class="grid grid-cols-2 gap-3">
          <div class="bg-gray-950 border border-gray-800 rounded-lg p-3">
            <div class="text-xs text-gray-500 mb-1">Language</div>
            <div class="text-sm text-gray-100">{{ file.language }}</div>
          </div>
          <div class="bg-gray-950 border border-gray-800 rounded-lg p-3">
            <div class="text-xs text-gray-500 mb-1">Priority</div>
            <MetricBadge :label="file.priority" :variant="getPriorityVariant(file.priority)" size="sm" />
          </div>
          <div class="bg-gray-950 border border-gray-800 rounded-lg p-3">
            <div class="text-xs text-gray-500 mb-1">Symbols</div>
            <div class="text-lg font-bold text-gray-100">{{ file.symbol_count || '—' }}</div>
          </div>
          <div class="bg-gray-950 border border-gray-800 rounded-lg p-3">
            <div class="text-xs text-gray-500 mb-1">Dependencies</div>
            <div class="text-lg font-bold text-gray-100">{{ file.dependency_count || '—' }}</div>
          </div>
        </div>

        <!-- Complexity Metrics -->
        <div class="bg-gray-950 border border-gray-800 rounded-xl p-4">
          <div class="text-xs text-gray-500 uppercase tracking-wider mb-3">Complexity Metrics</div>
          <div class="space-y-2">
            <div class="flex justify-between text-sm">
              <span class="text-gray-400">Entity Count</span>
              <span class="text-gray-100 font-mono">{{ file.entity_count || 0 }}</span>
            </div>
            <div class="flex justify-between text-sm">
              <span class="text-gray-400">Complexity Ratio</span>
              <span class="text-gray-100 font-mono">
                {{ file.dependency_count && file.symbol_count ? (file.dependency_count / file.symbol_count).toFixed(2) : '0.00' }}
              </span>
            </div>
            <div class="flex justify-between text-sm">
              <span class="text-gray-400">File Size</span>
              <span class="text-gray-100 font-mono">{{ file.file_size ? formatBytes(file.file_size) : '—' }}</span>
            </div>
          </div>
        </div>

        <!-- Detected Smells -->
        <div v-if="file.smells && file.smells.length > 0" class="space-y-3">
          <div class="text-xs text-gray-500 uppercase tracking-wider">
            Detected Smells ({{ file.smells.length }})
          </div>
          <div 
            v-for="(smell, idx) in file.smells" 
            :key="idx"
            class="bg-error/5 border border-error/20 rounded-lg p-3"
          >
            <div class="text-sm font-medium text-error mb-1">{{ smell.type }}</div>
            <div class="text-xs text-gray-400">{{ smell.description }}</div>
          </div>
        </div>

        <!-- Action Buttons -->
        <div class="space-y-2">
          <button 
            @click="runAuditPipeline"
            :disabled="auditLoading"
            :class="[
              'w-full font-medium py-2 px-4 rounded-lg transition-colors active:scale-95',
              auditLoading 
                ? 'bg-blue-600/50 border-2 border-blue-500 border-dashed animate-spin text-white cursor-not-allowed' 
                : auditComplete
                  ? 'bg-emerald-600 hover:bg-emerald-700 text-white'
                  : 'bg-blue-600 hover:bg-blue-700 text-white'
            ]"
          >
            {{ auditLoading ? 'Running Audit...' : auditComplete ? '✓ Audit Complete' : 'Run Agent Audit Pipeline' }}
          </button>
          <button 
            @click="$emit('update:modelValue', false)"
            class="w-full bg-gray-800 hover:bg-gray-700 text-gray-300 font-medium py-2 px-4 rounded-lg transition-colors active:scale-95"
          >
            Close Inspector
          </button>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { ref, onUnmounted } from 'vue'
import { useWorkspaceState } from '../../composables/useWorkspaceState'

interface QualityFile {
  path: string
  language: string
  score: number
  priority: string
  smell_count: number
  symbol_count?: number
  dependency_count?: number
  entity_count?: number
  file_size?: number
  smells?: Array<{ type: string, description: string }>
}

const props = defineProps<{
  modelValue: boolean
  file: QualityFile | null
}>()

defineEmits<{
  'update:modelValue': [value: boolean]
}>()

// Audit state
const auditLoading = ref(false)
const auditComplete = ref(false)
const auditMessage = ref('')
const activeAuditJobId = ref('')
let auditPollingInterval: any = null

async function runAuditPipeline() {
  if (!props.file || !props.file.path) {
    console.error('[NodeInspector] No file selected for audit')
    return
  }
  
  auditLoading.value = true
  auditComplete.value = false
  auditMessage.value = 'Initializing audit...'
  
  try {
    console.error('[NodeInspector] Starting audit pipeline for:', props.file.path)
    
    // Get active project from workspace state
    const workspace = useWorkspaceState()
    if (!workspace.activeProject.value) {
      throw new Error('No active project selected')
    }
    
    // Call audit endpoint
    const response = await fetch('/api/v1/workspace/audit-file', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_id: workspace.activeProject.value.id,
        file_path: props.file.path
      })
    })
    
    if (!response.ok) {
      throw new Error(`Audit API returned ${response.status}`)
    }
    
    const result = await response.json()
    
    if (result.success) {
      activeAuditJobId.value = result.data.job_id
      console.error('[NodeInspector] Audit job started:', result.data.job_id)
      
      // Start polling for job status
      startAuditPolling()
    } else {
      throw new Error(result.error || 'Failed to start audit')
    }
  } catch (err: any) {
    console.error('[NodeInspector] Audit failed:', err)
    auditLoading.value = false
    alert('Failed to run audit: ' + (err.message || 'Unknown error'))
  }
}

function startAuditPolling() {
  // Clear any existing polling
  if (auditPollingInterval) {
    clearInterval(auditPollingInterval)
  }
  
  // Poll every 800ms
  auditPollingInterval = setInterval(async () => {
    try {
      const response = await fetch('/api/v1/workspace/job-status')
      if (!response.ok) return
      
      const result = await response.json()
      
      if (result.success && activeAuditJobId.value) {
        const job = result.data.jobs[activeAuditJobId.value]
        
        if (job) {
          auditMessage.value = job.message || ''
          
          console.error(`[NodeInspector] Audit job: ${job.status} - ${job.message}`)
          
          // Check if job completed or failed
          if (job.status === 'completed') {
            stopAuditPolling()
            auditLoading.value = false
            auditComplete.value = true
            
            console.error('[NodeInspector] Audit completed!')
            
            // TODO: Refresh file data from API
            // For now, just show completion state
          } else if (job.status === 'failed') {
            stopAuditPolling()
            auditLoading.value = false
            
            console.error('[NodeInspector] Audit failed:', job.message)
            alert('Audit failed: ' + job.message)
          }
        }
      }
    } catch (err) {
      console.error('[NodeInspector] Error polling audit status:', err)
    }
  }, 800)
}

function stopAuditPolling() {
  if (auditPollingInterval) {
    clearInterval(auditPollingInterval)
    auditPollingInterval = null
  }
}

onUnmounted(() => {
  stopAuditPolling()
})

function getScoreColor(score: number): string {
  if (score >= 9.0) return 'text-success'
  if (score >= 7.5) return 'text-success'
  if (score >= 6.0) return 'text-info'
  if (score >= 4.0) return 'text-warning'
  return 'text-error'
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

function formatBytes(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1048576).toFixed(1) + ' MB'
}
</script>
