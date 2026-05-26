<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="bg-gradient-to-b from-gray-900 to-gray-950 border border-gray-800 rounded-xl p-6">
      <h2 class="text-xl font-bold text-gray-100 mb-2">Configuration Vault</h2>
      <p class="text-gray-400 text-sm">Manage API providers, model routing, and system settings</p>
    </div>

    <!-- Provider Configuration -->
    <div class="bg-gray-900 border border-gray-800 rounded-xl p-6">
      <h3 class="text-lg font-semibold text-gray-100 mb-4">LLM Provider Settings</h3>
      
      <div class="space-y-4">
        <!-- OpenRouter -->
        <div class="bg-gray-950 border border-gray-800 rounded-lg p-4">
          <div class="flex items-center justify-between mb-3">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 bg-blue-600/10 border border-blue-500/20 rounded-lg flex items-center justify-center">
                <span class="text-lg">🌐</span>
              </div>
              <div>
                <div class="text-sm font-medium text-gray-100">OpenRouter</div>
                <div class="text-xs text-gray-500">Multi-model aggregation</div>
              </div>
            </div>
            <MetricBadge :label="providerStatus.openrouter ? 'Connected' : 'Not Configured'" :variant="providerStatus.openrouter ? 'isolated' : 'medium'" size="sm" />
          </div>
          
          <CustomInput
            v-model="providers.openrouter.apiKey"
            type="password"
            label="API Key"
            placeholder="sk-or-v1-..."
          />
          
          <!-- Model Selector -->
          <div class="mt-3">
            <ModelSelector v-model="providers.openrouter.defaultModel" />
          </div>
          
          <div class="mt-3 flex gap-2">
            <button 
              @click="saveProvider('openrouter')"
              class="bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium py-1.5 px-4 rounded-lg transition-colors active:scale-95"
            >
              Save Configuration
            </button>
            <button 
              @click="testProvider('openrouter')"
              class="bg-gray-800 hover:bg-gray-700 text-gray-300 text-sm font-medium py-1.5 px-4 rounded-lg transition-colors active:scale-95"
            >
              Test Connection
            </button>
          </div>
        </div>

        <!-- Gemini -->
        <div class="bg-gray-950 border border-gray-800 rounded-lg p-4">
          <div class="flex items-center justify-between mb-3">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 bg-purple-600/10 border border-purple-500/20 rounded-lg flex items-center justify-center">
                <span class="text-lg">💎</span>
              </div>
              <div>
                <div class="text-sm font-medium text-gray-100">Google Gemini</div>
                <div class="text-xs text-gray-500">Gemini Pro / Ultra</div>
              </div>
            </div>
            <MetricBadge :label="providerStatus.gemini ? 'Connected' : 'Not Configured'" :variant="providerStatus.gemini ? 'isolated' : 'medium'" size="sm" />
          </div>
          
          <CustomInput
            v-model="providers.gemini.apiKey"
            type="password"
            label="API Key"
            placeholder="AIza..."
          />
          
          <div class="mt-3 flex gap-2">
            <button 
              @click="saveProvider('gemini')"
              class="bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium py-1.5 px-4 rounded-lg transition-colors active:scale-95"
            >
              Save Configuration
            </button>
            <button 
              @click="testProvider('gemini')"
              class="bg-gray-800 hover:bg-gray-700 text-gray-300 text-sm font-medium py-1.5 px-4 rounded-lg transition-colors active:scale-95"
            >
              Test Connection
            </button>
          </div>
        </div>

        <!-- DeepSeek -->
        <div class="bg-gray-950 border border-gray-800 rounded-lg p-4">
          <div class="flex items-center justify-between mb-3">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 bg-cyan-600/10 border border-cyan-500/20 rounded-lg flex items-center justify-center">
                <span class="text-lg">🔍</span>
              </div>
              <div>
                <div class="text-sm font-medium text-gray-100">DeepSeek</div>
                <div class="text-xs text-gray-500">DeepSeek Coder / Chat</div>
              </div>
            </div>
            <MetricBadge :label="providerStatus.deepseek ? 'Connected' : 'Not Configured'" :variant="providerStatus.deepseek ? 'isolated' : 'medium'" size="sm" />
          </div>
          
          <CustomInput
            v-model="providers.deepseek.apiKey"
            type="password"
            label="API Key"
            placeholder="sk-..."
          />
          
          <div class="mt-3 flex gap-2">
            <button 
              @click="saveProvider('deepseek')"
              class="bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium py-1.5 px-4 rounded-lg transition-colors active:scale-95"
            >
              Save Configuration
            </button>
            <button 
              @click="testProvider('deepseek')"
              class="bg-gray-800 hover:bg-gray-700 text-gray-300 text-sm font-medium py-1.5 px-4 rounded-lg transition-colors active:scale-95"
            >
              Test Connection
            </button>
          </div>
        </div>

        <!-- Qwen -->
        <div class="bg-gray-950 border border-gray-800 rounded-lg p-4">
          <div class="flex items-center justify-between mb-3">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 bg-yellow-600/10 border border-yellow-500/20 rounded-lg flex items-center justify-center">
                <span class="text-lg">⚡</span>
              </div>
              <div>
                <div class="text-sm font-medium text-gray-100">Qwen (Alibaba)</div>
                <div class="text-xs text-gray-500">Qwen-Max / Qwen-Plus</div>
              </div>
            </div>
            <MetricBadge :label="providerStatus.qwen ? 'Connected' : 'Not Configured'" :variant="providerStatus.qwen ? 'isolated' : 'medium'" size="sm" />
          </div>
          
          <CustomInput
            v-model="providers.qwen.apiKey"
            type="password"
            label="API Key"
            placeholder="sk-..."
          />
          
          <div class="mt-3 flex gap-2">
            <button 
              @click="saveProvider('qwen')"
              class="bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium py-1.5 px-4 rounded-lg transition-colors active:scale-95"
            >
              Save Configuration
            </button>
            <button 
              @click="testProvider('qwen')"
              class="bg-gray-800 hover:bg-gray-700 text-gray-300 text-sm font-medium py-1.5 px-4 rounded-lg transition-colors active:scale-95"
            >
              Test Connection
            </button>
          </div>
        </div>
      </div>
    </div>

    <GitHubIngestionPanel
      :project-id="projectId"
      @ingestion-started="emit('ingestion-started', $event)"
      @ingestion-completed="emit('ingestion-completed', $event)"
      @error="githubError = $event"
    />

    <div v-if="githubError" class="mt-4 rounded-xl bg-rose-950 border border-rose-500/20 p-3 text-sm text-rose-200 font-mono whitespace-pre-wrap">
      {{ githubError }}
    </div>

    <!-- System Settings -->
    <div class="bg-gray-900 border border-gray-800 rounded-xl p-6">
      <h3 class="text-lg font-semibold text-gray-100 mb-4">System Settings</h3>
      
      <div class="space-y-4">
        <!-- Default Model -->
        <div class="bg-gray-950 border border-gray-800 rounded-lg p-4">
          <label class="block text-sm font-medium text-gray-300 mb-2">Default Model</label>
          <select 
            v-model="systemSettings.defaultModel"
            class="w-full rounded-lg bg-gray-900 border border-gray-800 text-white px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-500/50 focus:border-blue-500 transition-colors"
          >
            <option value="">Select a model...</option>
            <option value="openrouter/gpt-4">GPT-4 (via OpenRouter)</option>
            <option value="openrouter/claude-3">Claude 3 (via OpenRouter)</option>
            <option value="gemini/gemini-pro">Gemini Pro</option>
            <option value="deepseek/deepseek-coder">DeepSeek Coder</option>
            <option value="qwen/qwen-max">Qwen-Max</option>
          </select>
        </div>

        <!-- Token Budget -->
        <div class="bg-gray-950 border border-gray-800 rounded-lg p-4">
          <CustomInput
            v-model="systemSettings.tokenBudget"
            type="text"
            label="Monthly Token Budget"
            placeholder="100000"
          />
          <p class="text-xs text-gray-500 mt-2">Maximum tokens per month before alerts are triggered</p>
        </div>

        <!-- Save Settings -->
        <button 
          @click="saveSystemSettings"
          class="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-lg transition-colors active:scale-95"
        >
          Save System Settings
        </button>
      </div>
    </div>

    <!-- Danger Zone -->
    <div class="bg-error/5 border border-error/20 rounded-xl p-6">
      <h3 class="text-lg font-semibold text-error mb-4">Danger Zone</h3>
      
      <div class="space-y-3">
        <button 
          @click="clearAllSettings"
          class="w-full bg-error/10 hover:bg-error/20 border border-error/30 text-error font-medium py-2 px-4 rounded-lg transition-colors active:scale-95"
        >
          Clear All Provider Configurations
        </button>
        <button 
          @click="resetDatabase"
          class="w-full bg-error/10 hover:bg-error/20 border border-error/30 text-error font-medium py-2 px-4 rounded-lg transition-colors active:scale-95"
        >
          Reset Codebase Database (hub.db)
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import ModelSelector from '../config/ModelSelector.vue'
import GitHubIngestionPanel from './GitHubIngestionPanel.vue'
const emit = defineEmits(['ingestion-started', 'ingestion-completed'])
const providers = reactive({
  openrouter: { apiKey: '', defaultModel: '' },
  gemini: { apiKey: '' },
  deepseek: { apiKey: '' },
  qwen: { apiKey: '' }
})

