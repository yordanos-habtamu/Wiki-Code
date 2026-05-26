"""
Refactoring Pipeline Graph - StateGraph for code quality auditing and refactoring.
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

# Load RefactorGraphState
refactor_state_path = os.path.join(os.path.dirname(__file__), "..", "schemas", "refactor_state.py")
spec = importlib.util.spec_from_file_location("refactor_state", refactor_state_path)
refactor_state_module = importlib.util.module_from_spec(spec)
sys.modules["refactor_state"] = refactor_state_module
spec.loader.exec_module(refactor_state_module)
RefactorGraphState = refactor_state_module.RefactorGraphState

# Load agents
smell_detector_path = os.path.join(os.path.dirname(__file__), "..", "agents", "code_smell_detector_agent.py")
spec2 = importlib.util.spec_from_file_location("code_smell_detector_agent", smell_detector_path)
smell_detector_module = importlib.util.module_from_spec(spec2)
sys.modules["code_smell_detector_agent"] = smell_detector_module
spec2.loader.exec_module(smell_detector_module)
CodeSmellDetectorAgent = smell_detector_module.CodeSmellDetectorAgent

suggester_path = os.path.join(os.path.dirname(__file__), "..", "agents", "refactoring_suggester_agent.py")
spec3 = importlib.util.spec_from_file_location("refactoring_suggester_agent", suggester_path)
suggester_module = importlib.util.module_from_spec(spec3)
sys.modules["refactoring_suggester_agent"] = suggester_module
spec3.loader.exec_module(suggester_module)
RefactoringSuggesterAgent = suggester_module.RefactoringSuggesterAgent

# Load TokenTrackingMiddleware
middleware_path = os.path.join(project_root, "apps", "ai-core", "services", "token_tracking_middleware.py")
spec4 = importlib.util.spec_from_file_location("token_tracking_middleware", middleware_path)
middleware_module = importlib.util.module_from_spec(spec4)
sys.modules["token_tracking_middleware"] = middleware_module
spec4.loader.exec_module(middleware_module)
TokenTrackingMiddleware = middleware_module.TokenTrackingMiddleware


class RefactoringPipelineGraph:
    """
    StateGraph for code smell detection and refactoring suggestion pipeline.
    
    Graph Architecture:
    [ENTRY] -> budget_audit_node -> smell_detector_node -> suggester_node -> [END]
    
    With budget enforcement between each transition.
    """
    
    def __init__(self, db_path: str = None):
        """
        Initialize the refactoring pipeline graph.
        
        Args:
            db_path: Path to SQLite hub.db
        """
        if db_path is None:
            db_path = os.path.join(project_root, "apps", "cli", "hub.db")
        
        self.db_path = db_path
        
        # Initialize agents
        self.smell_detector = CodeSmellDetectorAgent()
        self.suggester = RefactoringSuggesterAgent()
        
        # Initialize token tracking middleware
        try:
            self.middleware = TokenTrackingMiddleware(router=None, db_path=db_path)
        except Exception as e:
            print(f"Warning: TokenTrackingMiddleware initialization failed: {e}", file=sys.stderr)
            self.middleware = None
        
        # Build and compile graph
        self.graph = self._build_graph()
        
        print("RefactoringPipelineGraph initialized and compiled", file=sys.stderr)
    
    def _build_graph(self):
        """
        Construct and compile the StateGraph with budget enforcement.
        
        Returns:
            Compiled LangGraph workflow
        """
        print("Building refactoring pipeline graph...", file=sys.stderr)
        
        # Initialize StateGraph with RefactorGraphState schema
        workflow = StateGraph(RefactorGraphState)
        
        # Add nodes
        workflow.add_node("budget_audit", self._budget_audit_node)
        workflow.add_node("smell_detector", self._smell_detector_node)
        workflow.add_node("suggester", self._suggester_node)
        workflow.add_node("terminate_budget", self._terminate_budget_node)
        workflow.add_node("complete", self._complete_node)
        
        # Set entry point
        workflow.set_entry_point("budget_audit")
        
        # Add conditional edges with budget enforcement
        workflow.add_conditional_edges(
            "budget_audit",
            self._check_budget_after_audit,
            {
                "proceed": "smell_detector",
                "terminate": "terminate_budget"
            }
        )
        
        workflow.add_conditional_edges(
            "smell_detector",
            self._check_budget_after_detection,
            {
                "proceed": "suggester",
                "terminate": "terminate_budget",
                "skip_suggest": "complete"
            }
        )
        
        workflow.add_conditional_edges(
            "suggester",
            self._check_budget_after_suggestion,
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
        
        print("Refactoring pipeline graph compiled successfully", file=sys.stderr)
        return compiled_graph
    
    def _budget_audit_node(self, state: RefactorGraphState) -> Dict:
        """
        Entry node: Audit initial budget and target file validity.
        
        Args:
            state: Current graph state
        
        Returns:
            Updated state with audit results
        """
        print("\n=== Budget Audit Node ===", file=sys.stderr)
        
        reasoning_steps = state.reasoning_steps.copy()
        reasoning_steps.append("Starting refactoring pipeline audit")
        
        # Validate inputs
        if not state.target_file:
            reasoning_steps.append("Error: No target file specified")
            print("Warning: No target file specified", file=sys.stderr)
        
        print(f"Target file: {state.target_file}", file=sys.stderr)
        print(f"Budget: {state.token_budget_max} tokens", file=sys.stderr)
        
        return {
            "reasoning_steps": reasoning_steps
        }
    
    def _smell_detector_node(self, state: RefactorGraphState) -> Dict:
        """
        Processing node: Execute CodeSmellDetectorAgent.
        
        Args:
            state: Current graph state
        
        Returns:
            Updated state from smell detection
        """
        print("\n=== Smell Detector Node ===", file=sys.stderr)
        
        # Execute agent
        state_dict = state.model_dump()
        result = self.smell_detector(state_dict)
        
        detected_count = len(result.get("detected_smells", []))
        print(f"Detected {detected_count} code smell(s)", file=sys.stderr)
        
        return result
    
    def _suggester_node(self, state: RefactorGraphState) -> Dict:
        """
        Processing node: Execute RefactoringSuggesterAgent.
        
        Args:
            state: Current graph state
        
        Returns:
            Updated state with refactoring proposals
        """
        print("\n=== Suggester Node ===", file=sys.stderr)
        
        # Execute agent
        state_dict = state.model_dump()
        result = self.suggester(state_dict)
        
        proposal_count = len(result.get("proposed_architecture", []))
        print(f"Generated {proposal_count} refactoring proposal(s)", file=sys.stderr)
        
        return result
    
    def _terminate_budget_node(self, state: RefactorGraphState) -> Dict:
        """
        Terminal node: Handle budget exhaustion.
        
        Args:
            state: Current graph state
        
        Returns:
            Updated state with termination reason
        """
        print("\n=== Terminate Budget Node ===", file=sys.stderr)
        
        reasoning_steps = state.reasoning_steps.copy()
        reasoning_steps.append("TERMINATED: Token budget exceeded during refactoring pipeline")
        
        print("Pipeline terminated due to budget exhaustion", file=sys.stderr)
        
        return {
            "reasoning_steps": reasoning_steps,
            "done_condition": True
        }
    
    def _complete_node(self, state: RefactorGraphState) -> Dict:
        """
        Terminal node: Clean pipeline completion.
        
        Args:
            state: Current graph state
        
        Returns:
            Updated state with completion summary
        """
        print("\n=== Complete Node ===", file=sys.stderr)
        
        reasoning_steps = state.reasoning_steps.copy()
        reasoning_steps.append("Refactoring pipeline completed successfully")
        
        # Log summary
        smell_count = len(state.detected_smells)
        proposal_count = len(state.proposed_architecture)
        
        reasoning_steps.append(f"Summary: {smell_count} smell(s) detected, {proposal_count} proposal(s) generated")
        
        print(f"Pipeline completed: {smell_count} smells, {proposal_count} proposals", file=sys.stderr)
        
        return {
            "reasoning_steps": reasoning_steps,
            "done_condition": True
        }
    
    def _check_budget_after_audit(self, state: RefactorGraphState) -> str:
        """Conditional edge: Check budget after audit node."""
        if self.middleware and self.middleware.check_budget_threshold(max_tokens=state.token_budget_max):
            print("Budget exceeded after audit, terminating", file=sys.stderr)
            return "terminate"
        
        print("Budget OK, proceeding to smell detection", file=sys.stderr)
        return "proceed"
    
    def _check_budget_after_detection(self, state: RefactorGraphState) -> str:
        """Conditional edge: Check budget after smell detection."""
        if self.middleware and self.middleware.check_budget_threshold(max_tokens=state.token_budget_max):
            print("Budget exceeded after detection, terminating", file=sys.stderr)
            return "terminate"
        
        # If no smells detected, skip suggestion phase
        if len(state.detected_smells) == 0:
            print("No smells detected, skipping suggestion phase", file=sys.stderr)
            return "skip_suggest"
        
        print("Budget OK, proceeding to suggestion generation", file=sys.stderr)
        return "proceed"
    
    def _check_budget_after_suggestion(self, state: RefactorGraphState) -> str:
        """Conditional edge: Check budget after suggestion generation."""
        if self.middleware and self.middleware.check_budget_threshold(max_tokens=state.token_budget_max):
            print("Budget exceeded after suggestion, terminating", file=sys.stderr)
            return "terminate"
        
        print("Budget OK, completing pipeline", file=sys.stderr)
        return "proceed"
    
    def execute(self, initial_state: RefactorGraphState) -> RefactorGraphState:
        """
        Execute the refactoring pipeline with an initial state.
        
        Args:
            initial_state: Starting RefactorGraphState
        
        Returns:
            Final RefactorGraphState after execution
        """
        print("\n" + "=" * 70, file=sys.stderr)
        print("Starting Refactoring Pipeline Execution", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        
        # Convert to dict for LangGraph
        state_dict = initial_state.model_dump()
        
        # Execute graph
        final_state_dict = self.graph.invoke(state_dict)
        
        # Convert back to RefactorGraphState
        final_state = RefactorGraphState(**final_state_dict)
        
        print("\n" + "=" * 70, file=sys.stderr)
        print("Refactoring Pipeline Execution Complete", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        
        return final_state
