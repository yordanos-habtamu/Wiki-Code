<template>
  <div class="bg-slate-950 border border-slate-800 rounded-xl p-5 font-mono text-xs text-gray-300 space-y-4">
    <div class="border-b border-slate-800 pb-3">
      <h3 class="text-cyan-400 font-bold tracking-wider uppercase">Remote GitHub Ingestion Workspace</h3>
      <p class="text-[10px] text-gray-500 mt-1">Stream remote repository metrics directly into your isolated project space.</p>
    </div>

    <div class="space-y-3">
      <div>
        <label class="block text-gray-400 mb-1 text-[10px] uppercase tracking-wider">GitHub Personal Access Token (PAT)</label>
        <input
          v-model="githubToken"
          type="password"
          placeholder="ghp_xxxxxxxxxxxxxxxxxxxxxxxx"
          class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-gray-200 focus:outline-none focus:border-cyan-500 font-sans"
        />
      </div>

      <div>
        <label class="block text-gray-400 mb-1 text-[10px] uppercase tracking-wider">Target Repository HTTPS URL</label>
        <input
          v-model="repoUrl"
          type="text"
          placeholder="https://github.com/owner/repository"
          class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-gray-200 focus:outline-none focus:border-cyan-500"
        />
      </div>

      <div>
        <label class="block text-gray-400 mb-1 text-[10px] uppercase tracking-wider">Clone Depth</label>
        <div class="flex items-center gap-2">
          <input
            v-model.number="cloneDepth"
            type="number"
            min="0"
            max="100000"
            placeholder="50"
            class="w-28 bg-slate-900 border border-slate-700 rounded p-2 text-gray-200 focus:outline-none focus:border-cyan-500"
          />
          <span class="text-[10px] text-gray-500">0 = full history</span>
        </div>
      </div>
    </div>

    <div class="flex flex-wrap gap-2 pt-2">
      <button
        @click="testConnection"
        :disabled="isValidating || isIngesting || isPollingActive || !githubToken"
        class="px-3 py-2 bg-slate-900 border border-slate-700 rounded hover:border-gray-400 disabled:opacity-40 disabled:hover:border-slate-700 transition-colors"
      >
        {{ isValidating ? 'Verifying...' : 'Test Connection' }}
      </button>

      <button
        @click="triggerIngestion"
        :disabled="isIngesting || isValidating || isPollingActive || !githubToken || !repoUrl"
        class="px-3 py-2 bg-cyan-950 border border-cyan-700 text-cyan-400 rounded hover:bg-cyan-900/40 disabled:opacity-40 disabled:hover:bg-cyan-950/20 transition-colors font-bold"
      >
        {{ isIngesting || isPollingActive ? 'Ingesting...' : 'Start Ingestion' }}
      </button>
    </div>

    <!-- Ingestion Progress Bar -->
    <div v-if="isPollingActive" class="mt-2 space-y-2">
      <div class="flex items-center justify-between">
        <span class="text-cyan-400 text-[10px] uppercase tracking-wider">Ingestion Progress</span>
        <span class="text-gray-400 text-[10px]">{{ ingestionProgress }}%</span>
      </div>
      <div class="w-full bg-slate-900 rounded-full h-2.5 overflow-hidden">
        <div
          class="bg-cyan-500 h-full transition-all duration-500 ease-out rounded-full"
          :style="{ width: `${ingestionProgress}%` }"
        ></div>
      </div>
      <div class="text-[10px] text-gray-500 font-sans">{{ ingestionMessage || 'Processing...' }}</div>
    </div>

    <!-- Ingestion Complete -->
    <div v-if="ingestionComplete" class="mt-2 p-2 bg-emerald-950/30 border border-emerald-800 text-emerald-400 rounded text-[11px]">
      ✓ Ingestion completed successfully. Project <span class="font-bold">{{ ingestionProjectName }}</span> is now available.
    </div>

    <div class="mt-2 space-y-2">
      <div v-if="validationStatus === 'SUCCESS'" class="p-2 bg-emerald-950/30 border border-emerald-800 text-emerald-400 rounded text-[11px]">
        ✓ API Authorization Verified. Connection pipeline ready.
      </div>
      <div v-if="validationStatus === 'FAILED' || errorMessage" class="p-2 bg-rose-950/30 border border-rose-800 text-rose-400 rounded text-[11px] break-all">
        ⚠ Error: {{ errorMessage }}
      </div>
    </div>
  </div>
</template>

<script>
import { defineComponent, ref, onBeforeUnmount } from 'vue'

