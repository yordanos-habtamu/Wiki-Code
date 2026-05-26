<template>
  <div class="relative w-full h-full overflow-hidden">
    <!-- Zoom Controls -->
    <div class="absolute top-4 right-4 z-10 flex flex-col gap-2">
      <button 
        @click="zoomIn"
        class="bg-gray-900 border border-gray-700 hover:border-blue-500/50 text-gray-300 hover:text-blue-400 w-10 h-10 rounded-lg flex items-center justify-center transition-all active:scale-95 shadow-lg"
        title="Zoom In"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"/>
        </svg>
      </button>
      <button 
        @click="zoomOut"
        class="bg-gray-900 border border-gray-700 hover:border-blue-500/50 text-gray-300 hover:text-blue-400 w-10 h-10 rounded-lg flex items-center justify-center transition-all active:scale-95 shadow-lg"
        title="Zoom Out"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18 12H6"/>
        </svg>
      </button>
      <button 
        @click="resetZoom"
        class="bg-gray-900 border border-gray-700 hover:border-blue-500/50 text-gray-300 hover:text-blue-400 w-10 h-10 rounded-lg flex items-center justify-center transition-all active:scale-95 shadow-lg"
        title="Reset Zoom"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4"/>
        </svg>
      </button>
      <div class="bg-gray-900 border border-gray-700 text-gray-400 text-xs px-2 py-1 rounded-lg text-center">
        {{ Math.round(zoomLevel * 100) }}%
      </div>
    </div>

    <!-- Language Legend -->
    <div class="absolute bottom-4 left-4 z-10 bg-gray-900/95 border border-gray-800 rounded-lg p-3 backdrop-blur-sm">
      <div class="text-xs font-medium text-gray-300 mb-2">Languages</div>
      <div class="grid grid-cols-2 gap-1.5">
        <div v-for="(color, lang) in activeLanguages" :key="lang" class="flex items-center gap-2">
          <div class="w-3 h-3 rounded-full" :style="{ backgroundColor: color }"></div>
          <span class="text-[10px] text-gray-400 capitalize">{{ lang }}</span>
        </div>
      </div>
    </div>

    <!-- SVG Canvas with Zoom/Pan -->
    <svg 
      :width="dimensions.width" 
      :height="dimensions.height" 
      class="w-full h-full"
      ref="svgCanvas"
      @wheel="handleWheelZoom"
    >
      <!-- Background Grid Pattern -->
      <defs>
        <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
          <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#1f2937" stroke-width="0.5"/>
        </pattern>
        
        <!-- Luminescent Glow Filters -->
        <filter id="glow-emerald" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="6" result="blur" />
          <feFlood flood-color="#10b981" flood-opacity="0.4" result="color" />
          <feComposite in="color" in2="blur" operator="in" result="glow" />
          <feMerge>
            <feMergeNode in="glow" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        
        <filter id="glow-mint" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="5" result="blur" />
          <feFlood flood-color="#34d399" flood-opacity="0.35" result="color" />
          <feComposite in="color" in2="blur" operator="in" result="glow" />
          <feMerge>
            <feMergeNode in="glow" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        
        <filter id="glow-teal" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="5" result="blur" />
          <feFlood flood-color="#06b6d4" flood-opacity="0.35" result="color" />
          <feComposite in="color" in2="blur" operator="in" result="glow" />
          <feMerge>
            <feMergeNode in="glow" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        
        <filter id="glow-amber" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="5" result="blur" />
          <feFlood flood-color="#f59e0b" flood-opacity="0.4" result="color" />
          <feComposite in="color" in2="blur" operator="in" result="glow" />
          <feMerge>
            <feMergeNode in="glow" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        
        <filter id="glow-crimson" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="6" result="blur" />
          <feFlood flood-color="#ef4444" flood-opacity="0.5" result="color" />
          <feComposite in="color" in2="blur" operator="in" result="glow" />
          <feMerge>
            <feMergeNode in="glow" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>

        <marker id="lineage-arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#06b6d4" />
        </marker>
      </defs>
      <rect width="100%" height="100%" fill="url(#grid)" />

      <!-- Transform Group for Zoom/Pan -->
      <g :transform="`translate(${panX}, ${panY}) scale(${zoomLevel})`">
        <!-- Links with dynamic fade based on zoom -->
        <g class="links">
          <line 
            v-for="(link, index) in links" 
            :key="'link-' + index"
            :x1="nodes[link.source]?.x || 0"
            :y1="nodes[link.source]?.y || 0"
            :x2="nodes[link.target]?.x || 0"
            :y2="nodes[link.target]?.y || 0"
            :stroke="link.isCrossLanguage ? '#ef4444' : '#1e293b'"
            :stroke-width="link.isCrossLanguage ? 2.5 : 1.5"
            :stroke-dasharray="link.isCrossLanguage ? '4,4' : 'none'"
            :opacity="link.isCrossLanguage ? 1 : Math.max(0.3, Math.min(1, zoomLevel * 0.8))"
          />
        </g>

        <!-- Lineage Overlays -->
        <g class="lineage-overlays">
          <line
            v-for="(overlay, index) in lineageOverlays"
            :key="'overlay-' + index"
            :x1="overlay.x1"
            :y1="overlay.y1"
            :x2="overlay.x2"
            :y2="overlay.y2"
            stroke="#06b6d4"
            stroke-width="2.5"
            stroke-linecap="round"
            stroke-opacity="0.78"
            marker-end="url(#lineage-arrow)"
          />
        </g>

        <!-- Nodes -->
        <g class="nodes">
          <g 
            v-for="(node, index) in nodes" 
            :key="'node-' + index"
            :transform="`translate(${node.x}, ${node.y})`"
            class="cursor-grab active:cursor-grabbing"
            @mousedown="startNodeDrag($event, index)"
            @touchstart="startNodeDrag($event, index)"
          >
            <!-- Outer glow ring with SVG filter -->
            <circle 
              :r="node.weight / 2 + 6" 
              :fill="getNodeGlow(node.score, node.lang)"
              :filter="getNodeFilter(node.score, node.lang)"
              class="opacity-60"
            />
            <circle
              v-if="blastRadiusSet.has(node.id)"
              :r="node.weight / 2 + 12"
              fill="none"
              stroke="#ef4444"
              stroke-width="3"
              class="pulse-ring"
            />
            <!-- Main circle -->
            <circle 
              :r="node.weight / 2" 
              :fill="getNodeFill(node.score, node.lang)"
              :stroke="getNodeStroke(node.score, node.lang)"
              stroke-width="2.5"
              class="transition-all hover:stroke-white"
            />
            <!-- Score text -->
            <text 
              y="4" 
              text-anchor="middle" 
              class="text-xs font-bold pointer-events-none select-none"
              :fill="getNodeTextColor(node.score, node.lang)"
            >
              {{ node.score.toFixed(1) }}
            </text>
            <!-- File name label - Monospace with zoom visibility -->
            <text 
              v-show="zoomLevel >= 0.75"
              :y="node.weight / 2 + 18" 
              text-anchor="middle" 
              class="font-mono text-[11px] tracking-wider pointer-events-none select-none"
              :fill="zoomLevel >= 1.2 ? '#9ca3af' : '#6b7280'"
              :opacity="Math.min(1, (zoomLevel - 0.75) * 2)"
            >
              {{ getFileName(node.id) }}
            </text>
            <title>{{ node.id }} ({{ node.lang }}) - Score: {{ node.score.toFixed(1) }}</title>
          </g>
        </g>
      </g>
    </svg>
  </div>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'

