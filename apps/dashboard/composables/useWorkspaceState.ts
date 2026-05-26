// Centralized workspace state management for authentication and session
import { ref, reactive } from 'vue'

export function useWorkspaceState() {
  // Authentication state
  const isAuthenticated = ref(false)
  const authPage = ref('login')
  const activeUser = ref('')
  const authError = ref('')
  const apiStatus = ref('connecting') // 'connecting', 'connected', 'error'

  // Dashboard stats
  const indexStats = reactive({ 
    files: 0, 
    deps: 0, 
    languages: 0, 
    symbols: 0 
  })

  // Workspace project tracking
  const projectsList = ref<any[]>([])
  const activeProject = ref<any>(null)
  const isSwitchingWorkspace = ref(false)

  // Form data
  const loginForm = reactive({ username: '', password: '' })
  const registerForm = reactive({ username: '', password: '', confirmPassword: '' })

  // Initialize from localStorage with graceful error handling
  function initializeSession() {
    try {
      if (import.meta.client) {
        const cachedUser = localStorage.getItem('wikihub_user')
        if (cachedUser && typeof cachedUser === 'string' && cachedUser.trim()) {
          activeUser.value = cachedUser.trim()
          isAuthenticated.value = true
          return true
        }
      }
    } catch (err) {
      console.error('[Workspace] Session restoration failed, clearing corrupt data:', err)
      try {
        if (import.meta.client) {
          localStorage.removeItem('wikihub_user')
        }
      } catch (cleanupErr) {
        console.error('[Workspace] Cleanup failed:', cleanupErr)
      }
      // Force redirect to login
      if (import.meta.client) {
        window.location.href = '/login'
      }
    }
    return false
  }

  // Login handler
  async function login(username: string, password: string) {
    const trimmedUsername = username.trim()
    
    if (!trimmedUsername || password.length < 8) {
      authError.value = 'Invalid local credential configuration parameters.'
      return false
    }

    try {
      if (import.meta.client) {
        localStorage.setItem('wikihub_user', trimmedUsername)
      }
      activeUser.value = trimmedUsername
      isAuthenticated.value = true
      authError.value = ''
      return true
    } catch (err) {
      console.error('[Workspace] Login failed:', err)
      authError.value = 'Session storage error. Please try again.'
      return false
    }
  }

  // Register handler
  async function register(username: string, password: string, confirmPassword: string) {
    const trimmedUsername = username.trim()
    
    if (!trimmedUsername) {
      authError.value = 'Username cannot be empty or whitespace-only.'
      return false
    }
    if (trimmedUsername.length < 3) {
      authError.value = 'Username must be at least 3 characters.'
      return false
    }
    if (password.length < 8) {
      authError.value = 'Local master key must contain 8 or more characters.'
      return false
    }
    if (password !== confirmPassword) {
      authError.value = 'Master configuration confirmation matching failed.'
      return false
    }

    try {
      if (import.meta.client) {
        localStorage.setItem('wikihub_user', trimmedUsername)
      }
      activeUser.value = trimmedUsername
      isAuthenticated.value = true
      authError.value = ''
      return true
    } catch (err) {
      console.error('[Workspace] Registration failed:', err)
      authError.value = 'Session storage error. Please try again.'
      return false
    }
  }

  // Logout handler
  function logout() {
    try {
      if (import.meta.client) {
        localStorage.removeItem('wikihub_user')
      }
    } catch (err) {
      console.error('[Workspace] Logout cleanup failed:', err)
    }
    
    isAuthenticated.value = false
    authPage.value = 'login'
    activeUser.value = ''
    loginForm.username = ''
    loginForm.password = ''
    
    if (import.meta.client) {
      window.location.href = '/login'
    }
  }

  // Navigation helpers
  function switchToLogin() {
    authPage.value = 'login'
    authError.value = ''
  }

  function switchToRegister() {
    authPage.value = 'register'
    authError.value = ''
  }

  // Fetch telemetry from API
  async function fetchEngineTelemetry(projectId?: string) {
    try {
      const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : ''
      const statsResponse = await fetch(`/api/v1/stats${query}`)
      if (!statsResponse.ok) throw new Error(`Stats API returned ${statsResponse.status}`)
      const statsData = await statsResponse.json()
      
      if (statsData.success) {
        indexStats.files = statsData.data.files
        indexStats.deps = statsData.data.dependencies
        indexStats.languages = statsData.data.languages
        indexStats.symbols = statsData.data.symbols
      }

      apiStatus.value = 'connected'
      console.error('[Workspace] Successfully fetched telemetry from hub.db')
      return statsData
    } catch (err) {
      console.error('[Workspace] Failed to fetch telemetry:', err.message)
      apiStatus.value = 'error'
      return null
    }
  }

  // Workspace Management Functions
  async function fetchProjects() {
    try {
      const response = await fetch('/api/v1/projects')
      if (!response.ok) throw new Error(`Projects API returned ${response.status}`)
      const result = await response.json()
      
      if (result.success) {
        projectsList.value = result.data.projects
        console.error(`[Workspace] Loaded ${result.data.count} projects`)
      }
    } catch (err) {
      console.error('[Workspace] Failed to fetch projects:', err)
    }
  }

  async function registerProject(name: string, repoPath: string) {
    try {
      const response = await fetch('/api/v1/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, repo_path: repoPath })
      })
      
      const result = await response.json()
      
      if (result.success) {
        console.error(`[Workspace] Project registered: ${name}`)
        await fetchProjects() // Refresh list
        return result.data
      } else {
        throw new Error(result.error)
      }
    } catch (err) {
      console.error('[Workspace] Failed to register project:', err)
      throw err
    }
  }

  async function switchProjectWorkspace(projectId: string) {
    isSwitchingWorkspace.value = true
    
    try {
      // Notify backend of context shift
      const response = await fetch('/api/v1/workspace/select', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_id: projectId })
      })
      
      const result = await response.json()
      
      if (result.success) {
        activeProject.value = result.data
        console.error(`[Workspace] Switched to: ${result.data.name}`)
        
        // Clear existing graph state
        indexStats.files = 0
        indexStats.deps = 0
        indexStats.languages = 0
        indexStats.symbols = 0
        
        // Re-fetch telemetry for new project
        await fetchEngineTelemetry(projectId)
        
        return true
      } else {
        throw new Error(result.error)
      }
    } catch (err) {
      console.error('[Workspace] Failed to switch workspace:', err)
      throw err
    } finally {
      isSwitchingWorkspace.value = false
    }
  }

  async function initializeWorkspace() {
    try {
      // Load projects list
      await fetchProjects()
      
      // Get active workspace
      const response = await fetch('/api/v1/workspace/active')
      if (response.ok) {
        const result = await response.json()
        if (result.success && result.data.id) {
          activeProject.value = result.data
          console.error(`[Workspace] Restored active project: ${result.data.name}`)
        }
      }
    } catch (err) {
      console.error('[Workspace] Failed to initialize workspace:', err)
    }
  }

  return {
    // State
    isAuthenticated,
    authPage,
    activeUser,
    authError,
    apiStatus,
    indexStats,
    loginForm,
    registerForm,
    projectsList,
    activeProject,
    isSwitchingWorkspace,
    
    // Methods
    initializeSession,
    login,
    register,
    logout,
    switchToLogin,
    switchToRegister,
    fetchEngineTelemetry,
    fetchProjects,
    registerProject,
    switchProjectWorkspace,
    initializeWorkspace
  }
}
