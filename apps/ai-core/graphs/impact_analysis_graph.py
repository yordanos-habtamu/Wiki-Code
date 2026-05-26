"""
Impact Analysis Graph - StateGraph for blast radius analysis and dependency impact mapping.
Enforces hard resource verification bounds at every transition step.
"""

import os
import sys
from typing import Dict
import importlib.util

# Add project root to path
current_file = os.path.abspath(__file__)
if 'apps' in current_file and 'ai-core' in current_file:
    apps_idx = current_file.find('apps')
    project_root = current_file[:apps_idx].rstrip('/')
else:
    project_root = os.path.dirname(os.path.dirname(current_file))
sys.path.insert(0, project_root)

# Install langgraph if not available
try:
    from langgraph.graph import StateGraph, END
except ImportError:
    print("Error: langgraph package not installed", file=sys.stderr)
    sys.exit(1)

# Load ImpactGraphState
impact_state_path = os.path.join(os.path.dirname(__file__), "..", "schemas", "impact_state.py")
spec = importlib.util.spec_from_file_location("impact_state", impact_state_path)
impact_state_module = importlib.util.module_from_spec(spec)
sys.modules["impact_state"] = impact_state_module
spec.loader.exec_module(impact_state_module)
ImpactGraphState = impact_state_module.ImpactGraphState

# Load BlastRadiusAnalyzerAgent
analyzer_path = os.path.join(os.path.dirname(__file__), "..", "agents", "blast_radius_analyzer_agent.py")
spec2 = importlib.util.spec_from_file_location("blast_radius_analyzer_agent", analyzer_path)
analyzer_module = importlib.util.module_from_spec(spec2)
sys.modules["blast_radius_analyzer_agent"] = analyzer_module
spec2.loader.exec_module(analyzer_module)
BlastRadiusAnalyzerAgent = analyzer_module.BlastRadiusAnalyzerAgent

# Load TokenTrackingMiddleware
middleware_path = os.path.join(project_root, "apps", "ai-core", "services", "token_tracking_middleware.py")
spec3 = importlib.util.spec_from_file_location("token_tracking_middleware", middleware_path)
middleware_module = importlib.util.module_from_spec(spec3)
sys.modules["token_tracking_middleware"] = middleware_module
spec3.loader.exec_module(middleware_module)
TokenTrackingMiddleware = middleware_module.TokenTrackingMiddleware