interface Node {
  id: string
  lang: string
  score: number
  weight: number
  smells: number
  x: number
  y: number
  vx: number
  vy: number
}

interface Link {
  source: number
  target: number
  isCrossLanguage: boolean
}

interface LineagePath {
  source: string
  target: string
  direction: string
}

const props = defineProps<{
  nodes: Node[]
  links: Link[]
  dimensions: { width: number, height: number }
  lineagePaths?: LineagePath[]
  blastRadiusNodes?: string[]
  focusNodeId?: string
}>()

const nodeIndexMap = computed(() => {
  const map: Record<string, number> = {}
  props.nodes.forEach((node, index) => {
    if (node && node.id) {
      map[node.id] = index
    }
  })
  return map
})

const lineageOverlays = computed(() => {
  const paths = [] as Array<{ x1: number, y1: number, x2: number, y2: number, highlight: boolean }>
  const edgePaths = props.lineagePaths || []

  edgePaths.forEach((path) => {
    const sourceIdx = nodeIndexMap.value[path.source]
    const targetIdx = nodeIndexMap.value[path.target]
    const sourceNode = props.nodes[sourceIdx]
    const targetNode = props.nodes[targetIdx]

    if (sourceNode && targetNode) {
      paths.push({
        x1: sourceNode.x,
        y1: sourceNode.y,
        x2: targetNode.x,
        y2: targetNode.y,
        highlight: path.direction === 'forward'
      })
    }
  })

  return paths
})

