"""
Comprehension Graph - LangGraph StateGraph for codebase analysis workflows.
Manages execution state, conditional transitions, and token budget enforcement.
"""

import os
import sys
from typing import Literal, Dict
import importlib.util

# Add project root to path
current_file = os.path.abspath(__file__)
# Navigate up from apps/ai-core/graphs/ to project root
if 'apps' in current_file and 'ai-core' in current_file:
    # Find the 'apps' directory and go up one more level
    apps_idx = current_file.find('apps')
    project_root = current_file[:apps_idx].rstrip('/')
else:
    project_root = os.path.dirname(os.path.dirname(current_file))
sys.path.insert(0, project_root)

# Install langgraph if not available
try:
    from langgraph.graph import StateGraph, END
except ImportError:
    print("Error: langgraph package not installed. Run: pip install langgraph", file=sys.stderr)
    sys.exit(1)

# Load GraphState
graph_state_path = os.path.join(os.path.dirname(__file__), "..", "schemas", "graph_state.py")
spec = importlib.util.spec_from_file_location("graph_state", graph_state_path)
graph_state_module = importlib.util.module_from_spec(spec)
sys.modules["graph_state"] = graph_state_module
spec.loader.exec_module(graph_state_module)
GraphState = graph_state_module.GraphState

# Load CodeReaderAgent
code_reader_path = os.path.join(os.path.dirname(__file__), "..", "agents", "code_reader_agent.py")
spec2 = importlib.util.spec_from_file_location("code_reader_agent", code_reader_path)
code_reader_module = importlib.util.module_from_spec(spec2)
sys.modules["code_reader_agent"] = code_reader_module
spec2.loader.exec_module(code_reader_module)
CodeReaderAgent = code_reader_module.CodeReaderAgent

# Load TokenTrackingMiddleware
middleware_path = os.path.join(
    project_root, "apps", "ai-core", "services", "token_tracking_middleware.py"
)
spec3 = importlib.util.spec_from_file_location("token_tracking_middleware", middleware_path)
middleware_module = importlib.util.module_from_spec(spec3)
sys.modules["token_tracking_middleware"] = middleware_module
spec3.loader.exec_module(middleware_module)
TokenTrackingMiddleware = middleware_module.TokenTrackingMiddleware