export default defineComponent({
  name: 'GitHubIngestionPanel',
  props: {
    projectId: { type: String, required: true }
  },
  emits: ['ingestion-started', 'ingestion-completed', 'error'],
  setup(props, { emit }) {
    const githubToken = ref('')
    const repoUrl = ref('')
    const cloneDepth = ref(50)
    const isValidating = ref(false)
    const isIngesting = ref(false)
    const validationStatus = ref('IDLE')
    const errorMessage = ref('')

    // Ingestion progress tracking
    const isPollingActive = ref(false)
    const ingestionProgress = ref(0)
    const ingestionMessage = ref('')
    const ingestionComplete = ref(false)
    const ingestionProjectId = ref('')
    const ingestionProjectName = ref('')
    let pollingInterval = null

    const normalizeRepoUrl = (value) => {
      const candidate = String(value || '').trim().replace(/\/+$/, '')
      if (!candidate) {
        throw new Error('Repository URL is required')
      }
      if (!/^https:\/\/github\.com\//i.test(candidate)) {
        throw new Error('Repository URL must be a GitHub HTTPS URL')
      }
      return candidate
    }

    const testConnection = async () => {
      if (!githubToken.value) return
      isValidating.value = true
      validationStatus.value = 'IDLE'
      errorMessage.value = ''

      try {
        const res = await fetch('/api/v1/github/test-connection', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ github_token: githubToken.value, repository_url: repoUrl.value })
        })

        const payload = await res.json()
        if (res.ok && payload.success) {
          validationStatus.value = 'SUCCESS'
          errorMessage.value = ''
        } else {
          validationStatus.value = 'FAILED'
          errorMessage.value = payload.error || payload.message || 'Verification rejected.'
          emit('error', errorMessage.value)
        }
      } catch (err) {
        validationStatus.value = 'FAILED'
        errorMessage.value = err?.message || 'Network gateway communication failure.'
        emit('error', errorMessage.value)
      } finally {
        isValidating.value = false
      }
    }

    function startIngestionPolling(jobId) {
      isPollingActive.value = true
      ingestionProgress.value = 0
      ingestionMessage.value = 'Initializing ingestion pipeline...'
      ingestionComplete.value = false

      if (pollingInterval) {
        clearInterval(pollingInterval)
        pollingInterval = null
      }

      pollingInterval = setInterval(async () => {
        try {
          const response = await fetch('/api/v1/workspace/job-status')
          if (!response.ok) return

          const result = await response.json()
          if (result.success && jobId) {
            const job = result.data.jobs[jobId]
            if (job) {
              ingestionProgress.value = job.progress || 0
              ingestionMessage.value = job.message || ingestionMessage.value

              if (job.status === 'completed') {
                clearInterval(pollingInterval)
                pollingInterval = null
                isPollingActive.value = false
                isIngesting.value = false
                ingestionProgress.value = 100
                ingestionMessage.value = 'Ingestion completed successfully'
                ingestionComplete.value = true

                emit('ingestion-completed', {
                  project_id: ingestionProjectId.value,
                  project_name: ingestionProjectName.value
                })
              } else if (job.status === 'failed') {
                clearInterval(pollingInterval)
                pollingInterval = null
                isPollingActive.value = false
                isIngesting.value = false
                errorMessage.value = job.message || 'Ingestion failed'
                emit('error', errorMessage.value)
              }
            }
          }
        } catch (err) {
          // Continue polling on transient errors
        }
      }, 1000)
    }

    const triggerIngestion = async () => {
      if (!githubToken.value || !repoUrl.value) return
      isIngesting.value = true
      validationStatus.value = 'IDLE'
      errorMessage.value = ''
      ingestionComplete.value = false

      try {
        const normalizedUrl = normalizeRepoUrl(repoUrl.value)
        const res = await fetch('/api/v1/project/ingest-github', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            project_id: props.projectId || '',
            github_token: githubToken.value,
            repository_url: normalizedUrl,
            clone_depth: cloneDepth.value || 50
          })
        })

        const payload = await res.json()
        if (res.ok && payload.success && payload.data?.job_id) {
          // Store project info from response for completion event
          ingestionProjectId.value = payload.data.project_id || ''
          ingestionProjectName.value = payload.data.project_name || ''

          // Emit ingestion-started for AgentConsole to start watching
          emit('ingestion-started', payload.data.job_id)

          // Start our own progress polling
          startIngestionPolling(payload.data.job_id)
        } else {
          const message = payload.error || payload.message || 'Failed to initialize ingestion pipeline.'
          errorMessage.value = message
          isIngesting.value = false
          emit('error', message)
        }
      } catch (err) {
        const message = err?.message || 'Failed to dispatch worker process execution.'
        errorMessage.value = message
        isIngesting.value = false
        emit('error', message)
      }
      // Note: do NOT set isIngesting = false here; polling will handle it
    }

    onBeforeUnmount(() => {
      if (pollingInterval) {
        clearInterval(pollingInterval)
        pollingInterval = null
      }
    })

    return {
      githubToken,
      repoUrl,
      cloneDepth,
      isValidating,
      isIngesting,
      isPollingActive,
      validationStatus,
      errorMessage,
      ingestionProgress,
      ingestionMessage,
      ingestionComplete,
      ingestionProjectName,
      testConnection,
      triggerIngestion
    }
  }
})
</script>