const blastRadiusSet = computed(() => new Set(props.blastRadiusNodes || []))

// Computed: Get unique active languages with their colors
const activeLanguages = computed(() => {
  const langMap: Record<string, string> = {}
  props.nodes.forEach(node => {
    if (node.lang && !langMap[node.lang.toLowerCase()]) {
      langMap[node.lang.toLowerCase()] = getLanguageColor(node.lang)
    }
  })
  return langMap
})

const svgCanvas = ref<SVGElement | null>(null)
let animationFrameId: number | null = null
const inverseMass = ref<Float32Array>(new Float32Array(0))
const draggedNodeIndex = ref<number | null>(null)

// Zoom and pan state
const zoomLevel = ref(1)
const panX = ref(0)
const panY = ref(0)
const MIN_ZOOM = 0.25
const MAX_ZOOM = 3
const ZOOM_STEP = 0.1

// Physics engine constants
const DAMPING = 0.82
const REPULSION = 150
const SPRING_LENGTH = 100
const SPRING_STRENGTH = 0.08
const CENTER_GRAVITY = 0.01
const BOUNDARY_PADDING = 20

// Initialize inverse mass array and center nodes
function resetNodePositions() {
  const len = props.nodes.length
  if (len === 0 || !props.dimensions.width || !props.dimensions.height) return

  const centerX = props.dimensions.width / 2
  const centerY = props.dimensions.height / 2

  for (let i = 0; i < len; i++) {
    const node = props.nodes[i]
    node.x = centerX + (Math.random() - 0.5) * 4
    node.y = centerY + (Math.random() - 0.5) * 4
    node.vx = 0
    node.vy = 0
  }
}

function initializeInverseMass() {
  const len = props.nodes.length
  if (inverseMass.value.length !== len) {
    inverseMass.value = new Float32Array(len)
    for (let i = 0; i < len; i++) {
      inverseMass.value[i] = 1 / Math.max(0.1, props.nodes[i].weight / 10)
    }
    
    resetNodePositions()
  }
}

watch(
  [
    () => props.nodes.length,
    () => props.dimensions.width,
    () => props.dimensions.height
  ], () => {
    if (props.nodes.length > 0 && props.dimensions.width > 0 && props.dimensions.height > 0) {
      initializeInverseMass()
      resetNodePositions()
    }
  }, { immediate: true })