const providerStatus = reactive({
  openrouter: false,
  gemini: false,
  deepseek: false,
  qwen: false
})

const systemSettings = reactive({
  defaultModel: '',
  tokenBudget: '100000'
})

const projectId = ref<string | null>(null)
const githubError = ref('')

// Load saved configurations on mount
onMounted(() => {
  loadProviderConfigs()
  fetchActiveWorkspace()
})

async function fetchActiveWorkspace() {
  try {
    const response = await fetch('/api/v1/workspace/active')
    if (!response.ok) return
    const payload = await response.json()
    if (payload.success && payload.data && payload.data.id) {
      projectId.value = payload.data.id
    }
  } catch (err) {
    console.error('[Settings] Failed to load active workspace', err)
  }
}

async function loadProviderConfigs() {
  try {
    const response = await fetch('/api/v1/config')
    if (!response.ok) throw new Error(`Config API returned ${response.status}`)
    const result = await response.json()
    
    if (result.success && result.data) {
      const config = result.data
      
      // Load provider API keys
      if (config.providers) {
        providers.openrouter.apiKey = config.providers.openrouter?.apiKey || ''
        providers.openrouter.defaultModel = config.providers.openrouter?.defaultModel || ''
        providers.gemini.apiKey = config.providers.gemini?.apiKey || ''
        providers.deepseek.apiKey = config.providers.deepseek?.apiKey || ''
        providers.qwen.apiKey = config.providers.qwen?.apiKey || ''
        
        // Update status
        providerStatus.openrouter = !!providers.openrouter.apiKey
        providerStatus.gemini = !!providers.gemini.apiKey
        providerStatus.deepseek = !!providers.deepseek.apiKey
        providerStatus.qwen = !!providers.qwen.apiKey
      }
      
      // Load system settings
      if (config.system) {
        systemSettings.defaultModel = config.system.defaultModel || ''
        systemSettings.tokenBudget = config.system.tokenBudget?.toString() || '100000'
      }
    }
  } catch (err) {
    console.error('[Settings] Failed to load config from backend:', err)
    // Fallback to localStorage
    loadFromLocalStorage()
  }
}

