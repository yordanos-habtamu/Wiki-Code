"""
FastMCP Server - Model Context Protocol communication bridge.
Exposes structural codebase queries, semantic searches, and token telemetry.
"""

import sys
import os
import json
from typing import List, Dict, Any, Optional
import importlib.util

# CRITICAL: Redirect all stdout to stderr to prevent JSON-RPC stream corruption
# This MUST happen before any other imports
_original_stdout = sys.stdout
sys.stdout = sys.stderr

# Explicitly suppress noisy loggers across transitive graph dependencies
import logging
logging.getLogger("langgraph").setLevel(logging.ERROR)
logging.getLogger("pydantic").setLevel(logging.ERROR)
logging.getLogger("chromadb").setLevel(logging.ERROR)
logging.getLogger("sqlite3").setLevel(logging.ERROR)
logging.getLogger("onnxruntime").setLevel(logging.ERROR)

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# Add ai-core to path for module imports
ai_core_path = os.path.join(project_root, "apps", "ai-core")
if ai_core_path not in sys.path:
    sys.path.insert(0, ai_core_path)

# Import FastMCP
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("Error: fastmcp package not installed. Run: pip install fastmcp", file=sys.stderr)
    sys.exit(1)

# Initialize FastMCP Server (port is overridden by --port CLI arg at runtime)
mcp = FastMCP("WikiHub-Core-Engine", port=7000)


# ============================================================================
# Stream Isolation Guard
# Force all sub-dependencies to log to stderr
# ============================================================================

import logging

