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

        <!-- AI Importance Analysis -->
        <div class="bg-gray-950 border border-gray-800 rounded-xl p-4">
          <div class="text-xs text-gray-500 uppercase tracking-wider mb-3">AI Importance Analysis</div>

          <div v-if="!importanceData && !importanceLoading" class="text-xs text-gray-400">
            Run the analysis to assess this file's centrality, criticality, and risk impact.
          </div>

          <div v-if="importanceLoading" class="space-y-2">
            <div class="flex items-center gap-2 text-xs text-blue-400">
              <span class="inline-block animate-spin">⟳</span>
              Analyzing file importance...
            </div>
            <div class="w-full bg-gray-800 rounded-full h-1.5">
              <div class="bg-blue-500 h-1.5 rounded-full animate-pulse" style="width: 60%"></div>
            </div>
          </div>

          <div v-if="importanceData" class="space-y-3">
            <div class="grid grid-cols-2 gap-2">
              <div class="bg-gray-900 rounded-lg p-2">
                <div class="text-[10px] text-gray-500">Centrality</div>
                <div :class="['text-xs font-semibold', getImportanceColor(importanceData.centrality)]">
                  {{ importanceData.centrality }}
                </div>
              </div>
              <div class="bg-gray-900 rounded-lg p-2">
                <div class="text-[10px] text-gray-500">Change Freq</div>
                <div :class="['text-xs font-semibold', getImportanceColor(importanceData.change_frequency)]">
                  {{ importanceData.change_frequency }}
                </div>
              </div>
              <div class="bg-gray-900 rounded-lg p-2">
                <div class="text-[10px] text-gray-500">Complexity</div>
                <div :class="['text-xs font-semibold', getImportanceColor(importanceData.complexity_rating)]">
                  {{ importanceData.complexity_rating }}
                </div>
              </div>
              <div class="bg-gray-900 rounded-lg p-2">
                <div class="text-[10px] text-gray-500">Criticality</div>
                <div :class="['text-xs font-semibold', getImportanceColor(importanceData.criticality)]">
                  {{ importanceData.criticality }}
                </div>
              </div>
            </div>
            <div class="bg-gray-900 rounded-lg p-3">
              <div class="text-[10px] text-gray-500 mb-1">Risk Assessment</div>
              <div class="text-xs text-gray-300">{{ importanceData.risk_assessment }}</div>
            </div>
            <div class="bg-gray-900 rounded-lg p-3">
              <div class="text-[10px] text-gray-500 mb-1">Explanation</div>
              <div class="text-xs text-gray-300 leading-relaxed">{{ importanceData.explanation }}</div>
            </div>
          </div>

          <button
            v-if="!importanceLoading"
            @click="analyzeImportance"
            :disabled="importanceData !== null"
            class="w-full mt-3 bg-purple-600 hover:bg-purple-700 text-white font-medium py-2 px-4 rounded-lg transition-colors active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed text-sm"
          >
            {{ importanceData ? '✓ Analyzed' : 'Analyze Importance' }}
          </button>
          <button
            v-if="importanceData"
            @click="importanceData = null"
            class="w-full mt-1 text-xs text-gray-500 hover:text-gray-300 transition-colors"
          >
            Re-analyze
          </button>
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
import { ref, onUnmounted, watch } from 'vue'
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

// AI Importance state
const importanceLoading = ref(false)
const importanceData = ref<any>(null)

async function analyzeImportance() {
  if (!props.file || !props.file.path) return
  importanceLoading.value = true
  importanceData.value = null

  try {
    const workspace = useWorkspaceState()
    if (!workspace.activeProject.value) {
      throw new Error('No active project')
    }

    const response = await fetch('/api/v1/topology/file-importance', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_id: workspace.activeProject.value.id,
        file_path: props.file.path
      })
    })

    const result = await response.json()
    if (result.success && result.data?.importance) {
      importanceData.value = result.data.importance
    } else {
      throw new Error(result.error || 'Analysis failed')
    }
  } catch (err: any) {
    console.error('[NodeInspector] Importance analysis failed:', err)
    importanceData.value = {
      centrality: 'error',
      change_frequency: 'error',
      complexity_rating: 'error',
      criticality: 'error',
      risk_assessment: 'Failed to analyze. ' + (err.message || ''),
      explanation: 'Could not complete AI analysis. Check that the AI provider is configured in Settings.'
    }
  } finally {
    importanceLoading.value = false
  }
}

// Reset importance when file changes
watch(() => props.file?.path, () => {
  importanceData.value = null
  importanceLoading.value = false
})

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

function getImportanceColor(rating: string): string {
  const low = 'text-emerald-400'
  const moderate = 'text-sky-400'
  const high = 'text-amber-400'
  const critical = 'text-rose-400'
  const map: Record<string, string> = {
    'low': low,
    'stable': low,
    'simple': low,
    'medium': moderate,
    'moderate': moderate,
    'high': high,
    'frequent': high,
    'complex': high,
    'critical': critical,
    'very_frequent': critical,
    'very_complex': critical,
  }
  return map[rating?.toLowerCase()] || 'text-gray-400'
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1048576).toFixed(1) + ' MB'
}
</script>