class ComprehensionGraph:
    """
    StateGraph configuration for codebase comprehension workflows.
    
    Graph Architecture:
    - Entry Node: Evaluation filter to check project status
    - Processing Node: CodeReaderAgent reasoning step
    - Conditional Edge: should_continue checks budget and done_condition
    """
    
    def __init__(self, db_path: str = None, chromadb_dir: str = None):
        """
        Initialize the comprehension graph with all dependencies.
        
        Args:
            db_path: Path to SQLite hub.db
            chromadb_dir: Path to ChromaDB directory
        """
        if db_path is None:
            db_path = os.path.join(project_root, "apps", "cli", "hub.db")
        
        if chromadb_dir is None:
            chromadb_dir = os.path.join(project_root, "infrastructure", "chromadb", "db")
        
        self.db_path = db_path
        self.chromadb_dir = chromadb_dir
        
        # Initialize agent
        self.agent = CodeReaderAgent(db_path=db_path, chromadb_dir=chromadb_dir)
        
        # Initialize token tracking middleware
        try:
            self.middleware = TokenTrackingMiddleware(
                router=None,  # Will be initialized inside middleware
                db_path=db_path
            )
        except Exception as e:
            print(f"Warning: TokenTrackingMiddleware initialization failed: {e}", file=sys.stderr)
            self.middleware = None
        
        # Build and compile graph
        self.graph = self._build_graph()
        
        print("ComprehensionGraph initialized and compiled", file=sys.stderr)
    
    def _build_graph(self):
        """
        Construct and compile the StateGraph.
        
        Returns:
            Compiled LangGraph workflow
        """
        print("Building comprehension graph...", file=sys.stderr)
        
        # Initialize StateGraph with GraphState schema
        workflow = StateGraph(GraphState)
        
        # Add nodes
        workflow.add_node("evaluate", self._evaluate_node)
        workflow.add_node("analyze", self._analyze_node)
        workflow.add_node("terminate_budget", self._terminate_budget_node)
        workflow.add_node("end_workflow", self._end_workflow_node)
        
        # Set entry point
        workflow.set_entry_point("evaluate")
        
        # Add conditional edges
        workflow.add_conditional_edges(
            "evaluate",
            self._should_proceed,
            {
                "analyze": "analyze",
                "end_workflow": "end_workflow"
            }
        )
        
        workflow.add_conditional_edges(
            "analyze",
            self._should_continue,
            {
                "continue_analysis": "analyze",
                "terminate_budget_exceeded": "terminate_budget",
                "end_workflow": "end_workflow"
            }
        )
        
        # Terminal nodes lead to END
        workflow.add_edge("terminate_budget", END)
        workflow.add_edge("end_workflow", END)
        
        # Compile graph
        compiled_graph = workflow.compile()
        
        print("Graph compiled successfully", file=sys.stderr)
        return compiled_graph
    
    def _evaluate_node(self, state: GraphState) -> Dict:
        """
        Entry node: Evaluate project status and query validity.
        
        Args:
            state: Current graph state
        
        Returns:
            Updated state with evaluation results
        """
        print("\n=== Evaluate Node ===", file=sys.stderr)
        
        reasoning_steps = state.reasoning_steps.copy()
        reasoning_steps.append("Evaluating project path and user query")
        
        # Validate inputs
        if not state.user_query:
            reasoning_steps.append("Error: Empty user query")
            print("Warning: Empty user query", file=sys.stderr)
        
        if not state.project_path:
            reasoning_steps.append("Warning: No project path specified")
            print("Warning: No project path specified", file=sys.stderr)
        
        print(f"Project: {state.project_path}", file=sys.stderr)
        print(f"Query: {state.user_query}", file=sys.stderr)
        print(f"Budget: {state.token_budget_max} tokens", file=sys.stderr)
        
        return {
            "reasoning_steps": reasoning_steps
        }
    
    def _analyze_node(self, state: GraphState) -> Dict:
        """
        Processing node: Execute CodeReaderAgent reasoning step.
        
        Args:
            state: Current graph state
        
        Returns:
            Updated state from agent execution
        """
        print("\n=== Analyze Node ===", file=sys.stderr)
        
        # Execute agent
        state_dict = state.model_dump()
        result = self.agent(state_dict)
        
        print(f"Agent completed iteration {result.get('current_iteration', 0)}", file=sys.stderr)
        
        return result
    
    def _terminate_budget_node(self, state: GraphState) -> Dict:
        """
        Terminal node: Handle budget exhaustion.
        
        Args:
            state: Current graph state
        
        Returns:
            Updated state with termination reason
        """
        print("\n=== Terminate Budget Node ===", file=sys.stderr)
        
        reasoning_steps = state.reasoning_steps.copy()
        reasoning_steps.append("TERMINATED: Token budget exceeded")
        
        print("Graph terminated due to budget exhaustion", file=sys.stderr)
        
        return {
            "reasoning_steps": reasoning_steps,
            "done_condition": True
        }
    
    def _end_workflow_node(self, state: GraphState) -> Dict:
        """
        Terminal node: Clean workflow completion.
        
        Args:
            state: Current graph state
        
        Returns:
            Updated state with completion status
        """
        print("\n=== End Workflow Node ===", file=sys.stderr)
        
        reasoning_steps = state.reasoning_steps.copy()
        reasoning_steps.append("Workflow completed successfully")
        
        print("Graph completed successfully", file=sys.stderr)
        
        return {
            "reasoning_steps": reasoning_steps,
            "done_condition": True
        }
    
    def _should_proceed(self, state: GraphState) -> str:
        """
        Conditional edge: Check if we should proceed with analysis.
        
        Args:
            state: Current graph state
        
        Returns:
            Next node name
        """
        # Check if query is valid
        if not state.user_query:
            print("No query provided, ending workflow", file=sys.stderr)
            return "end_workflow"
        
        # Check budget before starting
        if self.middleware and self.middleware.check_budget_threshold(
            max_tokens=state.token_budget_max
        ):
            print("Budget exceeded before starting, terminating", file=sys.stderr)
            return "end_workflow"
        
        print("Proceeding with analysis", file=sys.stderr)
        return "analyze"
    
    def _should_continue(self, state: GraphState) -> str:
        """
        Conditional edge: Assess whether to continue, terminate, or end.
        
        This is the critical budget enforcement point per Constitution 2.2.
        
        Args:
            state: Current graph state
        
        Returns:
            Next node name
        """
        # Check tracking budget threshold through middleware interceptor
        if self.middleware and self.middleware.check_budget_threshold(
            max_tokens=state.token_budget_max
        ):
            print("Budget exceeded during execution, terminating", file=sys.stderr)
            return "terminate_budget_exceeded"
        
        # Check if agent marked workflow as done
        if state.done_condition:
            print("Agent marked workflow as done", file=sys.stderr)
            return "end_workflow"
        
        # Check iteration limit (safety valve)
        if state.current_iteration >= 10:
            print("Max iterations reached (10), ending workflow", file=sys.stderr)
            return "end_workflow"
        
        # Continue analysis loop
        print("Continuing analysis loop", file=sys.stderr)
        return "continue_analysis"
    
    def execute(self, initial_state: GraphState) -> GraphState:
        """
        Execute the comprehension graph with an initial state.
        
        Args:
            initial_state: Starting GraphState
        
        Returns:
            Final GraphState after execution
        """
        print("\n" + "=" * 70, file=sys.stderr)
        print("Starting Comprehension Graph Execution", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        
        # Convert to dict for LangGraph
        state_dict = initial_state.model_dump()
        
        # Execute graph
        final_state_dict = self.graph.invoke(state_dict)
        
        # Convert back to GraphState
        final_state = GraphState(**final_state_dict)
        
        print("\n" + "=" * 70, file=sys.stderr)
        print("Comprehension Graph Execution Complete", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        
        return final_state