function loadFromLocalStorage() {
  try {
    if (import.meta.client) {
      // Load from localStorage
      const saved = localStorage.getItem('wikihub_providers')
      if (saved) {
        const parsed = JSON.parse(saved)
        Object.assign(providers, parsed)
        
        // Mark configured providers
        providerStatus.openrouter = !!providers.openrouter.apiKey
        providerStatus.gemini = !!providers.gemini.apiKey
        providerStatus.deepseek = !!providers.deepseek.apiKey
        providerStatus.qwen = !!providers.qwen.apiKey
      }
      
      // Load system settings
      const settings = localStorage.getItem('wikihub_settings')
      if (settings) {
        Object.assign(systemSettings, JSON.parse(settings))
      }
    }
  } catch (err) {
    console.error('[Settings] Failed to load from localStorage:', err)
  }
}

async function saveProvider(provider: string) {
  try {
    // Save to backend
    const config = {
      providers: {
        openrouter: { 
          apiKey: providers.openrouter.apiKey, 
          defaultModel: providers.openrouter.defaultModel,
          status: providers.openrouter.apiKey ? 'configured' : 'not_configured' 
        },
        gemini: { apiKey: providers.gemini.apiKey, status: providers.gemini.apiKey ? 'configured' : 'not_configured' },
        deepseek: { apiKey: providers.deepseek.apiKey, status: providers.deepseek.apiKey ? 'configured' : 'not_configured' },
        qwen: { apiKey: providers.qwen.apiKey, status: providers.qwen.apiKey ? 'configured' : 'not_configured' }
      },
      system: {
        defaultModel: systemSettings.defaultModel,
        tokenBudget: parseInt(systemSettings.tokenBudget) || 100000
      }
    }
    
    const response = await fetch('/api/v1/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config)
    })
    
    if (!response.ok) throw new Error(`Save failed: ${response.status}`)
    
    // Also save to localStorage as backup
    if (import.meta.client) {
      localStorage.setItem('wikihub_providers', JSON.stringify(providers))
    }
    
    providerStatus[provider as keyof typeof providerStatus] = !!providers[provider as keyof typeof providers].apiKey
    console.error(`[Settings] ${provider} configuration saved`)
  } catch (err) {
    console.error(`[Settings] Failed to save ${provider}:`, err)
  }
}

