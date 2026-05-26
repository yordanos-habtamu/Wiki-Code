<template>
  <div class="model-selector">
    <label class="block text-sm font-medium text-gray-300 mb-2">Model Selector</label>

    <div class="flex gap-2 mb-2">
      <input
        v-model="search"
        placeholder="Search models (name or id)"
        class="flex-1 rounded-lg bg-gray-900 border border-gray-800 text-white px-3 py-2 focus:outline-none"
      />
      <button @click="refresh" class="bg-gray-800 text-gray-200 px-3 py-2 rounded-lg">Refresh</button>
    </div>

    <div ref="listRef" @scroll="onScroll" class="max-h-56 overflow-auto border border-gray-800 rounded-lg p-2 bg-gray-950">
      <div v-if="loading" class="text-gray-400 text-sm">Loading models...</div>
      <div v-else-if="error" class="text-red-400 text-sm">{{ error }}</div>
      <ul v-else class="space-y-1">
        <li v-for="m in filtered" :key="m.id">
          <button
            @click="selectModel(m)"
            :class="['w-full text-left px-3 py-2 rounded-lg', selected === m.id ? 'bg-blue-600 text-white' : 'text-gray-200 hover:bg-gray-900']"
          >
            <div class="flex items-center justify-between">
              <div class="truncate">
                <div class="text-sm font-medium truncate">{{ m.name }}</div>
                <div class="text-xs text-gray-500 truncate">{{ m.id }}</div>
              </div>
              <div class="text-xs text-gray-400">{{ m.context_length || '-' }}</div>
            </div>
          </button>
        </li>
      </ul>
      <div v-if="!loading && filtered.length === 0" class="text-gray-500 text-sm">No models match your search.</div>
    </div>

    <div class="mt-3 flex items-center gap-2">
      <div class="flex-1 text-sm text-gray-300">Selected: <span class="text-gray-100">{{ selected || '—' }}</span></div>
      <button @click="save" :disabled="!canSave" class="bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium py-1.5 px-4 rounded-lg">Save to Project</button>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, computed, onMounted, watch } from 'vue'

export default defineComponent({
  name: 'ModelSelector',
  props: {
    modelValue: { type: String, default: '' }
  },
  emits: ['update:modelValue'],
  setup(props, { emit }) {
    const rawModels = ref<Array<any>>([])
    const loading = ref(false)
    const error = ref('')
    const search = ref('')
    const selected = ref(props.modelValue || '')
    const projectId = ref<string | null>(null)
    const page = ref(1)
    const limit = ref(40)
    const hasMore = ref(true)
    const fetching = ref(false)
    const displayLimit = ref(20)
    const listRef = ref<HTMLElement | null>(null)

    watch(() => props.modelValue, (v) => { selected.value = v || '' })

    onMounted(async () => {
      await fetchActiveWorkspace()
      await resetAndLoad()
    })

    async function fetchActiveWorkspace() {
      try {
        const resp = await fetch('/api/v1/workspace/active')
        if (!resp.ok) return
        const body = await resp.json()
        if (body && body.success && body.data && body.data.id) {
          projectId.value = body.data.id
        }
      } catch (err) {
        console.error('ModelSelector: failed to fetch workspace', err)
      }
    }

    async function loadPage(p: number) {
      fetching.value = true
      error.value = ''
      try {
        const resp = await fetch(`/api/v1/config/models?page=${p}&limit=${limit.value}`)
        if (!resp.ok) throw new Error(`Status ${resp.status}`)
        const body = await resp.json()
        if (body.success && body.data) {
          const payload = body.data
          // append models (mutate existing array to avoid reallocation in hot paths)
          for (const m of (payload.models || [])) rawModels.value.push(m)
          hasMore.value = !!payload.has_more
          page.value = payload.page || p
        } else {
          error.value = body.error || 'Failed to load models'
        }
      } catch (err: any) {
        error.value = err.message || String(err)
      } finally {
        fetching.value = false
        loading.value = false
      }
    }

    async function resetAndLoad() {
      loading.value = true
      rawModels.value.length = 0
      page.value = 1
      hasMore.value = true
      displayLimit.value = 20
      await loadPage(1)
    }

    function refresh() { resetAndLoad() }

    const filtered = computed(() => {
      const list = rawModels.value
      if (!search.value) return list.slice(0, displayLimit.value)
      const q = search.value.toLowerCase()
      // perform simple filter over current items
      const out: any[] = []
      for (let i = 0; i < list.length; i++) {
        const m = list[i]
        if (((m.name || '').toLowerCase().includes(q)) || ((m.id || '').toLowerCase().includes(q))) {
          out.push(m)
        }
        if (out.length >= displayLimit.value) break
      }
      return out
    })

    function selectModel(m: any) {
      selected.value = m.id
      emit('update:modelValue', selected.value)
    }

    async function loadNextIfNeeded() {
      if (displayLimit.value < rawModels.value.length) {
        displayLimit.value = Math.min(rawModels.value.length, displayLimit.value + 20)
        return
      }
      if (hasMore.value && !fetching.value) {
        await loadPage(page.value + 1)
      }
    }

    // Non-allocating scroll handler: only mutate numeric refs, avoid creating objects
    function onScroll(e: Event) {
      const el = listRef.value as HTMLElement | null
      if (!el) return
      const remaining = (el.scrollHeight - el.clientHeight) - el.scrollTop
      if (remaining < 120) {
        // fire-and-forget; caller will schedule next page
        void loadNextIfNeeded()
      }
    }

    const canSave = computed(() => !!selected.value && !!projectId.value)

    async function save() {
      if (!projectId.value) return alert('No active project selected')
      try {
        const resp = await fetch('/api/v1/project/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ project_id: projectId.value, target_model: selected.value })
        })
        if (!resp.ok) throw new Error(`Save failed: ${resp.status}`)
        const body = await resp.json()
        if (body.success) {
          alert('Project model updated')
          emit('update:modelValue', selected.value)
        } else {
          alert('Save failed: ' + (body.error || 'unknown'))
        }
      } catch (err) {
        console.error('ModelSelector save error', err)
        alert('Error saving model')
      }
    }

    return {
      rawModels,
      loading,
      error,
      search,
      selected,
      projectId,
      filtered,
      refresh,
      selectModel,
      canSave,
      save,
      listRef,
      onScroll
    }
  }
})
</script>

<style scoped>
.model-selector input::placeholder { color: #9ca3af; }
</style>