// Physics update loop - ZERO ALLOCATIONS
function updatePhysics() {
  const nodes = props.nodes
  const links = props.links
  
  // Skip if no nodes
  if (nodes.length === 0) {
    animationFrameId = requestAnimationFrame(updatePhysics)
    return
  }

  const len = nodes.length
  const width = props.dimensions.width
  const height = props.dimensions.height

  // Initialize inverse mass if needed
  if (inverseMass.value.length !== len) {
    initializeInverseMass()
  }

  // Repulsion phase (multi-loop for performance)
  for (let i = 0; i < len; i++) {
    for (let j = i + 1; j < len; j++) {
      let dx = nodes[j].x - nodes[i].x
      let dy = nodes[j].y - nodes[i].y
      
      // NaN guards
      if (dx === 0) dx = 0.1
      if (dy === 0) dy = 0.1
      
      let distSq = dx * dx + dy * dy
      let dist = Math.sqrt(distSq)
      
      if (dist < 1) dist = 1
      if (distSq < 1) distSq = 1
      
      let force = REPULSION / distSq
      let fx = force * (dx / dist)
      let fy = force * (dy / dist)
      
      // Don't move dragged node
      if (i !== draggedNodeIndex.value) {
        nodes[i].vx -= fx * inverseMass.value[i]
        nodes[i].vy -= fy * inverseMass.value[i]
      }
      if (j !== draggedNodeIndex.value) {
        nodes[j].vx += fx * inverseMass.value[j]
        nodes[j].vy += fy * inverseMass.value[j]
      }
    }
  }

  // Spring attraction phase
  for (let k = 0; k < links.length; k++) {
    const link = links[k]
    const source = nodes[link.source]
    const target = nodes[link.target]
    
    if (!source || !target) continue
    
    let dx = target.x - source.x
    let dy = target.y - source.y
    
    // NaN guards
    if (dx === 0) dx = 0.1
    if (dy === 0) dy = 0.1
    
    let dist = Math.sqrt(dx * dx + dy * dy)
    if (dist < 1) dist = 1
    
    let displacement = dist - SPRING_LENGTH
    let force = displacement * SPRING_STRENGTH
    let fx = force * (dx / dist)
    let fy = force * (dy / dist)
    
    // Don't move dragged node
    if (link.source !== draggedNodeIndex.value) {
      source.vx += fx * inverseMass.value[link.source]
      source.vy += fy * inverseMass.value[link.source]
    }
    if (link.target !== draggedNodeIndex.value) {
      target.vx -= fx * inverseMass.value[link.target]
      target.vy -= fy * inverseMass.value[link.target]
    }
  }

  // Update positions with damping, center gravity, and boundary clamping
  const centerX = width / 2
  const centerY = height / 2
  
  for (let i = 0; i < len; i++) {
    // Skip dragged node
    if (i === draggedNodeIndex.value) continue
    
    const n = nodes[i]
    
    // Center gravity (pull nodes toward center)
    n.vx += (centerX - n.x) * CENTER_GRAVITY
    n.vy += (centerY - n.y) * CENTER_GRAVITY
    
    // Damping
    n.vx *= DAMPING
    n.vy *= DAMPING
    
    // Velocity clamping
    const maxVelocity = 10
    n.vx = Math.max(-maxVelocity, Math.min(maxVelocity, n.vx))
    n.vy = Math.max(-maxVelocity, Math.min(maxVelocity, n.vy))
    
    // Update position
    n.x += n.vx
    n.y += n.vy
    
    // Boundary clamping with padding
    n.x = Math.max(BOUNDARY_PADDING, Math.min(width - BOUNDARY_PADDING, n.x))
    n.y = Math.max(BOUNDARY_PADDING, Math.min(height - BOUNDARY_PADDING, n.y))
    
    // NaN protection
    if (isNaN(n.x) || isNaN(n.y)) {
      console.error(`[Physics] NaN detected on node ${i}, resetting position`)
      n.x = centerX
      n.y = centerY
      n.vx = 0
      n.vy = 0
    }
  }

  // Continue loop
  animationFrameId = requestAnimationFrame(updatePhysics)
}

// Node styling helpers - Language-based color coding
function getNodeGlow(score: number, lang: string): string {
  // Solid fill for glow circle (filter adds the blur effect)
  return getLanguageColor(lang)
}

function getNodeFilter(score: number, lang: string): string {
  // Return SVG filter ID based on language
  const color = getLanguageColor(lang)
  return getFilterForColor(color)
}

function getNodeFill(score: number, lang: string): string {
  // Language-based color coding
  return getLanguageColor(lang)
}