async function testProvider(provider: string) {
  const apiKey = (providers as any)[provider]?.apiKey
  if (!apiKey) {
    alert(`Please enter an API key for ${provider} before testing.`)
    return
  }

  console.error(`[Settings] Testing ${provider} connection...`)
  try {
    const response = await fetch('/api/v1/config/test-connection', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider, api_key: apiKey })
    })

    const result = await response.json()
    if (result.success) {
      providerStatus[provider as keyof typeof providerStatus] = true
      alert(`✓ ${provider}: ${result.message}`)
    } else {
      providerStatus[provider as keyof typeof providerStatus] = false
      alert(`✗ ${provider}: ${result.error || 'Connection test failed'}`)
    }
  } catch (err: any) {
    console.error(`[Settings] ${provider} test failed:`, err)
    alert(`✗ ${provider}: ${err?.message || 'Network error during test'}`)
  }
}

async function saveSystemSettings() {
  try {
    const config = {
      providers: {
        openrouter: { apiKey: providers.openrouter.apiKey, status: providers.openrouter.apiKey ? 'configured' : 'not_configured' },
        gemini: { apiKey: providers.gemini.apiKey, status: providers.gemini.apiKey ? 'configured' : 'not_configured' },
        deepseek: { apiKey: providers.deepseek.apiKey, status: providers.deepseek.apiKey ? 'configured' : 'not_configured' },
        qwen: { apiKey: providers.qwen.apiKey, status: providers.qwen.apiKey ? 'configured' : 'not_configured' }
      },
      system: {
        defaultModel: systemSettings.defaultModel,
        tokenBudget: parseInt(systemSettings.tokenBudget) || 100000
      }
    }

    const response = await fetch('/api/v1/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config)
    })

    if (!response.ok) throw new Error(`Save failed: ${response.status}`)

    if (import.meta.client) {
      localStorage.setItem('wikihub_settings', JSON.stringify(systemSettings))
    }

    console.error('[Settings] System settings saved')
  } catch (err) {
    console.error('[Settings] Failed to save system settings:', err)
  }
}

function clearAllSettings() {
  if (confirm('Are you sure you want to clear all provider configurations?')) {
    try {
      if (import.meta.client) {
        localStorage.removeItem('wikihub_providers')
        Object.keys(providers).forEach(key => {
          (providers as any)[key].apiKey = ''
          providerStatus[key as keyof typeof providerStatus] = false
        })
        console.error('[Settings] All provider configurations cleared')
      }
    } catch (err) {
      console.error('[Settings] Failed to clear settings:', err)
    }
  }
}

function resetDatabase() {
  if (confirm('WARNING: This will delete all indexed codebase data. Are you sure?')) {
    console.error('[Settings] Database reset requested (not yet implemented)')
    alert('Database reset not yet implemented')
  }
}
</script>
