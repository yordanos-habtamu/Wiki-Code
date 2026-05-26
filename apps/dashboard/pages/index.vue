<template>
  <div class="min-h-screen bg-gray-950 text-gray-100">
    <!-- Sidebar -->
    <aside class="fixed inset-y-0 left-0 w-64 bg-gray-900 border-r border-gray-800 flex flex-col">
      <!-- Logo -->
      <div class="p-4 border-b border-gray-800">
        <div class="flex items-center gap-3">
          <div class="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
            <span class="text-white font-bold text-sm">W</span>
          </div>
          <div>
            <h1 class="font-bold text-gray-100">WikiHub</h1>
            <p class="text-xs text-gray-500">Developer Console</p>
          </div>
        </div>
      </div>

      <!-- Workspace Selector -->
      <div class="p-3 border-b border-gray-800">
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs text-gray-500">Workspace</span>
          <div class="flex gap-2">
            <button 
              @click="resetWorkspace"
              class="text-[10px] text-red-400 hover:text-red-300 transition-colors"
              title="Clear workspace state"
            >
              ↺
            </button>
            <button 
              @click="showRegisterModal = true"
              class="text-[10px] text-blue-400 hover:text-blue-300 transition-colors"
            >
              + Add
            </button>
          </div>
        </div>
        <select 
          v-model="selectedProjectId"
          @change="onProjectChange"
          :disabled="workspace.isSwitchingWorkspace.value"
          class="w-full rounded-lg bg-gray-950 border border-gray-800 text-white px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500/50 disabled:opacity-50"
        >
          <option value="">Select project...</option>
          <option v-for="project in workspace.projectsList.value" :key="project.id" :value="project.id">
            {{ project.name }}
          </option>
        </select>
        <div v-if="workspace.activeProject.value" class="mt-2 space-y-1">
          <div class="text-[10px] text-gray-600 truncate" :title="workspace.activeProject.value.repo_path">
            {{ workspace.activeProject.value.repo_path }}
          </div>
          <div class="flex gap-2">
            <button 
              @click="rescanProject"
              :disabled="scanLoading"
              class="flex-1 text-[10px] bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-400 border border-emerald-600/30 rounded px-2 py-1 transition-colors disabled:opacity-50"
            >
              {{ scanLoading ? '⏳ Scanning...' : '↻ Rescan' }}
            </button>
            <button 
              @click="deleteProject"
              :disabled="scanLoading"
              class="text-[10px] bg-red-600/20 hover:bg-red-600/30 text-red-400 border border-red-600/30 rounded px-2 py-1 transition-colors disabled:opacity-50"
              title="Delete Project"
            >
              🗑️
            </button>
          </div>
          <!-- Progress Bar -->
          <div v-if="scanLoading && activeJobId" class="space-y-1">
            <div class="w-full bg-gray-800 rounded-full h-1.5 overflow-hidden">
              <div 
                class="bg-emerald-500 h-full transition-all duration-300 ease-out"
                :style="{ width: `${jobProgress}%` }"
              ></div>
            </div>
            <div class="text-[9px] text-gray-500 truncate">{{ jobMessage }}</div>
          </div>
        </div>
      </div>

      <!-- Navigation -->
      <nav class="flex-1 p-4 space-y-1">
        <button 
          v-for="item in navItems" 
          :key="item.name"
          @click="activeTab = item.id"
          :class="[
            'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors',
            activeTab === item.id 
              ? 'bg-blue-600/10 text-blue-400 border border-blue-500/20' 
              : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'
          ]"
        >
          <span>{{ item.icon }}</span>
          <span>{{ item.label }}</span>
        </button>
      </nav>

      <!-- User Profile -->
      <div class="p-4 border-t border-gray-800">
        <div class="flex items-center justify-between mb-3">
          <span class="text-xs text-gray-500">Workspace</span>
          <span :class="['inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-medium border', 
                        apiStatus === 'connected' ? 'bg-success/10 text-success border-success/20' : 'bg-error/10 text-error border-error/20']">
            {{ apiStatus === 'connected' ? '● LIVE' : '● OFFLINE' }}
          </span>
        </div>
        <div class="text-sm text-gray-300 mb-3">{{ activeUser || 'Anonymous' }}</div>
        <button 
          @click="handleLogout"
          class="w-full bg-gray-800 hover:bg-gray-700 text-gray-300 text-sm font-medium py-2 px-3 rounded-lg transition-colors"
        >
          Logout
        </button>
      </div>
    </aside>

    <!-- Main Content -->
    <main class="ml-64 p-6">
      <!-- Loading State -->
      <div v-if="isLoading" class="flex items-center justify-center h-96">
        <div class="text-center">
          <div class="text-4xl mb-2 animate-pulse">⏳</div>
          <div class="text-gray-400">Loading dashboard...</div>
        </div>
      </div>

      <!-- Dashboard Content -->
      <template v-else>
      <!-- Header -->
      <header class="mb-6">
        <h2 class="text-2xl font-bold text-gray-100 mb-1">{{ getCurrentTabLabel }}</h2>
        <p class="text-gray-400 text-sm">{{ getCurrentTabDescription }}</p>
      </header>

      <!-- Tab Content -->
      <div v-if="activeTab === 'dashboard'" class="space-y-6">
        <!-- Stats Grid -->
        <StatGrid :stats="indexStats" />

        <!-- Quality Table -->
        <QualityTable :files="qualityFiles" @inspect="inspectFile" />
      </div>

      <div v-if="activeTab === 'traverser'" class="space-y-4">
        <!-- Git Intelligence Controls -->
        <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-sm font-semibold text-gray-300">Git Analytics Controls</h3>
            <MetricBadge label="Git Integration" variant="isolated" size="sm" />
          </div>
          
          <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
            <!-- Branch Selector -->
            <div>
              <label class="block text-xs text-gray-400 mb-1">Branch</label>
              <select 
                v-model="gitControls.selectedBranch"
                @change="onBranchChange"
                class="w-full rounded-lg bg-gray-950 border border-gray-800 text-white px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500/50"
              >
                <option value="">Loading...</option>
                <option v-for="branch in gitControls.branches" :key="branch" :value="branch">
                  {{ branch }}{{ branch === gitControls.activeBranch ? ' (active)' : '' }}
                </option>
              </select>
            </div>
            
            <!-- Commit Selector -->
            <div>
              <label class="block text-xs text-gray-400 mb-1">Recent Commits</label>
              <select 
                v-model="gitControls.selectedCommit"
                @change="onCommitSelect"
                class="w-full rounded-lg bg-gray-950 border border-gray-800 text-white px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500/50"
              >
                <option value="">Select commit...</option>
                <option v-for="commit in gitControls.commits" :key="commit.hash" :value="commit.hash">
                  {{ commit.short_hash }} - {{ commit.message.substring(0, 30) }}...
                </option>
              </select>
            </div>
            
            <!-- Commit Range Slider -->
            <div>
              <label class="block text-xs text-gray-400 mb-1">Lookback Range: {{ gitControls.commitLimit }} commits</label>
              <input 
                type="range" 
                v-model.number="gitControls.commitLimit"
                @input="onLimitChange"
                min="5" 
                max="100" 
                step="5"
                class="w-full h-2 bg-gray-800 rounded-lg appearance-none cursor-pointer accent-blue-500"
              />
              <div class="flex justify-between text-[10px] text-gray-500 mt-1">
                <span>5</span>
                <span>100</span>
              </div>
            </div>
            
            <!-- Refresh Button -->
            <div class="flex items-end">
              <button 
                @click="refreshGitData"
                :disabled="gitControls.loading"
                class="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 text-white text-sm font-medium py-2 px-4 rounded-lg transition-colors active:scale-95 flex items-center justify-center gap-2"
              >
                <span v-if="gitControls.loading" class="animate-spin">⟳</span>
                {{ gitControls.loading ? 'Loading...' : 'Refresh' }}
              </button>
            </div>
          </div>
        </div>
        
        <!-- Delta Scoreboard -->
        <div v-if="gitControls.diffData" class="grid grid-cols-1 md:grid-cols-4 gap-4">
          <!-- Files Changed -->
          <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <div class="text-xs text-gray-500 mb-1">Files Changed</div>
            <div class="text-2xl font-bold text-gray-100">{{ gitControls.diffData.files_changed }}</div>
            <div class="text-[10px] text-gray-400 mt-1">in selected commit</div>
          </div>
          
          <!-- Lines Added -->
          <div class="bg-gray-900 border border-green-900/30 rounded-xl p-4">
            <div class="text-xs text-green-400 mb-1">Lines Added</div>
            <div class="text-2xl font-bold text-green-400">+{{ gitControls.diffData.total_added }}</div>
            <div class="text-[10px] text-gray-400 mt-1">structural additions</div>
          </div>
          
          <!-- Lines Removed -->
          <div class="bg-gray-900 border border-red-900/30 rounded-xl p-4">
            <div class="text-xs text-red-400 mb-1">Lines Removed</div>
            <div class="text-2xl font-bold text-red-400">-{{ gitControls.diffData.total_removed }}</div>
            <div class="text-[10px] text-gray-400 mt-1">structural deletions</div>
          </div>
          
          <!-- Complexity Delta -->
          <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <div class="text-xs text-gray-500 mb-1">Complexity Δ</div>
            <div :class="['text-2xl font-bold', gitControls.diffData.complexity_delta > 0 ? 'text-amber-400' : 'text-emerald-400']">
              {{ gitControls.diffData.complexity_delta > 0 ? '+' : '' }}{{ gitControls.diffData.complexity_delta.toFixed(2) }}
            </div>
            <div class="text-[10px] text-gray-400 mt-1">
              {{ gitControls.diffData.complexity_delta > 0 ? 'increasing' : 'stable' }}
            </div>
          </div>
        </div>
        
        <!-- Navigator Console -->
        <AgentConsole
          :project-id="workspace.activeProject.value?.id"
          :external-job-id="externalIngestionJobId"
          @navigator-result="handleNavigatorResult"
          @focus-file="focusOnNode"
        />

        <!-- Canvas -->
        <ClientOnly>
          <CanvasWrapper v-slot="{ dimensions }">
            <PhysicsEngine 
              :nodes="traverserData.nodes" 
              :links="traverserData.links"
              :dimensions="dimensions"
              :lineage-paths="lineagePaths"
              :blast-radius-nodes="blastRadiusNodes"
              :focus-node-id="focusFilePath"
            />
          </CanvasWrapper>
        </ClientOnly>
      </div>

      <div v-if="activeTab === 'quality'" class="space-y-4">
        <QualityTable :files="qualityFiles" @inspect="inspectFile" />
      </div>

      <div v-if="activeTab === 'analytics'" class="space-y-4">
        <!-- Telemetry Summary Cards -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <div class="text-xs text-gray-500 mb-1">Total Input Tokens</div>
            <div class="text-2xl font-bold text-blue-400">{{ telemetryAggregates.total_input_tokens?.toLocaleString() || 0 }}</div>
          </div>
          <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <div class="text-xs text-gray-500 mb-1">Total Output Tokens</div>
            <div class="text-2xl font-bold text-emerald-400">{{ telemetryAggregates.total_output_tokens?.toLocaleString() || 0 }}</div>
          </div>
          <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <div class="text-xs text-gray-500 mb-1">Estimated Cost</div>
            <div class="text-2xl font-bold text-amber-400">${{ telemetryAggregates.total_estimated_cost?.toFixed(6) || '0.000000' }}</div>
          </div>
        </div>

        <!-- Telemetry Logs Table -->
        <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-sm font-semibold text-gray-300">Token Usage Logs</h3>
            <button
              @click="fetchTelemetryData"
              class="text-[10px] bg-gray-800 hover:bg-gray-700 text-gray-300 px-3 py-1 rounded-lg transition-colors"
            >
              ↻ Refresh
            </button>
          </div>

          <div v-if="telemetryLoading" class="text-center py-8 text-gray-500">
            <div class="animate-spin text-2xl mb-2">⟳</div>
            Loading telemetry data...
          </div>

          <div v-else-if="telemetryLogs.length === 0" class="text-center py-8 text-gray-500">
            <div class="text-4xl mb-2">📊</div>
            <div>No telemetry data yet. Run navigator queries to generate usage logs.</div>
          </div>

          <div v-else class="overflow-x-auto">
            <table class="w-full text-xs">
              <thead>
                <tr class="border-b border-gray-800 text-gray-500">
                  <th class="text-left py-2 px-2">Model</th>
                  <th class="text-right py-2 px-2">Input</th>
                  <th class="text-right py-2 px-2">Output</th>
                  <th class="text-right py-2 px-2">Cost</th>
                  <th class="text-center py-2 px-2">Status</th>
                  <th class="text-right py-2 px-2">Time</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(log, index) in telemetryLogs" :key="index" class="border-b border-gray-800/50 hover:bg-gray-800/30">
                  <td class="py-2 px-2 text-gray-300 font-mono">{{ log.model_id || 'unknown' }}</td>
                  <td class="py-2 px-2 text-right text-blue-400">{{ log.input_tokens?.toLocaleString() || 0 }}</td>
                  <td class="py-2 px-2 text-right text-emerald-400">{{ log.output_tokens?.toLocaleString() || 0 }}</td>
                  <td class="py-2 px-2 text-right text-amber-400">${{ log.estimated_cost?.toFixed(6) || '0.000000' }}</td>
                  <td class="py-2 px-2 text-center">
                    <span :class="['inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-medium',
                      log.execution_status === 'SUCCESS' ? 'bg-emerald-900/30 text-emerald-400' : 'bg-rose-900/30 text-rose-400']">
                      {{ log.execution_status }}
                    </span>
                  </td>
                  <td class="py-2 px-2 text-right text-gray-500">{{ formatTelemetryTime(log.created_at) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div v-if="activeTab === 'settings'" class="space-y-4">
        <SettingsPanel
          @ingestion-started="handleIngestionJobStarted"
          @ingestion-completed="handleIngestionCompleted"
        />
      </div>
      </template>
    </main>

    <!-- Node Inspector -->
    <NodeInspector 
      v-model="showInspector" 
      :file="selectedFile" 
    />

    <!-- Workspace Loading Overlay -->
    <div 
      v-if="workspace.isSwitchingWorkspace.value" 
      class="fixed inset-0 z-50 bg-gray-950/95 backdrop-blur-sm flex items-center justify-center"
    >
      <div class="text-center">
        <div class="text-6xl mb-4 animate-spin">⟳</div>
        <div class="text-xl font-bold text-gray-100 mb-2">Switching Workspace</div>
        <div class="text-gray-400">Loading project context...</div>
      </div>
    </div>

    <!-- Active Scan Lockout Overlay -->
    <div
      v-if="scanLoading && activeJobId"
      class="fixed inset-0 z-40 bg-gray-950/30 backdrop-blur-[2px] pointer-events-none flex items-start justify-center pt-8"
    >
      <div class="bg-gray-900/90 border border-emerald-600/50 rounded-xl px-6 py-3 shadow-lg shadow-emerald-500/20">
        <div class="flex items-center gap-3">
          <div class="text-emerald-400 animate-pulse text-xl">⟳</div>
          <div>
            <div class="text-sm font-bold text-emerald-400">[SYSTEM] Scanning Project</div>
            <div class="text-xs text-gray-400">{{ jobMessage || 'Extracting commit line deltas...' }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Ingestion Progress Overlay -->
    <div
      v-if="isIngestionActive"
      class="fixed inset-0 z-50 bg-gray-950/90 backdrop-blur-sm flex items-center justify-center"
    >
      <div class="bg-gray-900 border border-cyan-600/50 rounded-2xl px-8 py-6 shadow-2xl shadow-cyan-500/20 max-w-md w-full mx-4">
        <div class="flex items-center gap-4 mb-4">
          <div class="text-cyan-400 animate-pulse text-3xl">⟳</div>
          <div>
            <div class="text-lg font-bold text-cyan-400">GitHub Ingestion in Progress</div>
            <div class="text-sm text-gray-400 mt-1">{{ ingestionOverlayMessage || 'Cloning repository...' }}</div>
          </div>
        </div>
        <div class="w-full bg-slate-800 rounded-full h-3 overflow-hidden mb-2">
          <div
            class="bg-cyan-500 h-full transition-all duration-500 ease-out rounded-full"
            :style="{ width: `${ingestionOverlayProgress}%` }"
          ></div>
        </div>
        <div class="flex justify-between text-[11px] text-gray-500">
          <span>{{ ingestionOverlayProgress }}% complete</span>
          <span>Processing repository...</span>
        </div>
      </div>
    </div>

    <!-- Register Project Modal -->
    <div 
      v-if="showRegisterModal" 
      class="fixed inset-0 z-50 bg-gray-950/90 backdrop-blur-sm flex items-center justify-center p-4"
      @click.self="showRegisterModal = false"
    >
      <div class="bg-gray-900 border border-gray-800 rounded-xl p-6 w-full max-w-md">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-lg font-bold text-gray-100">Register New Project</h3>
          <button 
            @click="showRegisterModal = false"
            class="text-gray-400 hover:text-gray-200 transition-colors"
          >
            ✕
          </button>
        </div>

        <div class="space-y-4">
          <!-- Project Name -->
          <div>
            <label class="block text-sm text-gray-300 mb-1">Project Name</label>
            <input 
              v-model="registerForm.name"
              type="text"
              placeholder="my-awesome-project"
              class="w-full rounded-lg bg-gray-950 border border-gray-800 text-white px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500/50"
            />
          </div>

          <!-- Repository Path -->
          <div>
            <label class="block text-sm text-gray-300 mb-1">Repository Path</label>
            <input 
              v-model="registerForm.repoPath"
              type="text"
              placeholder="/home/user/projects/my-repo"
              class="w-full rounded-lg bg-gray-950 border border-gray-800 text-white px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500/50"
            />
            <p class="text-[10px] text-gray-500 mt-1">Must be a valid git repository with .git directory</p>
          </div>

          <!-- Error Message -->
          <div v-if="registerError" class="bg-red-900/20 border border-red-900/50 rounded-lg p-3 text-sm text-red-400">
            {{ registerError }}
          </div>

          <!-- Actions -->
          <div class="flex gap-3 pt-2">
            <button 
              @click="showRegisterModal = false"
              class="flex-1 bg-gray-800 hover:bg-gray-700 text-gray-300 text-sm font-medium py-2 px-4 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button 
              @click="handleRegisterProject"
              :disabled="registerLoading"
              class="flex-1 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 text-white text-sm font-medium py-2 px-4 rounded-lg transition-colors active:scale-95"
            >
              {{ registerLoading ? 'Registering...' : 'Register Project' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
// Authentication check
const workspace = useWorkspaceState()
const { isAuthenticated, activeUser, apiStatus, indexStats } = workspace
const { logout, fetchEngineTelemetry } = workspace

// Data
const qualityFiles = ref<any[]>([])
const traverserData = reactive({ nodes: [], links: [] })
const showInspector = ref(false)
const selectedFile = ref<any>(null)
const isLoading = ref(true)

const focusFilePath = ref('')
const lineagePaths = ref<any[]>([])
const blastRadiusNodes = ref<string[]>([])
const navigatorResult = ref<any>(null)
const navigatorJobId = ref('')

// Workspace Project Management
const selectedProjectId = ref('')
const showRegisterModal = ref(false)
const registerLoading = ref(false)
const registerError = ref('')
const scanLoading = ref(false)
const activeJobId = ref('')
const externalIngestionJobId = ref('')
const jobProgress = ref(0)
const jobMessage = ref('')
let jobPollingInterval: any = null
const registerForm = reactive({
  name: '',
  repoPath: ''
})

// Telemetry data
const telemetryLogs = ref<any[]>([])
const telemetryAggregates = reactive({
  total_input_tokens: 0,
  total_output_tokens: 0,
  total_estimated_cost: 0
})
const telemetryLoading = ref(false)

// Ingestion progress overlay state
const isIngestionActive = ref(false)
const ingestionOverlayProgress = ref(0)
const ingestionOverlayMessage = ref('')
let ingestionOverlayPollingInterval: any = null

// Git Analytics Controls
const gitControls = reactive({
  branches: [] as string[],
  activeBranch: 'main',
  selectedBranch: '',
  commits: [] as any[],
  selectedCommit: '',
  commitLimit: 20,
  loading: false,
  diffData: null as any
})

// Redirect if not authenticated - use nextTick to ensure session is initialized
onMounted(async () => {
    // First, try to initialize session from localStorage
    await workspace.initializeSession()
    
    // Wait a tick for state to update
    await nextTick()

    // Initialize workspace before loading project-specific data
    await workspace.initializeWorkspace()
    selectedProjectId.value = workspace.activeProject.value?.id || ''

    // Fetch initial data after workspace state is restored
    if (!isAuthenticated.value) {
      console.error('[Dashboard] Not authenticated, redirecting to login')
      window.location.href = '/login'
      return
    }

    console.error('[Dashboard] Authenticated, loading dashboard data')
    isLoading.value = false
    
    await fetchEngineTelemetry(workspace.activeProject.value?.id)
    await fetchQualityData()
    await fetchTopologyData()
    await fetchGitBranches()  // Load Git analytics
  })

// Clean up polling intervals on component unmount
onBeforeUnmount(() => {
  stopJobPolling()
  stopIngestionOverlayPolling()
})

// Navigation
const activeTab = ref('dashboard')
const navItems = [
  { id: 'dashboard', label: 'Dashboard Overview', icon: '📊' },
  { id: 'traverser', label: 'Code Traverser Graph', icon: '🌐' },
  { id: 'quality', label: 'Quality Matrix', icon: '🛡️' },
  { id: 'analytics', label: 'Token Telemetry', icon: '📈' },
  { id: 'settings', label: 'Configuration Vault', icon: '⚙️' }
]

const getCurrentTabLabel = computed(() => {
  return navItems.find(item => item.id === activeTab.value)?.label || 'Dashboard'
})

const getCurrentTabDescription = computed(() => {
  const descriptions: Record<string, string> = {
    dashboard: 'System overview and code quality metrics',
    traverser: 'Interactive dependency topology visualization',
    quality: 'File-level quality analysis and smell detection',
    analytics: 'Token usage tracking and cost estimation',
    settings: 'Provider configuration and system settings'
  }
  return descriptions[activeTab.value] || ''
})

// Handlers
function handleLogout() {
  logout()
}

function inspectFile(file: any) {
  selectedFile.value = file
  showInspector.value = true
}

function resetNavigatorState() {
  navigatorResult.value = null
  navigatorJobId.value = ''
  focusFilePath.value = ''
  lineagePaths.value = []
  blastRadiusNodes.value = []
}

function handleNavigatorResult(result: any) {
  navigatorResult.value = result
  focusFilePath.value = ''
  lineagePaths.value = []
  blastRadiusNodes.value = []

  if (!result) {
    return
  }

  if (result.tool === 'blast_radius' && Array.isArray(result.impacted_files)) {
    blastRadiusNodes.value = result.impacted_files.map((item: any) => item.file_path)
  }

  if (result.tool === 'trace_lineage' && Array.isArray(result.paths)) {
    lineagePaths.value = result.paths.map((path: any) => ({
      source: path.source_file || path.source_dataset || '',
      target: path.target_dataset || path.target_file || '',
      direction: result.direction || 'forward'
    })).filter((path: any) => path.source && path.target)
  }
}
function handleIngestionJobStarted(jobId: string) {
  externalIngestionJobId.value = jobId

  // Show the ingestion progress overlay instead of switching tabs immediately
  isIngestionActive.value = true
  ingestionOverlayProgress.value = 0
  ingestionOverlayMessage.value = 'Starting GitHub ingestion...'

  // Start polling the ingestion job status at the index.vue level
  startIngestionOverlayPolling(jobId)
}

function startIngestionOverlayPolling(jobId: string) {
  // Clear any existing overlay polling
  if (ingestionOverlayPollingInterval) {
    clearInterval(ingestionOverlayPollingInterval)
  }

  ingestionOverlayPollingInterval = setInterval(async () => {
    try {
      const response = await fetch('/api/v1/workspace/job-status')
      if (!response.ok) return

      const result = await response.json()

      if (result.success && jobId) {
        const job = result.data.jobs[jobId]

        if (job) {
          ingestionOverlayProgress.value = job.progress || 0
          ingestionOverlayMessage.value = job.message || 'Processing...'

          // Check if job completed or failed
          if (job.status === 'completed') {
            stopIngestionOverlayPolling()
            ingestionOverlayProgress.value = 100
            ingestionOverlayMessage.value = 'Ingestion complete! Switching workspace...'
          } else if (job.status === 'failed') {
            stopIngestionOverlayPolling()
            isIngestionActive.value = false
            console.error('[Dashboard] Ingestion job failed:', job.message)
            alert('❌ Ingestion failed: ' + (job.message || 'Unknown error'))
          }
        }
      }
    } catch (err) {
      console.error('[Dashboard] Error polling ingestion status:', err)
    }
  }, 1000)
}

function stopIngestionOverlayPolling() {
  if (ingestionOverlayPollingInterval) {
    clearInterval(ingestionOverlayPollingInterval)
    ingestionOverlayPollingInterval = null
  }
}

async function handleIngestionCompleted(data: { project_id: string; project_name: string }) {
  if (!data?.project_id) return
  console.error('[Dashboard] Ingestion completed, switching workspace to:', data.project_name, data.project_id)

  // Stop overlay polling (it may already be stopped, but ensure it)
  stopIngestionOverlayPolling()

  // Update overlay to show final state
  ingestionOverlayProgress.value = 100
  ingestionOverlayMessage.value = 'Finalizing workspace...'

  try {
    // Refresh projects list first (new project may have been auto-created)
    await workspace.fetchProjects()

    // Switch workspace to the new project
    selectedProjectId.value = data.project_id
    await workspace.switchProjectWorkspace(data.project_id)

    // Switch to traverser tab
    activeTab.value = 'traverser'

    // Trigger automatic rescan to populate quality_files for topology graph
    // The ingestion clone + initial scan may not fully populate quality_files
    // (especially with shallow clones), so a rescan ensures complete data
    if (workspace.activeProject.value?.id) {
      console.error('[Dashboard] Triggering automatic rescan for:', data.project_name)
      await rescanProject()
    } else {
      // Fallback: just refresh data without rescan
      await fetchEngineTelemetry()
      await fetchQualityData()
      await fetchTopologyData()
      await fetchGitBranches()
    }

    console.error('[Dashboard] Workspace switched to project:', data.project_name)
  } catch (err) {
    console.error('[Dashboard] Failed to switch workspace after ingestion:', err)
  } finally {
    // Dismiss the overlay regardless of success/failure
    isIngestionActive.value = false
  }
}

function focusOnNode(path: string) {
  if (!path) return
  focusFilePath.value = path
}

async function fetchQualityData() {
  try {
    const projectId = workspace.activeProject.value?.id
    const query = projectId ? `?project_id=${projectId}` : ''
    const response = await fetch(`/api/v1/quality${query}`)
    if (!response.ok) throw new Error(`Quality API returned ${response.status}`)
    const data = await response.json()
    if (data.success) {
      qualityFiles.value = data.data
    }
  } catch (err) {
    console.error('[Dashboard] Failed to fetch quality data:', err)
  }
}

async function fetchTopologyData() {
  try {
    const projectId = workspace.activeProject.value?.id
    const query = projectId ? `?project_id=${projectId}` : ''
    const response = await fetch(`/api/v1/topology${query}`)
    if (!response.ok) throw new Error(`Topology API returned ${response.status}`)
    const data = await response.json()
    if (data.success) {
      traverserData.nodes = data.data.nodes
      traverserData.links = data.data.links
    }
  } catch (err) {
    console.error('[Dashboard] Failed to fetch topology data:', err)
  }
}

watch(() => workspace.activeProject.value?.id, () => {
  resetNavigatorState()
})

// Git Analytics Functions
async function fetchGitBranches() {
  try {
    const response = await fetch('/api/v1/git/branches')
    if (!response.ok) throw new Error(`Git branches API returned ${response.status}`)
    const result = await response.json()
    
    if (result.success) {
      gitControls.branches = result.data.branches
      gitControls.activeBranch = result.data.active
      gitControls.selectedBranch = result.data.active
      
      // Fetch commits for active branch
      await fetchGitCommits(result.data.active)
    }
  } catch (err) {
    console.error('[Dashboard] Failed to fetch git branches:', err)
  }
}

async function fetchGitCommits(branch: string) {
  try {
    const response = await fetch(`/api/v1/git/commits?branch=${branch}&limit=${gitControls.commitLimit}`)
    if (!response.ok) throw new Error(`Git commits API returned ${response.status}`)
    const result = await response.json()
    
    if (result.success) {
      gitControls.commits = result.data.commits
    }
  } catch (err) {
    console.error('[Dashboard] Failed to fetch git commits:', err)
  }
}

async function fetchCommitDiff(commitHash: string) {
  try {
    const response = await fetch(`/api/v1/git/diff?commit=${commitHash}`)
    if (!response.ok) throw new Error(`Git diff API returned ${response.status}`)
    const result = await response.json()
    
    if (result.success) {
      gitControls.diffData = result.data
      console.error('[Dashboard] Commit diff loaded:', result.data)
    }
  } catch (err) {
    console.error('[Dashboard] Failed to fetch commit diff:', err)
  }
}

async function onBranchChange() {
  if (gitControls.selectedBranch) {
    console.error('[Dashboard] Branch changed to:', gitControls.selectedBranch)
    await fetchGitCommits(gitControls.selectedBranch)
    gitControls.selectedCommit = ''
    gitControls.diffData = null
  }
}

async function onCommitSelect() {
  if (gitControls.selectedCommit) {
    console.error('[Dashboard] Commit selected:', gitControls.selectedCommit)
    await fetchCommitDiff(gitControls.selectedCommit)
  } else {
    gitControls.diffData = null
  }
}

async function onLimitChange() {
  // Debounce the limit change
  setTimeout(async () => {
    if (gitControls.selectedBranch) {
      await fetchGitCommits(gitControls.selectedBranch)
    }
  }, 300)
}

async function refreshGitData() {
  gitControls.loading = true
  try {
    await fetchGitBranches()
    if (gitControls.selectedCommit) {
      await fetchCommitDiff(gitControls.selectedCommit)
    }
    console.error('[Dashboard] Git data refreshed')
  } catch (err) {
    console.error('[Dashboard] Failed to refresh git data:', err)
  } finally {
    gitControls.loading = false
  }
}

// Workspace Management Functions
async function onProjectChange() {
  resetNavigatorState()

  if (selectedProjectId.value) {
    console.error('[Dashboard] Switching to project:', selectedProjectId.value)
    try {
      await workspace.switchProjectWorkspace(selectedProjectId.value)
      
      // Clear all existing data
      qualityFiles.value = []
      traverserData.nodes = []
      traverserData.links = []
      gitControls.branches = []
      gitControls.commits = []
      gitControls.selectedCommit = ''
      gitControls.diffData = null
      
      // Fetch fresh data for new project
      await fetchEngineTelemetry()
      await fetchQualityData()
      await fetchTopologyData()
      await fetchGitBranches()
      
      console.error('[Dashboard] Workspace switched successfully')
    } catch (err) {
      console.error('[Dashboard] Failed to switch workspace:', err)
    }
  }
}

async function handleRegisterProject() {
  registerError.value = ''
  registerLoading.value = true
  
  try {
    // Validate inputs
    if (!registerForm.name.trim()) {
      registerError.value = 'Project name is required'
      return
    }
    
    if (!registerForm.repoPath.trim()) {
      registerError.value = 'Repository path is required'
      return
    }
    
    // Register project and get the result
    const projectData = await workspace.registerProject(registerForm.name.trim(), registerForm.repoPath.trim())
    
    console.error('[Dashboard] Project registered:', projectData)
    
    // Auto-select the newly registered project
    if (projectData && projectData.id) {
      console.error('[Dashboard] Setting selected project ID:', projectData.id)
      selectedProjectId.value = projectData.id
      
      // Switch to the new project
      console.error('[Dashboard] Calling onProjectChange()...')
      await onProjectChange()
      
      console.error('[Dashboard] Auto-switched to new project:', projectData.name)
      console.error('[Dashboard] Active project after switch:', workspace.activeProject.value)
      
      // Auto-trigger scan to populate database
      if (workspace.activeProject.value && workspace.activeProject.value.id) {
        console.error('[Dashboard] Starting initial project scan...')
        await rescanProject()
        console.error('[Dashboard] Initial scan triggered for:', projectData.name)
      } else {
        console.error('[Dashboard] WARNING: Active project not set after switch, skipping auto-scan')
      }
    }
    
    // Close modal and reset form
    showRegisterModal.value = false
    registerForm.name = ''
    registerForm.repoPath = ''
    
    console.error('[Dashboard] Project registered successfully')
  } catch (err: any) {
    registerError.value = err.message || 'Failed to register project'
    console.error('[Dashboard] Registration failed:', err)
  } finally {
    registerLoading.value = false
  }
}

async function rescanProject() {
  if (!workspace.activeProject.value) {
    console.error('[Dashboard] No active project to rescan')
    alert('No active project selected. Please select a project first.')
    return
  }
  
  if (!workspace.activeProject.value.id) {
    console.error('[Dashboard] Active project has no ID:', workspace.activeProject.value)
    alert('Invalid project state. Please try again.')
    return
  }
  
  console.error('[Dashboard] Rescanning project:', workspace.activeProject.value.id, workspace.activeProject.value.name)
  
  scanLoading.value = true
  activeJobId.value = ''
  jobProgress.value = 0
  jobMessage.value = 'Initializing scan...'
  
  try {
    console.error('[Dashboard] Starting project rescan...')
    
    // Call scan endpoint
    const response = await fetch('/api/v1/workspace/scan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_id: workspace.activeProject.value.id
      })
    })
    
    if (!response.ok) {
      throw new Error(`Scan API returned ${response.status}`)
    }
    
    const result = await response.json()
    
    if (result.success) {
      activeJobId.value = result.data.job_id
      console.error('[Dashboard] Scan job started:', result.data.job_id)
      
      // Start polling for job status
      startJobPolling()
    } else {
      throw new Error(result.error || 'Failed to start scan')
    }
  } catch (err: any) {
    console.error('[Dashboard] Scan failed:', err)
    alert('Failed to scan project: ' + (err.message || 'Unknown error'))
    scanLoading.value = false
  }
}

async function deleteProject() {
  if (!workspace.activeProject.value) {
    alert('No project selected')
    return
  }
  
  const projectName = workspace.activeProject.value.name
  const confirmed = confirm(`Are you sure you want to delete "${projectName}"?\n\nThis will remove:\n- Project configuration\n- All scan data\n- Git history\n- File analysis\n\nThis action cannot be undone.`)
  
  if (!confirmed) {
    return
  }
  
  try {
    console.error('[Dashboard] Deleting project:', workspace.activeProject.value.id)
    
    const response = await fetch(`/api/v1/projects/${workspace.activeProject.value.id}`, {
      method: 'DELETE'
    })
    
    const result = await response.json()
    
    if (result.success) {
      console.error('[Dashboard] Project deleted:', projectName)
      
      // Clear active project and selected ID
      workspace.activeProject.value = null
      selectedProjectId.value = ''
      
      // Clear all displayed data
      qualityFiles.value = []
      traverserData.nodes = []
      traverserData.links = []
      gitControls.branches = []
      gitControls.commits = []
      gitControls.selectedCommit = ''
      gitControls.diffData = null
      
      // Refresh project list
      await workspace.fetchProjects()
      
      alert(result.message || 'Project deleted successfully')
    } else {
      throw new Error(result.error || 'Failed to delete project')
    }
  } catch (err: any) {
    console.error('[Dashboard] Delete failed:', err)
    alert('Failed to delete project: ' + (err.message || 'Unknown error'))
  }
}

function startJobPolling() {
  // Clear any existing polling
  if (jobPollingInterval) {
    clearInterval(jobPollingInterval)
  }
  
  // Poll every 800ms
  jobPollingInterval = setInterval(async () => {
    try {
      const response = await fetch('/api/v1/workspace/job-status')
      if (!response.ok) return
      
      const result = await response.json()
      
      if (result.success && activeJobId.value) {
        const job = result.data.jobs[activeJobId.value]
        
        if (job) {
          jobProgress.value = job.progress || 0
          jobMessage.value = job.message || ''
          
          console.error(`[Dashboard] Job ${activeJobId.value}: ${job.status} - ${job.progress}% - ${job.message}`)
          
          // Check if job completed or failed
          if (job.status === 'completed') {
            stopJobPolling()
            scanLoading.value = false
            
            console.error('[Dashboard] Scan completed!')
            
            // Refresh all data
            await fetchEngineTelemetry()
            await fetchQualityData()
            await fetchTopologyData()
            await fetchGitBranches()
            
            alert('✅ Project scan completed successfully!')
          } else if (job.status === 'failed') {
            stopJobPolling()
            scanLoading.value = false
            
            console.error('[Dashboard] Scan failed:', job.message)
            alert('❌ Scan failed: ' + job.message)
          }
        }
      }
    } catch (err) {
      console.error('[Dashboard] Error polling job status:', err)
    }
  }, 800)
}

function stopJobPolling() {
  if (jobPollingInterval) {
    clearInterval(jobPollingInterval)
    jobPollingInterval = null
  }
}

function resetWorkspace() {
  resetNavigatorState()

  // Clear all workspace state
  selectedProjectId.value = ''
  activeJobId.value = ''
  jobProgress.value = 0
  jobMessage.value = ''
  scanLoading.value = false
  
  // Clear active project
  workspace.activeProject.value = null
  
  // Clear all data
  qualityFiles.value = []
  traverserData.nodes = []
  traverserData.links = []
  gitControls.branches = []
  gitControls.commits = []
  gitControls.selectedCommit = ''
  gitControls.diffData = null
  
  // Reset stats
  workspace.indexStats.files = 0
  workspace.indexStats.deps = 0
  workspace.indexStats.languages = 0
  workspace.indexStats.symbols = 0
  
  // Stop any polling
  stopJobPolling()
  stopIngestionOverlayPolling()
  isIngestionActive.value = false
  
  // Refresh projects list
  workspace.fetchProjects()
  
  console.error('[Dashboard] Workspace reset complete')
}

// Telemetry functions
async function fetchTelemetryData() {
  telemetryLoading.value = true
  try {
    const projectId = workspace.activeProject.value?.id
    const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : ''
    const response = await fetch(`/api/v1/telemetry${query}`)
    if (!response.ok) throw new Error(`Telemetry API returned ${response.status}`)

    const result = await response.json()
    if (result.success) {
      telemetryLogs.value = result.data.logs || []
      telemetryAggregates.total_input_tokens = result.data.aggregates?.total_input_tokens || 0
      telemetryAggregates.total_output_tokens = result.data.aggregates?.total_output_tokens || 0
      telemetryAggregates.total_estimated_cost = result.data.aggregates?.total_estimated_cost || 0
    }
  } catch (err) {
    console.error('[Dashboard] Failed to fetch telemetry:', err)
  } finally {
    telemetryLoading.value = false
  }
}

function formatTelemetryTime(dateStr: string | undefined): string {
  if (!dateStr) return ''
  try {
    const d = new Date(dateStr)
    const now = new Date()
    const diff = Math.floor((now.getTime() - d.getTime()) / 1000)
    if (diff < 60) return 'just now'
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
    return d.toLocaleDateString()
  } catch {
    return dateStr || ''
  }
}

// Watch tab changes to refresh telemetry when analytics tab is selected
watch(activeTab, (newTab) => {
  if (newTab === 'analytics') {
    fetchTelemetryData()
  }
})

// Also watch project changes to refresh telemetry
watch(() => workspace.activeProject.value?.id, () => {
  if (activeTab.value === 'analytics') {
    fetchTelemetryData()
  }
})
</script>
