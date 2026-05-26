"""
Refactor Graph State Schema - Extended state for code quality and refactoring workflows.
Composes foundational GraphState properties with code evolution tracking details.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import importlib.util
import os

# Load base GraphState
current_file = os.path.abspath(__file__)
if 'apps' in current_file and 'ai-core' in current_file:
    apps_idx = current_file.find('apps')
    project_root = current_file[:apps_idx].rstrip('/')
else:
    project_root = os.path.dirname(os.path.dirname(current_file))

graph_state_path = os.path.join(project_root, "apps", "ai-core", "schemas", "graph_state.py")
spec = importlib.util.spec_from_file_location("graph_state", graph_state_path)
graph_state_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(graph_state_module)
GraphState = graph_state_module.GraphState


class RefactorGraphState(BaseModel):
    """
    Extended state model for code smell detection and refactoring workflows.
    
    Composes base GraphState properties with specialized fields for:
    - Target file tracking
    - Detected anti-patterns
    - Proposed architectural improvements
    - Budget enforcement
    """
    
    # Base state composition (manually included for simplicity)
    project_path: str = Field(
        default="",
        description="The current local codebase reference string"
    )
    
    user_query: str = Field(
        default="",
        description="The original incoming exploration task request string"
    )
    
    search_history: List[str] = Field(
        default_factory=list,
        description="List of past semantic search query words executed by the nodes"
    )
    
    retrieved_abstracts: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Array dictionary tracking files discovered through vector queries"
    )
    
    reasoning_steps: List[str] = Field(
        default_factory=list,
        description="Chronological log tracking the agent's internal thought progression"
    )
    
    token_budget_max: int = Field(
        default=100000,
        description="Strict execution ceiling monitoring metrics"
    )
    
    done_condition: bool = Field(
        default=False,
        description="Termination signal flag"
    )
    
    current_iteration: int = Field(
        default=0,
        description="Current loop iteration count"
    )
    
    last_error: Optional[str] = Field(
        default=None,
        description="Last error encountered during graph execution"
    )
    
    # Refactoring-specific fields
    target_file: str = Field(
        default="",
        description="The relative system path of the target module being evaluated"
    )
    
    detected_smells: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Array listing classified anti-patterns with severity and description"
    )
    
    proposed_architecture: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Clean text-based signature re-allocations preserving backwards compatibility"
    )
    
    quality_score: Optional[float] = Field(
        default=None,
        description="Overall code quality score (0.0 - 10.0)"
    )
    
    refactoring_priority: str = Field(
        default="medium",
        description="Priority level: low, medium, high, critical"
    )
    
    class Config:
        """Pydantic configuration for immutability and validation."""
        validate_assignment = True
        extra = "forbid"
    
    def add_detected_smell(self, smell: Dict[str, Any]):
        """Append a detected code smell to the array."""
        self.detected_smells.append(smell)
    
    def add_proposed_architecture(self, proposal: Dict[str, Any]):
        """Add a refactoring proposal to the architecture list."""
        self.proposed_architecture.append(proposal)
    
    def add_reasoning_step(self, step: str):
        """Log a reasoning step."""
        self.reasoning_steps.append(step)
    
    def increment_iteration(self):
        """Increment the iteration counter."""
        self.current_iteration += 1
    
    def mark_done(self, reason: str = None):
        """Mark the workflow as complete."""
        self.done_condition = True
        if reason:
            self.add_reasoning_step(f"Termination reason: {reason}")
    
    def to_base_state(self) -> GraphState:
        """Convert to base GraphState for compatibility."""
        return GraphState(
            project_path=self.project_path,
            user_query=self.user_query,
            search_history=self.search_history,
            retrieved_abstracts=self.retrieved_abstracts,
            reasoning_steps=self.reasoning_steps,
            token_budget_max=self.token_budget_max,
            done_condition=self.done_condition,
            current_iteration=self.current_iteration,
            last_error=self.last_error
        )
