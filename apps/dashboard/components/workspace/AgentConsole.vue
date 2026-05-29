<template>
  <div class="bg-gray-900 border border-gray-800 rounded-2xl p-4 space-y-4">
    <div class="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
      <div class="flex-1 space-y-3">
        <div class="flex flex-wrap items-center gap-2">
          <span class="text-xs uppercase tracking-[0.18em] text-slate-500">Navigator Console</span>
          <span class="inline-flex items-center rounded-full bg-slate-800 px-2.5 py-1 text-[10px] uppercase tracking-wider text-slate-400">
            {{ projectId ? 'Project connected' : 'No project selected' }}
          </span>
          <span v-if="activeModel" class="inline-flex items-center rounded-full bg-blue-900/30 border border-blue-700/30 px-2.5 py-1 text-[10px] uppercase tracking-wider text-blue-300">
            {{ activeModel }}
          </span>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div class="space-y-2">
            <label class="text-xs uppercase tracking-[0.18em] text-slate-500">Tool</label>
            <div class="grid grid-cols-2 gap-2">
              <button
                v-for="tool in tools"
                :key="tool.value"
                type="button"
                @click="selectToolAndRun(tool.value)"
                :class="[
                  'rounded-xl border px-3 py-2 text-left text-sm transition-all',
                  selectedTool === tool.value
                    ? 'border-blue-500 bg-blue-600/10 text-blue-300'
                    : 'border-slate-800 bg-slate-950 text-slate-300 hover:border-slate-600 hover:bg-slate-800'
                ]"
              >
                {{ tool.label }}
              </button>
            </div>
          </div>

        </div>

        <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div v-if="selectedTool === 'trace_lineage'" class="space-y-2">
            <label class="text-xs uppercase tracking-[0.18em] text-slate-500">Direction</label>
            <select
              v-model="direction"
              class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500/20"
            >
              <option value="forward">Forward</option>
              <option value="backward">Backward</option>
            </select>
          </div>

          <div v-if="selectedTool !== 'find_implementation'" class="space-y-2">
            <label class="text-xs uppercase tracking-[0.18em] text-slate-500">Max Depth</label>
            <input
              type="range"
              min="1"
              max="6"
              step="1"
              v-model.number="maxDepth"
              class="w-full accent-blue-500"
            />
            <div class="text-[11px] text-slate-400">Depth: {{ maxDepth }}</div>
          </div>

          <div class="space-y-2">
            <label class="text-xs uppercase tracking-[0.18em] text-slate-500">Status</label>
            <div class="rounded-xl border border-slate-800 bg-slate-950 p-3 text-[12px] font-mono text-slate-300">
              <div class="space-y-1">
                <div>State: <span class="font-semibold text-slate-100">{{ statusLabel }}</span></div>
                <div>Message: <span class="text-slate-400">{{ statusMessage }}</span></div>
                <div v-if="jobId">Job: <span class="text-slate-400">{{ jobId }}</span></div>
                <div v-if="progress !== null">Progress: <span class="text-slate-400">{{ progress }}%</span></div>
              </div>
            </div>
          </div>
        </div>

        <div class="flex flex-wrap gap-2">
          <button
            @click="submitQuery"
            :disabled="!projectId || status === 'running'"
            class="rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {{ status === 'running' ? 'Executing…' : 'Run' }}
          </button>
          <button
            @click="resetConsole"
            type="button"
            class="rounded-xl border border-slate-800 bg-slate-950 px-4 py-2 text-sm font-medium text-slate-200 transition hover:border-slate-600 hover:bg-slate-900"
          >
            Reset Console
          </button>
        </div>
      </div>
    </div>

    <div class="grid grid-cols-1 xl:grid-cols-[1.2fr_0.8fr] gap-4">
      <div class="bg-slate-950 border border-slate-800 rounded-2xl p-4 h-[320px] overflow-auto font-mono text-[12px] text-slate-200">
        <div class="mb-3 text-xs uppercase tracking-[0.18em] text-slate-500">Terminal Logs</div>
        <div v-if="logs.length === 0" class="text-slate-500">Waiting for agent output…</div>
        <div v-for="(line, index) in logs" :key="index" class="whitespace-pre-wrap leading-5">
          <template v-if="line.startsWith('[ERR]')">
            <span class="text-red-400">{{ line }}</span>
          </template>
          <template v-else>
            <span>{{ line }}</span>
          </template>
        </div>
      </div>

      <div class="bg-gray-900 border border-gray-800 rounded-2xl p-4 h-[320px] overflow-auto">
        <div class="mb-3 text-xs uppercase tracking-[0.18em] text-slate-500">Navigator Output</div>
        <div v-if="!result" class="text-slate-500">No structured results yet. Select a tool to populate the output panel.</div>

        <template v-if="result">
          <div class="space-y-3 text-sm text-slate-100">
            <div class="text-xs uppercase tracking-[0.18em] text-slate-500">Tool</div>
            <div class="rounded-xl bg-slate-950 px-3 py-2">
              {{ result.tool || result.data?.tool || 'unknown' }}
            </div>

            <div class="text-xs uppercase tracking-[0.18em] text-slate-500">Summary</div>
            <div class="rounded-xl bg-slate-950 px-3 py-2 text-slate-200">
              <pre class="whitespace-pre-wrap text-[12px]">{{ summaryText }}</pre>
            </div>

            <div v-if="result.tool === 'find_implementation' && Array.isArray(result.matches)" class="space-y-2">
              <div class="text-xs uppercase tracking-[0.18em] text-slate-500">Matches</div>
              <div class="space-y-2">
                <button
                  v-for="(match, index) in result.matches"
                  :key="index"
                  type="button"
                  @click="handleFileClick(match.file_path)"
                  class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-left text-sm text-slate-100 hover:border-blue-500 hover:text-blue-300"
                >
                  <div class="font-semibold">{{ match.file_path }}</div>
                  <div class="text-slate-500 text-[11px]">Score: {{ match.score }}</div>
                </button>
              </div>
            </div>

            <div v-if="result.tool === 'blast_radius' && Array.isArray(result.impacted_files)" class="space-y-2">
              <div class="text-xs uppercase tracking-[0.18em] text-slate-500">Impacted Files</div>
              <div class="space-y-2">
                <button
                  v-for="(file, index) in result.impacted_files"
                  :key="index"
                  type="button"
                  @click="handleFileClick(file.file_path)"
                  class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-left text-sm text-slate-100 hover:border-rose-500 hover:text-rose-300"
                >
                  <div class="font-semibold">{{ file.file_path }}</div>
                  <div class="text-slate-500 text-[11px]">Depends on: {{ file.depends_on }}</div>
                </button>
              </div>
            </div>

            <div v-if="result.tool === 'trace_lineage' && Array.isArray(result.paths)" class="space-y-2">
              <div class="text-xs uppercase tracking-[0.18em] text-slate-500">Lineage Paths</div>
              <div class="space-y-2">
                <div
                  v-for="(path, index) in result.paths"
                  :key="index"
                  class="rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-100"
                >
                  <div class="font-semibold">{{ path.source_dataset || path.source_file || 'source' }} → {{ path.target_dataset || path.target_file || 'target' }}</div>
                  <div class="text-slate-500 text-[11px]">Line range: {{ path.line_range || 'n/a' }}</div>
                </div>
              </div>
            </div>

            <div v-if="result.tool === 'explain_module'" class="space-y-2">
              <div class="text-xs uppercase tracking-[0.18em] text-slate-500">Module Explanation</div>
              <div class="rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-100">
                <div v-if="result.file_path" class="font-semibold">File: {{ result.file_path }}</div>
                <div class="text-slate-400 text-[12px] mt-2">{{ result.summary || 'No summary available.' }}</div>
                <div v-if="result.has_doc_drift" class="mt-2 rounded-xl bg-rose-950 px-3 py-2 text-rose-200">
                  Documentation drift detected.
                </div>
              </div>
              <div v-if="Array.isArray(result.files)" class="space-y-2">
                <div class="text-xs uppercase tracking-[0.18em] text-slate-500">Project Files</div>
                <div class="space-y-2 max-h-52 overflow-y-auto">
                  <button
                    v-for="(file, index) in result.files"
                    :key="index"
                    type="button"
                    @click="handleFileClick(file.file_path)"
                    class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-left text-sm text-slate-100 hover:border-blue-500 hover:text-blue-300"
                  >
                    <div class="font-semibold truncate">{{ file.file_path }}</div>
                    <div class="text-slate-500 text-[11px]">
                      Lang: {{ extractLang(file.purpose_summary || file.language || 'Unknown') }}
                      <span v-if="file.symbol_count !== undefined"> &middot; Symbols: {{ file.symbol_count }}</span>
                    </div>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, computed, onBeforeUnmount, ref, watch, onMounted } from 'vue'

