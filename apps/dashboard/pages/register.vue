<template>
  <div class="min-h-screen bg-gray-950 flex items-center justify-center p-4">
    <div class="w-full max-w-md">
      <!-- Logo -->
      <div class="text-center mb-8">
        <div class="inline-flex items-center justify-center w-16 h-16 bg-blue-600/10 border border-blue-500/20 rounded-2xl mb-4">
          <span class="text-2xl">👤</span>
        </div>
        <h1 class="text-2xl font-bold text-gray-100 mb-2">Create Workspace</h1>
        <p class="text-gray-400">Register for local developer access</p>
      </div>

      <!-- Register Form -->
      <div class="bg-gray-900 border border-gray-800 rounded-2xl p-6 space-y-4">
        <h2 class="text-lg font-semibold text-gray-100">Register</h2>

        <!-- Error Message -->
        <div v-if="authError" class="bg-error/10 border border-error/20 rounded-lg p-3 text-sm text-error">
          {{ authError }}
        </div>

        <CustomInput
          v-model="registerForm.username"
          label="Username"
          placeholder="Choose a username (min 3 chars)"
          type="text"
        />

        <CustomInput
          v-model="registerForm.password"
          label="Password"
          placeholder="Create password (min 8 chars)"
          type="password"
        />

        <CustomInput
          v-model="registerForm.confirmPassword"
          label="Confirm Password"
          placeholder="Confirm your password"
          type="password"
        />

        <button
          @click="handleRegister"
          class="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-lg transition-colors active:scale-95"
        >
          Create Workspace
        </button>

        <div class="text-center text-sm text-gray-400">
          Already have an account?
          <button @click="switchToLogin" class="text-blue-400 hover:text-blue-300 transition-colors">
            Sign in
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const workspace = useWorkspaceState()

const { authError, registerForm, isAuthenticated } = workspace
const { register, switchToLogin } = workspace

// If already authenticated, redirect to dashboard
onMounted(() => {
  // Try to restore session first
  workspace.initializeSession()
  
  // Check if now authenticated
  if (isAuthenticated.value) {
    console.error('[Register] Already authenticated, redirecting to dashboard')
    window.location.href = '/'
  }
})

async function handleRegister() {
  const success = await register(
    registerForm.username,
    registerForm.password,
    registerForm.confirmPassword
  )
  if (success) {
    window.location.href = '/'
  }
}
</script>