class ImpactAnalysisGraph:
    """
    StateGraph for blast radius analysis and architectural impact mapping.
    
    Graph Architecture:
    [ENTRY] -> initial_budget_node -> dependency_traversal_node -> risk_scoring_node -> [END]
    
    With budget enforcement between each transition.
    """
    
    def __init__(self, db_path: str = None):
        """
        Initialize the impact analysis graph.
        
        Args:
            db_path: Path to SQLite hub.db
        """
        if db_path is None:
            db_path = os.path.join(project_root, "apps", "cli", "hub.db")
        
        self.db_path = db_path
        
        # Initialize blast radius analyzer
        self.analyzer = BlastRadiusAnalyzerAgent(db_path=db_path)
        
        # Initialize token tracking middleware
        try:
            self.middleware = TokenTrackingMiddleware(router=None, db_path=db_path)
        except Exception as e:
            print(f"Warning: TokenTrackingMiddleware initialization failed: {e}", file=sys.stderr)
            self.middleware = None
        
        # Build and compile graph
        self.graph = self._build_graph()
        
        print("ImpactAnalysisGraph initialized and compiled", file=sys.stderr)
    
    def _build_graph(self):
        """
        Construct and compile the StateGraph with budget enforcement.
        
        Returns:
            Compiled LangGraph workflow
        """
        print("Building impact analysis graph...", file=sys.stderr)
        
        # Initialize StateGraph with ImpactGraphState schema
        workflow = StateGraph(ImpactGraphState)
        
        # Add nodes
        workflow.add_node("initial_budget", self._initial_budget_node)
        workflow.add_node("dependency_traversal", self._dependency_traversal_node)
        workflow.add_node("risk_scoring", self._risk_scoring_node)
        workflow.add_node("terminate_budget", self._terminate_budget_node)
        workflow.add_node("complete", self._complete_node)
        
        # Set entry point
        workflow.set_entry_point("initial_budget")
        
        # Add conditional edges with budget enforcement
        workflow.add_conditional_edges(
            "initial_budget",
            self._check_budget_after_initial,
            {
                "proceed": "dependency_traversal",
                "terminate": "terminate_budget"
            }
        )
        
        workflow.add_conditional_edges(
            "dependency_traversal",
            self._check_budget_after_traversal,
            {
                "proceed": "risk_scoring",
                "terminate": "terminate_budget"
            }
        )
        
        workflow.add_conditional_edges(
            "risk_scoring",
            self._check_budget_after_scoring,
            {
                "proceed": "complete",
                "terminate": "terminate_budget"
            }
        )
        
        # Terminal nodes lead to END
        workflow.add_edge("terminate_budget", END)
        workflow.add_edge("complete", END)
        
        # Compile graph
        compiled_graph = workflow.compile()
        
        print("Impact analysis graph compiled successfully", file=sys.stderr)
        return compiled_graph
    
    def _initial_budget_node(self, state: ImpactGraphState) -> Dict:
        """
        Entry node: Audit initial budget and validate target file.
        
        Args:
            state: Current graph state
        
        Returns:
            Updated state with audit results
        """
        print("\n=== Initial Budget Node ===", file=sys.stderr)
        
        reasoning_steps = state.reasoning_steps.copy()
        reasoning_steps.append("Starting impact analysis pipeline audit")
        
        # Validate inputs
        if not state.target_file:
            reasoning_steps.append("Error: No target file specified")
            print("Warning: No target file specified", file=sys.stderr)
        
        print(f"Target file: {state.target_file}", file=sys.stderr)
        print(f"Budget: {state.token_budget_max} tokens", file=sys.stderr)
        print(f"Max traversal depth: {state.max_traversal_depth}", file=sys.stderr)
        
        return {
            "reasoning_steps": reasoning_steps
        }
    
    def _dependency_traversal_node(self, state: ImpactGraphState) -> Dict:
        """
        Processing node: Execute BlastRadiusAnalyzerAgent for recursive traversal.
        
        Args:
            state: Current graph state
        
        Returns:
            Updated state from blast radius analysis
        """
        print("\n=== Dependency Traversal Node ===", file=sys.stderr)
        
        # Execute analyzer
        state_dict = state.model_dump()
        result = self.analyzer(state_dict)
        
        impacted_count = len(result.get("impacted_nodes", []))
        print(f"Found {impacted_count} impacted node(s)", file=sys.stderr)
        
        return result
    
    def _risk_scoring_node(self, state: ImpactGraphState) -> Dict:
        """
        Processing node: Calculate and finalize risk scoring.
        
        Args:
            state: Current graph state
        
        Returns:
            Updated state with final risk metrics
        """
        print("\n=== Risk Scoring Node ===", file=sys.stderr)
        
        reasoning_steps = state.reasoning_steps.copy()
        
        # Risk score already calculated by BlastRadiusAnalyzerAgent
        risk_score = state.architectural_risk_score
        classification = state.blast_radius_classification
        
        reasoning_steps.append(f"Final risk score: {risk_score}/10.0")
        reasoning_steps.append(f"Final classification: {classification}")
        
        # Log summary
        impacted_count = len(state.impacted_nodes)
        reasoning_steps.append(f"Impact analysis complete: {impacted_count} node(s) impacted")
        
        print(f"Risk score: {risk_score}/10.0", file=sys.stderr)
        print(f"Classification: {classification}", file=sys.stderr)
        print(f"Total impacted nodes: {impacted_count}", file=sys.stderr)
        
        # Print impacted nodes summary
        if state.impacted_nodes:
            print("\nImpacted Nodes Summary:", file=sys.stderr)
            for node in state.impacted_nodes:
                depth = node.get("depth", "?")
                path = node.get("relative_path", "unknown")
                lang = node.get("language", "unknown")
                print(f"  Depth {depth}: {path} ({lang})", file=sys.stderr)
        
        return {
            "reasoning_steps": reasoning_steps
        }
    
    def _terminate_budget_node(self, state: ImpactGraphState) -> Dict:
        """
        Terminal node: Handle budget exhaustion.
        
        Args:
            state: Current graph state
        
        Returns:
            Updated state with termination reason
        """
        print("\n=== Terminate Budget Node ===", file=sys.stderr)
        
        reasoning_steps = state.reasoning_steps.copy()
        reasoning_steps.append("TERMINATED: Token budget exceeded during impact analysis")
        
        print("Pipeline terminated due to budget exhaustion", file=sys.stderr)
        
        return {
            "reasoning_steps": reasoning_steps,
            "done_condition": True
        }
    
    def _complete_node(self, state: ImpactGraphState) -> Dict:
        """
        Terminal node: Clean pipeline completion.
        
        Args:
            state: Current graph state
        
        Returns:
            Updated state with completion summary
        """
        print("\n=== Complete Node ===", file=sys.stderr)
        
        reasoning_steps = state.reasoning_steps.copy()
        reasoning_steps.append("Impact analysis pipeline completed successfully")
        
        # Log summary
        impacted_count = len(state.impacted_nodes)
        reasoning_steps.append(
            f"Summary: {impacted_count} node(s) impacted, "
            f"risk={state.architectural_risk_score}/10.0, "
            f"classification={state.blast_radius_classification}"
        )
        
        print(
            f"Pipeline completed: {impacted_count} impacted, "
            f"risk={state.architectural_risk_score}, "
            f"classification={state.blast_radius_classification}",
            file=sys.stderr
        )
        
        return {
            "reasoning_steps": reasoning_steps,
            "done_condition": True
        }
    
    def _check_budget_after_initial(self, state: ImpactGraphState) -> str:
        """Conditional edge: Check budget after initial budget node."""
        if self.middleware and self.middleware.check_budget_threshold(max_tokens=state.token_budget_max):
            print("Budget exceeded after initial audit, terminating", file=sys.stderr)
            return "terminate"
        
        print("Budget OK, proceeding to dependency traversal", file=sys.stderr)
        return "proceed"
    
    def _check_budget_after_traversal(self, state: ImpactGraphState) -> str:
        """Conditional edge: Check budget after dependency traversal."""
        if self.middleware and self.middleware.check_budget_threshold(max_tokens=state.token_budget_max):
            print("Budget exceeded after traversal, terminating", file=sys.stderr)
            return "terminate"
        
        print("Budget OK, proceeding to risk scoring", file=sys.stderr)
        return "proceed"
    
    def _check_budget_after_scoring(self, state: ImpactGraphState) -> str:
        """Conditional edge: Check budget after risk scoring."""
        if self.middleware and self.middleware.check_budget_threshold(max_tokens=state.token_budget_max):
            print("Budget exceeded after scoring, terminating", file=sys.stderr)
            return "terminate"
        
        print("Budget OK, completing analysis", file=sys.stderr)
        return "proceed"
    
    def execute(self, initial_state: ImpactGraphState) -> ImpactGraphState:
        """
        Execute the impact analysis pipeline with an initial state.
        
        Args:
            initial_state: Starting ImpactGraphState
        
        Returns:
            Final ImpactGraphState after execution
        """
        print("\n" + "=" * 70, file=sys.stderr)
        print("Starting Impact Analysis Pipeline Execution", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        
        # Convert to dict for LangGraph
        state_dict = initial_state.model_dump()
        
        # Execute graph
        final_state_dict = self.graph.invoke(state_dict)
        
        # Convert back to ImpactGraphState
        final_state = ImpactGraphState(**final_state_dict)
        
        print("\n" + "=" * 70, file=sys.stderr)
        print("Impact Analysis Pipeline Execution Complete", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        
        return final_state