function getLanguageColor(lang: string): string {
  // Professional color palette by programming language
  const colors: Record<string, string> = {
    // JavaScript ecosystem
    'javascript': '#f7df1e',  // JavaScript Yellow
    'typescript': '#3178c6',  // TypeScript Blue
    
    // Python ecosystem
    'python': '#3776ab',      // Python Blue
    
    // Go ecosystem
    'go': '#00add8',          // Go Cyan
    
    // Web technologies
    'html': '#e34f26',        // HTML Orange
    'css': '#1572b6',         // CSS Blue
    'vue': '#42b883',         // Vue Green
    'react': '#61dafb',       // React Light Blue
    
    // Systems programming
    'rust': '#dea584',        // Rust Orange
    'c': '#a8b9cc',           // C Gray
    'cpp': '#9c033a',         // C++ Red
    
    // JVM languages
    'java': '#ed8b00',        // Java Orange
    'kotlin': '#7f52ff',      // Kotlin Purple
    
    // Other languages
    'ruby': '#cc342d',        // Ruby Red
    'php': '#777bb4',         // PHP Purple
    'swift': '#fa7343',       // Swift Orange
    'csharp': '#178600',      // C# Green
    
    // Config/Data files
    'json': '#5b9553',        // JSON Green
    'yaml': '#cb171e',        // YAML Red
    'toml': '#9c4121',        // TOML Orange
    'xml': '#e7cd51',         // XML Yellow
    
    // Shell/Scripts
    'shell': '#89e051',       // Shell Green
    'bash': '#89e051',        // Bash Green
    
    // Database
    'sql': '#e38c00',         // SQL Orange
    
    // Markdown/Docs
    'markdown': '#083fa1',    // Markdown Blue
  }
  
  return colors[lang.toLowerCase()] || '#8b5cf6' // Default: Violet for unknown
}

function getFilterForColor(color: string): string {
  // Map color to appropriate SVG filter
  const filterMap: Record<string, string> = {
    '#f7df1e': 'url(#glow-emerald)',  // JavaScript
    '#3178c6': 'url(#glow-teal)',     // TypeScript
    '#3776ab': 'url(#glow-teal)',     // Python
    '#00add8': 'url(#glow-teal)',     // Go
    '#e34f26': 'url(#glow-amber)',    // HTML
    '#1572b6': 'url(#glow-teal)',     // CSS
    '#42b883': 'url(#glow-emerald)',  // Vue
    '#61dafb': 'url(#glow-teal)',     // React
    '#dea584': 'url(#glow-amber)',    // Rust
    '#a8b9cc': 'url(#glow-mint)',     // C
    '#9c033a': 'url(#glow-crimson)',  // C++
    '#ed8b00': 'url(#glow-amber)',    // Java
    '#7f52ff': 'url(#glow-crimson)',  // Kotlin
    '#cc342d': 'url(#glow-crimson)',  // Ruby
    '#777bb4': 'url(#glow-crimson)',  // PHP
    '#fa7343': 'url(#glow-amber)',    // Swift
    '#178600': 'url(#glow-emerald)',  // C#
    '#5b9553': 'url(#glow-emerald)',  // JSON
    '#cb171e': 'url(#glow-crimson)',  // YAML
    '#9c4121': 'url(#glow-amber)',    // TOML
    '#e7cd51': 'url(#glow-emerald)',  // XML
    '#89e051': 'url(#glow-emerald)',  // Shell
    '#e38c00': 'url(#glow-amber)',    // SQL
    '#083fa1': 'url(#glow-teal)',     // Markdown
  }
  
  return filterMap[color] || 'url(#glow-teal)' // Default filter
}

function getNodeStroke(score: number, lang: string): string {
  // Darker shade of language color for stroke
  const color = getLanguageColor(lang)
  // Return a slightly darker version for the border
  return color
}

function getNodeTextColor(score: number, lang: string): string {
  // Use white or black based on language color brightness
  const color = getLanguageColor(lang)
  // Simple brightness check
  const brightness = parseInt(color.slice(1), 16)
  const r = (brightness >> 16) & 255
  const g = (brightness >> 8) & 255
  const b = brightness & 255
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
  return luminance > 0.5 ? '#000000' : '#ffffff'
}

// Extract short file name from path
function getFileName(path: string): string {
  if (!path) return 'unknown'
  const parts = path.split('/')
  const fileName = parts[parts.length - 1]
  // Truncate if too long
  return fileName.length > 20 ? fileName.substring(0, 17) + '...' : fileName
}

// Zoom controls
function zoomIn() {
  zoomLevel.value = Math.min(MAX_ZOOM, zoomLevel.value + ZOOM_STEP)
}

