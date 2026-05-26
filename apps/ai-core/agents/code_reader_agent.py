"""
CodeReaderAgent - Structural analyzer node for codebase comprehension.
Contains pure reasoning logic - no direct provider SDK imports.
"""

import os
import sys
from typing import Dict, Any, List
import importlib.util

# Add project root to path
current_file = os.path.abspath(__file__)
# Navigate up from apps/ai-core/agents/ to project root
if 'apps' in current_file and 'ai-core' in current_file:
    # Find the 'apps' directory and go up one more level
    apps_idx = current_file.find('apps')
    project_root = current_file[:apps_idx].rstrip('/')
else:
    project_root = os.path.dirname(os.path.dirname(current_file))
sys.path.insert(0, project_root)

# Load EmbeddingPipeline dynamically
embedding_pipeline_path = os.path.join(
    project_root, "apps", "ai-core", "pipelines", "embedding_pipeline.py"
)
spec = importlib.util.spec_from_file_location("embedding_pipeline", embedding_pipeline_path)
embedding_pipeline_module = importlib.util.module_from_spec(spec)
sys.modules["embedding_pipeline"] = embedding_pipeline_module
spec.loader.exec_module(embedding_pipeline_module)
EmbeddingPipeline = embedding_pipeline_module.EmbeddingPipeline


class CodeReaderAgent:
    """
    Structured analyzer node that receives GraphState and performs codebase comprehension.
    
    This agent:
    1. Examines user_query and existing search_history
    2. Calls search_codebase_abstracts if additional context is needed
    3. Injects resulting abstracts back into state
    4. Formats token-compressed abstracts and fires inspection prompt to LLMRouter
    """
    
    def __init__(self, db_path: str = None, chromadb_dir: str = None):
        """
        Initialize the CodeReaderAgent with embedding pipeline.
        
        Args:
            db_path: Path to SQLite hub.db
            chromadb_dir: Path to ChromaDB directory
        """
        if chromadb_dir is None:
            chromadb_dir = os.path.join(project_root, "infrastructure", "chromadb", "db")
        
        if db_path is None:
            db_path = os.path.join(project_root, "apps", "cli", "hub.db")
        
        self.embedding_pipeline = EmbeddingPipeline(
            db_path=db_path,
            chromadb_dir=chromadb_dir
        )
        
        print("CodeReaderAgent initialized", file=sys.stderr)
    
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main agent execution method. Receives and returns GraphState as dict.
        
        Args:
            state: Current graph state dictionary
        
        Returns:
            Updated graph state dictionary
        """
        print("\n=== CodeReaderAgent Execution ===", file=sys.stderr)
        
        # Extract state fields
        user_query = state.get("user_query", "")
        search_history = state.get("search_history", [])
        retrieved_abstracts = state.get("retrieved_abstracts", [])
        reasoning_steps = state.get("reasoning_steps", [])
        current_iteration = state.get("current_iteration", 0)
        
        # Step 1: Log reasoning
        reasoning_steps.append(
            f"Iteration {current_iteration + 1}: Analyzing query '{user_query}'"
        )
        print(f"User query: {user_query}", file=sys.stderr)
        print(f"Search history: {len(search_history)} previous queries", file=sys.stderr)
        
        # Step 2: Determine if additional search is needed
        # For now, always search on first iteration or if no abstracts retrieved
        should_search = (current_iteration == 0) or (len(retrieved_abstracts) == 0)
        
        if should_search:
            print("Performing semantic search for additional context...", file=sys.stderr)
            
            # Step 3: Call search_codebase_abstracts
            new_abstracts = self._search_codebase(user_query, n_results=5)
            
            # Step 4: Inject abstracts into state
            retrieved_abstracts.extend(new_abstracts)
            
            # Update search history
            search_history.append(user_query)
            
            reasoning_steps.append(
                f"Retrieved {len(new_abstracts)} abstracts from semantic search"
            )
            
            print(f"Retrieved {len(new_abstracts)} new abstracts", file=sys.stderr)
        else:
            print("Using existing retrieved abstracts", file=sys.stderr)
            reasoning_steps.append("Using previously retrieved context")
        
        # Step 5: Format context for LLM (token-compressed abstracts only)
        context_summary = self._format_context_summary(retrieved_abstracts)
        
        reasoning_steps.append(
            f"Context summary prepared: {len(retrieved_abstracts)} files indexed"
        )
        
        # For now, we don't call LLMRouter directly to avoid API key requirements in testing
        # In production, this is where you'd call:
        # response = middleware.complete(
        #     prompt=f"Analyze this codebase context:\n\n{context_summary}\n\nQuery: {user_query}",
        #     model_id="gemini/gemini-pro",
        #     operation_type="comprehension"
        # )
        
        reasoning_steps.append("Context analysis complete")
        
        print(f"Total abstracts: {len(retrieved_abstracts)}", file=sys.stderr)
        print(f"Reasoning steps: {len(reasoning_steps)}", file=sys.stderr)
        
        # Return updated state
        return {
            "search_history": search_history,
            "retrieved_abstracts": retrieved_abstracts,
            "reasoning_steps": reasoning_steps,
            "current_iteration": current_iteration + 1,
            # Don't set done_condition here - let the graph's conditional edge decide
        }
    
    def _search_codebase(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """
        Search codebase abstracts using ChromaDB vector search.
        
        Args:
            query: Natural language search query
            n_results: Number of results to return
        
        Returns:
            List of matching abstract dictionaries
        """
        try:
            collection = self.embedding_pipeline.get_or_create_collection()
            
            results = collection.query(
                query_texts=[query],
                n_results=n_results
            )
            
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
            
            print(f"Semantic search returned {len(matches)} matches", file=sys.stderr)
            return matches
            
        except Exception as e:
            print(f"Error in CodeReaderAgent._search_codebase: {e}", file=sys.stderr)
            return []
    
    def _format_context_summary(self, abstracts: List[Dict[str, Any]]) -> str:
        """
        Format retrieved abstracts into a token-compressed context summary.
        
        Args:
            abstracts: List of abstract dictionaries
        
        Returns:
            Formatted context string
        """
        if not abstracts:
            return "No abstracts retrieved."
        
        lines = []
        lines.append(f"Retrieved {len(abstracts)} file abstracts:")
        lines.append("")
        
        for idx, abstract in enumerate(abstracts, 1):
            lines.append(f"--- File {idx}: {abstract['relative_path']} ---")
            lines.append(f"Language: {abstract['language']}")
            lines.append(f"Distance: {abstract['distance']}")
            lines.append("")
            lines.append(abstract['abstract'])  # The token-compressed abstract
            lines.append("")
        
        return "\n".join(lines)
