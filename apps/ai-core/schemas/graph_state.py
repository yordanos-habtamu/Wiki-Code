"""
Graph State Schema - Centralized state management for LangGraph orchestration.
Defines the shared agent memory structure with strict type contracts.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class GraphState(BaseModel):
    """
    Strict Pydantic model representing the shared agent memory for LangGraph workflows.
    
    This state object is passed through each node in the graph and accumulates
    data as the agent processes the user query.
    """
    
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
        description="Hard boundary ceiling integer specifying maximum permissible session context overhead"
    )
    
    done_condition: bool = Field(
        default=False,
        description="Boolean breakout signal flag - when True, graph execution terminates"
    )
    
    # Additional metadata fields for tracking
    current_iteration: int = Field(
        default=0,
        description="Current loop iteration count"
    )
    
    last_error: Optional[str] = Field(
        default=None,
        description="Last error encountered during graph execution"
    )
    
    class Config:
        """Pydantic configuration for immutability and validation."""
        validate_assignment = True
        extra = "forbid"  # Prevent adding unexpected fields
    
    def add_search_query(self, query: str):
        """Append a query to search history."""
        self.search_history.append(query)
    
    def add_abstract(self, abstract: Dict[str, Any]):
        """Add a retrieved abstract to the collection."""
        self.retrieved_abstracts.append(abstract)
    
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
