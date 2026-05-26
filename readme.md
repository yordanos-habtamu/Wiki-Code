# WikiHub

WikiHub is a local, hybrid code intelligence engine engineered to solve token overhead, documentation rot, and polyglot context gaps in complex codebases. By separating fast syntactic parsing from stateful AI reasoning, WikiHub indexes and monitors cross-file dependencies and generates diff-ready refactor suggestions without overflowing LLM context limits or exposing your raw source code.

---

## Key Features

* **Token-Compressed Context Maps:** Re-parses thousands of raw source lines into lightweight file abstracts, eliminating high token overhead.
* **Blast Radius Analysis:** Instantly surfaces interactive dependency maps inside your IDE to evaluate the downstream impact of changing core utility code.
* **Agentic Refactoring Subgraphs:** Uses specialized LangGraph workflows to flag architectural code smells (high coupling, dead code, duplication) and emit structured improvement objects.
* **Bring Your Own Key (BYOK) Routing:** Executes all model interactions through a local, encrypted, multi-provider abstraction layer supporting OpenRouter, Gemini, DeepSeek, and Qwen.
* **Real-time Token Metering UI:** A read-only Nuxt 3 dashboard tracks real-time and 30-day cumulative token burn with per-provider breakdowns, cost estimates, and threshold alerts.

---

## Architecture Overview

WikiHub is built using a clean monorepo architecture divided into isolated runtime spaces, shared contract packages, and dedicated data providers.

### Repository Layout

```text
wikihub/
├── apps/
│   ├── cli/             # Go CLI high-speed scanner ("The Muscle")
│   ├── ai-core/         # Python core LangGraph engine & services ("The Brain")
│   ├── dashboard/       # Nuxt 3 web-based visualizer ("The Lens")
│   └── mcp-server/      # FastMCP interface exposing tools to AI editors
├── packages/
│   ├── contracts/       # Centralized business schemas (Pydantic / JSON)
│   ├── prompts/         # Versioned, model-tagged prompt templates
│   ├── config/          # Global configuration primitives
│   ├── sdk/             # Internal program communication helpers
│   └── shared-types/    # Transpiled cross-language type definitions
└── infrastructure/      # Local data orchestration boundaries
    ├── sqlite/          # Relational entity & token state definitions
    ├── chromadb/        # Semantic embedding vector stores
    ├── embeddings/      # Local fallback text-vectorization layers
    ├── encryption/      # Configuration & API key at-rest encryption utilities
    ├── logging/         # Stream-isolated structured log managers
    └── telemetry/       # Performance metric collection frameworks