function zoomOut() {
  zoomLevel.value = Math.max(MIN_ZOOM, zoomLevel.value - ZOOM_STEP)
}

function resetZoom() {
  zoomLevel.value = 1
  panX.value = 0
  panY.value = 0
}

function handleWheelZoom(event: WheelEvent) {
  event.preventDefault()
  
  const delta = event.deltaY > 0 ? -ZOOM_STEP : ZOOM_STEP
  zoomLevel.value = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, zoomLevel.value + delta))
}

// Node drag handlers
function startNodeDrag(event: MouseEvent | TouchEvent, index: number) {
  event.preventDefault()
  draggedNodeIndex.value = index
  
  // Stop the node from moving while dragged
  if (props.nodes[index]) {
    props.nodes[index].vx = 0
    props.nodes[index].vy = 0
  }
  
  // Add global event listeners
  document.addEventListener('mousemove', handleNodeDrag)
  document.addEventListener('mouseup', stopNodeDrag)
  document.addEventListener('touchmove', handleNodeDrag, { passive: false })
  document.addEventListener('touchend', stopNodeDrag)
}

function handleNodeDrag(event: MouseEvent | TouchEvent) {
  if (draggedNodeIndex.value === null) return
  event.preventDefault()
  
  const node = props.nodes[draggedNodeIndex.value]
  if (!node) return
  
  const svg = svgCanvas.value
  if (!svg) return
  
  const rect = svg.getBoundingClientRect()
  let clientX: number, clientY: number
  
  if (event instanceof MouseEvent) {
    clientX = event.clientX
    clientY = event.clientY
  } else {
    const touch = event.touches[0]
    clientX = touch.clientX
    clientY = touch.clientY
  }
  
  node.x = clientX - rect.left
  node.y = clientY - rect.top
  
  // Boundary clamping
  node.x = Math.max(BOUNDARY_PADDING, Math.min(props.dimensions.width - BOUNDARY_PADDING, node.x))
  node.y = Math.max(BOUNDARY_PADDING, Math.min(props.dimensions.height - BOUNDARY_PADDING, node.y))
}

function stopNodeDrag() {
  draggedNodeIndex.value = null
  
  // Remove global event listeners
  document.removeEventListener('mousemove', handleNodeDrag)
  document.removeEventListener('mouseup', stopNodeDrag)
  document.removeEventListener('touchmove', handleNodeDrag)
  document.removeEventListener('touchend', stopNodeDrag)
}

// Watch: Auto-center nodes when new data arrives
watch(() => props.nodes.length, () => {
  if (props.nodes.length > 0 && props.dimensions.width) {
    resetNodePositions()
  }
})

watch(() => props.focusNodeId, (newFocus) => {
  if (!newFocus || !props.dimensions.width || !props.dimensions.height) return
  const index = nodeIndexMap.value[newFocus]
  if (index == null) return

  const node = props.nodes[index]
  if (!node) return

  zoomLevel.value = Math.min(MAX_ZOOM, Math.max(1.1, zoomLevel.value))
  panX.value = props.dimensions.width / 2 - node.x * zoomLevel.value
  panY.value = props.dimensions.height / 2 - node.y * zoomLevel.value
})

// Alt key: Re-center nodes
function handleKeyDown(event: KeyboardEvent) {
  if (event.altKey) {
    event.preventDefault()
    resetNodePositions()
    resetZoom()
  }
}

// Lifecycle
onMounted(() => {
  initializeInverseMass()
  animationFrameId = requestAnimationFrame(updatePhysics)
  document.addEventListener('keydown', handleKeyDown)
})

onBeforeUnmount(() => {
  if (animationFrameId) {
    cancelAnimationFrame(animationFrameId)
  }
  document.removeEventListener('keydown', handleKeyDown)
})
</script>

<style scoped>
.pulse-ring {
  animation: pulseHalo 1.8s ease-in-out infinite;
  will-change: transform, opacity;
}

@keyframes pulseHalo {
  0% {
    transform: scale(1);
    opacity: 0.35;
  }
  50% {
    transform: scale(1.15);
    opacity: 0.65;
  }
  100% {
    transform: scale(1);
    opacity: 0.35;
  }
}
</style>