export default defineComponent({
  name: 'AgentConsole',
  props: {
    projectId: { type: String, default: '' },
    externalJobId: { type: String, default: '' }
  },
  emits: ['navigator-result', 'focus-file'],
  setup(props, { emit }) {
    const tools = [
      { label: 'Implementation', value: 'find_implementation' },
      { label: 'Lineage Trace', value: 'trace_lineage' },
      { label: 'Blast Radius', value: 'blast_radius' },
      { label: 'Explain Module', value: 'explain_module' }
    ]

    const selectedTool = ref('find_implementation')
    const direction = ref('forward')
    const maxDepth = ref(3)
    const status = ref<'idle' | 'running' | 'completed' | 'failed'>('idle')
    const statusMessage = ref('Ready')
    const jobId = ref('')
    const progress = ref<number | null>(0)
    const logs = ref<string[]>([])
    const result = ref<any>(null)
    const lastExternalJobId = ref('')
    const activeModel = ref('')
    let pollingInterval: number | null = null

    const statusLabel = computed(() => {
      if (status.value === 'running') return 'Running'
      if (status.value === 'completed') return 'Completed'
      if (status.value === 'failed') return 'Failed'
      return 'Idle'
    })

    const summaryText = computed(() => {
      if (!result.value) return 'No data yet.'
      if (result.value.tool === 'explain_module') {
        return result.value.summary || 'No summary available.'
      }
      if (result.value.tool === 'blast_radius') {
        return `Risk: ${result.value.risk_score ?? 'n/a'} · ${result.value.classification ?? 'unknown'}`
      }
      if (result.value.tool === 'find_implementation') {
        return result.value.matches?.length ? `${result.value.matches.length} match(es) found` : 'No implementation matches found.'
      }
      if (result.value.tool === 'trace_lineage') {
        return result.value.paths?.length ? `${result.value.paths.length} paths traced` : 'No lineage paths discovered.'
      }
      return 'Results available.'
    })

    function extractLang(lang: string): string {
      if (lang.startsWith('[')) {
        const m = lang.match(/\[(.*?)\]/)
        if (m) return m[1]
      }
      return lang || 'Unknown'
    }

    function selectToolAndRun(tool: string) {
      selectedTool.value = tool
      statusMessage.value = 'Ready'
      result.value = null
      logs.value = []
      submitQuery()
    }

    function appendLogs(jobData: any) {
      const stdout = Array.isArray(jobData.stdout_lines) ? jobData.stdout_lines : []
      const stderr = Array.isArray(jobData.stderr_lines) ? jobData.stderr_lines.map((line: string) => `[ERR] ${line}`) : []
      logs.value = [...stdout, ...stderr]
    }

    function handleFileClick(filePath: string) {
      emit('focus-file', filePath)
    }

    function resetConsole() {
      status.value = 'idle'
      statusMessage.value = 'Ready'
      jobId.value = ''
      progress.value = 0
      logs.value = []
      result.value = null
      if (pollingInterval) {
        window.clearInterval(pollingInterval)
        pollingInterval = null
      }
    }

    function extractResult(jobData: any) {
      if (!jobData || !jobData.result) return null
      if (typeof jobData.result === 'object') {
        return jobData.result.success ? jobData.result.data : jobData.result
      }
      return null
    }

    async function fetchJobStatus() {
      if (!jobId.value) return

      try {
        const response = await fetch('/api/v1/workspace/job-status')
        if (!response.ok) {
          status.value = 'failed'
          statusMessage.value = `Status endpoint returned ${response.status}`
          return
        }

        const payload = await response.json()
        if (!payload.success) {
          status.value = 'failed'
          statusMessage.value = payload.error || 'Failed to fetch job status'
          return
        }

        const jobData = payload.data.jobs?.[jobId.value]
        if (!jobData) {
          statusMessage.value = 'Job not found yet…'
          return
        }

        statusMessage.value = jobData.message || statusMessage.value
        progress.value = Number.isFinite(jobData.progress) ? jobData.progress : progress.value
        appendLogs(jobData)

        if (jobData.status === 'completed' || jobData.status === 'failed') {
          status.value = jobData.status === 'completed' ? 'completed' : 'failed'
          statusMessage.value = jobData.status === 'completed' ? 'Query execution finished' : jobData.message || 'Query failed'
          window.clearInterval(pollingInterval!)
          pollingInterval = null

          const parsed = extractResult(jobData)
          if (parsed) {
            result.value = parsed
            emit('navigator-result', parsed)
          } else {
            const stdout = Array.isArray(jobData.stdout_lines) ? jobData.stdout_lines.join('') : ''
            if (stdout) {
              try {
                const parsedStdout = JSON.parse(stdout)
                if (parsedStdout.success && parsedStdout.data) {
                  result.value = parsedStdout.data
                  emit('navigator-result', parsedStdout.data)
                }
              } catch {
                // Not valid JSON — result stays null
              }
            }
          }
        }
      } catch (err: any) {
        status.value = 'failed'
        statusMessage.value = err.message || 'Job polling failed'
        if (pollingInterval) {
          window.clearInterval(pollingInterval)
          pollingInterval = null
        }
      }
    }

    async function submitQuery() {
      if (!props.projectId) {
        status.value = 'failed'
        statusMessage.value = 'Select a project before querying'
        return
      }

      status.value = 'running'
      statusMessage.value = 'Dispatching navigator query'
      progress.value = 0
      logs.value = []
      result.value = null

      const payload = {
        project_id: props.projectId,
        tool: selectedTool.value,
        target: '',
        query: '',
        direction: direction.value,
        max_depth: maxDepth.value
      }

      try {
        const response = await fetch('/api/v1/navigator/query', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        })

        const body = await response.json()
        if (!response.ok || !body.success) {
          status.value = 'failed'
          statusMessage.value = body.error || `Query endpoint returned ${response.status}`
          return
        }

        jobId.value = body.data.job_id
        statusMessage.value = 'Query dispatched, waiting for results'
        if (pollingInterval) {
          window.clearInterval(pollingInterval)
        }

        pollingInterval = window.setInterval(fetchJobStatus, 750)
        fetchJobStatus()
      } catch (err: any) {
        status.value = 'failed'
        statusMessage.value = err.message || 'Failed to dispatch query'
      }
    }

    async function fetchProjectModel() {
      if (!props.projectId) {
        activeModel.value = ''
        return
      }
      try {
        const response = await fetch(`/api/v1/project/settings?project_id=${encodeURIComponent(props.projectId)}`)
        if (response.ok) {
          const result = await response.json()
          if (result.success && result.data?.target_model) {
            activeModel.value = result.data.target_model
          } else {
            activeModel.value = ''
          }
        }
      } catch {
        activeModel.value = ''
      }
    }

    onMounted(() => {
      fetchProjectModel()
    })

    watch(() => props.projectId, () => {
      resetConsole()
      fetchProjectModel()
    })

    watch(() => props.externalJobId, (newJobId) => {
      if (!newJobId || newJobId === lastExternalJobId.value) {
        return
      }

      lastExternalJobId.value = newJobId
      jobId.value = newJobId
      status.value = 'running'
      statusMessage.value = 'Remote ingestion job dispatched'
      logs.value = []
      result.value = null

      if (pollingInterval) {
        window.clearInterval(pollingInterval)
      }

      pollingInterval = window.setInterval(fetchJobStatus, 750)
      fetchJobStatus()
    })

    onBeforeUnmount(() => {
      if (pollingInterval) {
        window.clearInterval(pollingInterval)
        pollingInterval = null
      }
    })

    return {
      tools,
      selectedTool,
      direction,
      maxDepth,
      status,
      statusMessage,
      jobId,
      progress,
      logs,
      result,
      statusLabel,
      summaryText,
      selectToolAndRun,
      extractLang,
      handleFileClick,
      resetConsole,
      submitQuery,
      projectId: props.projectId,
      activeModel
    }
  }
})
</script>

<style scoped>
button:focus {
  outline: none;
}
</style>