# Redirect Python logging to stderr
logging.basicConfig(
    level=logging.WARNING,
    stream=sys.stderr,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Suppress verbose logging from known noisy libraries (additional)
# Already suppressed above for critical libraries


# ============================================================================
# Dynamic Module Loading
# Load repositories and pipelines from apps/ai-core/
# ============================================================================

def load_module_from_path(module_name: str, file_path: str):
    """Dynamically load a Python module from a file path."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# Load ProjectRepository
project_repo_path = os.path.join(project_root, "apps", "ai-core", "repositories", "project_repository.py")
project_repo_module = load_module_from_path("project_repository", project_repo_path)
ProjectRepository = project_repo_module.ProjectRepository

# Load TokenUsageRepository
token_repo_path = os.path.join(project_root, "apps", "ai-core", "repositories", "token_usage_repository.py")
token_repo_module = load_module_from_path("token_usage_repository", token_repo_path)
TokenUsageRepository = token_repo_module.TokenUsageRepository

# Load EmbeddingPipeline
embedding_pipeline_path = os.path.join(project_root, "apps", "ai-core", "pipelines", "embedding_pipeline.py")
embedding_pipeline_module = load_module_from_path("embedding_pipeline", embedding_pipeline_path)
EmbeddingPipeline = embedding_pipeline_module.EmbeddingPipeline

# Load RefactorGraphState and RefactoringPipelineGraph
refactor_state_path = os.path.join(project_root, "apps", "ai-core", "schemas", "refactor_state.py")
refactor_state_module = load_module_from_path("refactor_state", refactor_state_path)
RefactorGraphState = refactor_state_module.RefactorGraphState

refactoring_pipeline_path = os.path.join(project_root, "apps", "ai-core", "graphs", "refactoring_pipeline_graph.py")
refactoring_pipeline_module = load_module_from_path("refactoring_pipeline_graph", refactoring_pipeline_path)
RefactoringPipelineGraph = refactoring_pipeline_module.RefactoringPipelineGraph

# Load ImpactGraphState and ImpactAnalysisGraph
impact_state_path = os.path.join(project_root, "apps", "ai-core", "schemas", "impact_state.py")
impact_state_module = load_module_from_path("impact_state", impact_state_path)
ImpactGraphState = impact_state_module.ImpactGraphState

impact_analysis_path = os.path.join(project_root, "apps", "ai-core", "graphs", "impact_analysis_graph.py")
impact_analysis_module = load_module_from_path("impact_analysis_graph", impact_analysis_path)
ImpactAnalysisGraph = impact_analysis_module.ImpactAnalysisGraph


# ============================================================================
# Initialize Repository Instances
# ============================================================================

# Database paths
db_path = os.path.join(project_root, "apps", "cli", "hub.db")
chromadb_dir = os.path.join(project_root, "infrastructure", "chromadb", "db")

# Initialize repositories
project_repo = ProjectRepository(db_path=db_path)
token_repo = TokenUsageRepository(db_path=db_path)
embedding_pipeline = EmbeddingPipeline(db_path=db_path, chromadb_dir=chromadb_dir)

print("WikiHub MCP Server initialized with all repositories", file=sys.stderr)


# ============================================================================
# MCP Tool Registration
# ============================================================================

@mcp.tool()
def get_codebase_structure() -> List[Dict[str, Any]]:
    """
    Retrieve the complete structural inventory of the indexed codebase.
    
    Returns a list of all tracked source files with their relative paths,
    programming languages, index freshness timestamps, and entity counts.
    This allows external agents to understand the project layout without
    scanning raw code lines.
    
    Returns:
        List of dictionaries containing:
        - relative_path: File path relative to project root
        - language: Programming language (Go, Python, TypeScript/JavaScript, PHP)
        - file_hash: SHA-256 hash for freshness tracking
        - file_size: File size in bytes
    """
    try:
        files = project_repo.get_all_files()
        
        # Enrich with symbol counts
        enriched_files = []
        for file_info in files:
            rel_path = file_info["relative_path"]
            symbols = project_repo.get_symbols_for_file(rel_path)
            dependencies = project_repo.get_dependencies_for_file(rel_path)
            
            enriched_files.append({
                "relative_path": rel_path,
                "language": file_info["language"],
                "file_hash": file_info["file_hash"],
                "file_size": file_info["file_size"],
                "symbol_count": len(symbols),
                "dependency_count": len(dependencies)
            })
        
        print(
            f"MCP Tool: get_codebase_structure returned {len(enriched_files)} files",
            file=sys.stderr
        )
        
        return enriched_files
        
    except Exception as e:
        print(f"Error in get_codebase_structure: {e}", file=sys.stderr)
        raise


@mcp.tool()
def search_codebase_abstracts(query: str, n_results: int = 5) -> List[Dict[str, Any]]:
    """
    Perform semantic search across token-compressed codebase abstracts.
    
    Searches the embedded ChromaDB vector store to find files that match
    the natural language query based on structural semantics, not raw code.
    This enables finding files by technical concepts (e.g., "authentication",
    "database connection pooling") rather than keyword matching.
    
    Args:
        query: Natural language search query describing the technical concept
               (e.g., "User route authorization interceptor patterns")
        n_results: Number of top results to return (default: 5, max: 20)
    
    Returns:
        List of matching context nodes containing:
        - relative_path: File path
        - language: Programming language
        - abstract: Token-compressed structural abstract
        - distance: Semantic similarity score (lower is better)
        - file_size: File size in bytes
        - entity_count: Total symbols + dependencies
    """
    try:
        # Cap results to prevent excessive data transfer
        n_results = min(n_results, 20)
        
        # Get ChromaDB collection
        collection = embedding_pipeline.get_or_create_collection()
        
        # Perform semantic search
        results = collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        # Format results
        matches = []
        if results and "documents" in results and len(results["documents"]) > 0:
            for doc, doc_id, distance, metadata in zip(
                results["documents"][0],
                results["ids"][0],
                results["distances"][0],
                results["metadatas"][0]
            ):
                matches.append({
                    "relative_path": doc_id,
                    "language": metadata.get("language", "unknown"),
                    "abstract": doc,
                    "distance": round(distance, 4),
                    "file_size": metadata.get("file_size", 0),
                    "entity_count": metadata.get("entity_count", 0)
                })
        
        print(
            f"MCP Tool: search_codebase_abstracts query='{query}' "
            f"returned {len(matches)} results",
            file=sys.stderr
        )
        
        return matches
        
    except Exception as e:
        print(f"Error in search_codebase_abstracts: {e}", file=sys.stderr)
        raise


@mcp.tool()
def get_token_telemetry(time_window_days: int = 30) -> Dict[str, Any]:
    """
    Retrieve real-time token tracking metadata and budget consumption metrics.
    
    Exposes comprehensive token usage statistics aggregated by provider,
    including input/output token breakdowns, request counts, and cumulative
    consumption within the specified time window. This enables external
    clients to monitor API usage and estimate costs.
    
    Args:
        time_window_days: Historical aggregation window in days (default: 30)
    
    Returns:
        Dictionary containing:
        - total_tokens_consumed: Cumulative token count across all providers
        - total_requests: Total API calls made
        - time_window_days: The aggregation window used
        - per_provider_metrics: List of provider-specific breakdowns including:
          - provider: Provider name (gemini, deepseek, qwen, etc.)
          - request_count: Number of API calls
          - total_prompt_tokens: Input tokens consumed
          - total_completion_tokens: Output tokens generated
          - total_tokens: Combined token usage
          - avg_tokens_per_request: Average tokens per call
          - first_usage: Earliest usage timestamp
          - last_usage: Most recent usage timestamp
        - budget_health: Simple health indicator based on usage patterns
    """
    try:
        # Get total budget spent
        total_tokens = token_repo.get_total_budget_spent(time_window_days=time_window_days)
        
        # Get per-provider metrics
        provider_metrics = token_repo.get_per_provider_metrics()
        
        # Calculate total requests
        total_requests = sum(m["request_count"] for m in provider_metrics)
        
        # Determine budget health (simple heuristic)
        if total_tokens == 0:
            budget_health = "healthy"
        elif total_tokens < 100000:
            budget_health = "healthy"
        elif total_tokens < 500000:
            budget_health = "moderate"
        else:
            budget_health = "high_usage"
        
        telemetry = {
            "total_tokens_consumed": total_tokens,
            "total_requests": total_requests,
            "time_window_days": time_window_days,
            "per_provider_metrics": provider_metrics,
            "budget_health": budget_health
        }
        
        print(
            f"MCP Tool: get_token_telemetry returned {total_tokens} tokens "
            f"across {len(provider_metrics)} providers",
            file=sys.stderr
        )
        
        return telemetry
        
    except Exception as e:
        print(f"Error in get_token_telemetry: {e}", file=sys.stderr)
        raise


@mcp.tool()
def audit_code_quality(target_file: str, token_budget: int = 100000) -> Dict[str, Any]:
    """
    Run comprehensive code quality and architectural audit on a target file.
    
    Executes the multi-agent refactoring pipeline to trace code rot, measure
    architectural decay metrics, and generate structural improvement plans.
    This tool analyzes token-compressed abstracts only - no raw source code
    is accessed, ensuring complete structural safety.
    
    The audit detects anti-patterns including:
    - High cyclomatic coupling (excessive dependencies)
    - Interface segregation deficits (too many classes/interfaces)
    - Excessive module complexity (large files)
    - Language-specific violations
    
    Args:
        target_file: The relative path of the file to inspect within the
                     active repository context (e.g., "apps/ai-core/agents/code_smell_detector_agent.py")
        token_budget: Strict ceiling specifying maximum permissible context
                      usage for the run (default: 100000)
    
    Returns:
        Dictionary containing:
        - target_file: The audited file path
        - quality_score: Overall code quality score (0.0 - 10.0, higher is better)
        - refactoring_priority: Priority level (isolated, low, medium, high, critical)
        - detected_smells: List of categorized code smells with:
          - type: Anti-pattern classification
          - severity: Severity level (low, medium, high, critical)
          - description: Detailed explanation
          - metric: Quantitative measurement
        - proposed_architecture: List of backward-compatible refactoring schemas with:
          - title: Proposal name
          - smell_addressed: Which smell this addresses
          - priority: Implementation priority
          - description: Detailed improvement strategy
          - proposed_changes: List of specific change recommendations
          - backwards_compatibility: Compatibility impact assessment
          - estimated_effort: Implementation effort (Low, Medium, High)
        - done_condition: Whether audit completed successfully
        - reasoning_steps: Chronological log of audit progression
    """
    try:
        print(
            f"MCP Tool: audit_code_quality target='{target_file}' budget={token_budget}",
            file=sys.stderr
        )
        
        # Verify file exists in repository
        all_files = project_repo.get_all_files()
        file_paths = [f["relative_path"] for f in all_files]
        
        if target_file not in file_paths:
            print(f"Warning: target_file '{target_file}' not found in indexed files", file=sys.stderr)
            # Continue anyway - might be in retrieved_abstracts from search
        
        # Construct RefactorGraphState
        initial_state = RefactorGraphState(
            target_file=target_file,
            token_budget_max=token_budget,
            retrieved_abstracts=[]  # Will be populated by pipeline if needed
        )
        
        # Execute refactoring pipeline
        pipeline = RefactoringPipelineGraph(db_path=db_path)
        final_state = pipeline.execute(initial_state)
        
        # Build response payload
        result = {
            "target_file": final_state.target_file,
            "quality_score": final_state.quality_score,
            "refactoring_priority": final_state.refactoring_priority,
            "detected_smells": final_state.detected_smells,
            "proposed_architecture": final_state.proposed_architecture,
            "done_condition": final_state.done_condition,
            "reasoning_steps": final_state.reasoning_steps[-5:]  # Last 5 steps for brevity
        }
        
        print(
            f"MCP Tool: audit_code_quality completed - "
            f"score={final_state.quality_score}, "
            f"smells={len(final_state.detected_smells)}, "
            f"proposals={len(final_state.proposed_architecture)}",
            file=sys.stderr
        )
        
        return result
        
    except Exception as e:
        print(f"Error in audit_code_quality: {e}", file=sys.stderr)
        raise


@mcp.tool()
def map_blast_radius(
    target_file: str,
    max_depth: int = 3,
    token_budget: int = 100000
) -> Dict[str, Any]:
    """
    Trace recursive reference paths and calculate system-wide change risk scores.
    
    Analyzes downstream dependency propagation to assess blast radius impact
    prior to code signature modification. This tool traces relational dependency
    propagation across the codebase using repository metadata only - no raw
    source code is accessed.
    
    The analysis identifies:
    - Direct dependents (files importing the target)
    - Indirect dependents (transitive dependencies up to max_depth)
    - Language boundary crossings (cross-language dependencies)
    - Architectural risk score (0.0 - 10.0)
    
    Args:
        target_file: The relative path of the file intended for modification
                     (e.g., "apps/ai-core/schemas/graph_state.py")
        max_depth: Depth limit ceiling tracking reference steps through the
                   dependency tree (default: 3, range: 1-5)
        token_budget: Budget constraints bounding the evaluation loop
                      execution parameters (default: 100000)
    
    Returns:
        Dictionary containing:
        - target_file: The analyzed file path
        - impacted_nodes: List of affected downstream modules with:
          - relative_path: File path
          - language: Programming language
          - depth: Distance separation index from target (1-based)
          - depends_on: Parent dependency
        - architectural_risk_score: Calculated danger index (0.0 - 10.0)
        - blast_radius_classification: Systemic impact classification
          (isolated, low, medium, high, critical)
        - max_traversal_depth: Depth limit used for analysis
        - done_condition: Whether analysis completed successfully
        - reasoning_steps: Chronological log of traversal progression
    """
    try:
        # Validate max_depth
        max_depth = max(1, min(5, max_depth))  # Clamp to 1-5
        
        print(
            f"MCP Tool: map_blast_radius target='{target_file}' "
            f"depth={max_depth} budget={token_budget}",
            file=sys.stderr
        )
        
        # Construct ImpactGraphState
        initial_state = ImpactGraphState(
            target_file=target_file,
            max_traversal_depth=max_depth,
            token_budget_max=token_budget
        )
        
        # Execute impact analysis pipeline
        pipeline = ImpactAnalysisGraph(db_path=db_path)
        final_state = pipeline.execute(initial_state)
        
        # Build response payload
        result = {
            "target_file": final_state.target_file,
            "impacted_nodes": final_state.impacted_nodes,
            "architectural_risk_score": final_state.architectural_risk_score,
            "blast_radius_classification": final_state.blast_radius_classification,
            "max_traversal_depth": final_state.max_traversal_depth,
            "done_condition": final_state.done_condition,
            "reasoning_steps": final_state.reasoning_steps[-5:]  # Last 5 steps for brevity
        }
        
        print(
            f"MCP Tool: map_blast_radius completed - "
            f"impacted={len(final_state.impacted_nodes)}, "
            f"risk={final_state.architectural_risk_score}, "
            f"classification={final_state.blast_radius_classification}",
            file=sys.stderr
        )
        
        return result
        
    except Exception as e:
        print(f"Error in map_blast_radius: {e}", file=sys.stderr)
        raise


# ============================================================================
# Server Entry Point
# ============================================================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="WikiHub MCP Server")
    parser.add_argument(
        '--transport',
        choices=['stdio', 'sse'],
        default='stdio',
        help='Transport protocol (stdio for AI editor pipes, sse for HTTP)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=None,
        help='HTTP port for SSE transport (default: 7000)'
    )
    args = parser.parse_args()

    if args.transport == 'sse':
        mcp.host = '0.0.0.0'
        if args.port is not None:
            mcp.port = args.port

    transport_desc = f"SSE on port {mcp.port}" if args.transport == 'sse' else "stdio"
    print(f"Starting WikiHub MCP Server on {transport_desc}...", file=sys.stderr)
    print(f"Database path: {db_path}", file=sys.stderr)
    print(f"ChromaDB path: {chromadb_dir}", file=sys.stderr)
    
    # Run the MCP server (blocks until termination)
    mcp.run(transport=args.transport)
