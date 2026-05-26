"""
Impact Graph State Schema - Extended state for blast radius analysis and impact mapping.
Handles topological tree structures for dependency propagation tracking.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ImpactGraphState(BaseModel):
    """
    State model for blast radius analysis and architectural impact mapping.
    
    Tracks downstream dependency propagation through recursive traversal
    and calculates quantitative risk scores for structural changes.
    """
    
    # Base state fields
    project_path: str = Field(
        default="",
        description="The current local codebase reference string"
    )
    
    user_query: str = Field(
        default="",
        description="The original incoming exploration task request string"
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
    
    # Impact analysis-specific fields
    target_file: str = Field(
        default="",
        description="The relative path string of the module intended for refactoring"
    )
    
    impacted_nodes: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of dictionaries tracking direct and indirect downstream files"
    )
    
    max_traversal_depth: int = Field(
        default=3,
        description="How far down the reference rabbit hole to look (default: 3)"
    )
    
    architectural_risk_score: float = Field(
        default=0.0,
        description="Calculated float value scale (0.0 - 10.0) tracking danger profile"
    )
    
    blast_radius_classification: str = Field(
        default="isolated",
        description="Text ranking label: isolated, low, medium, high, critical"
    )
    
    traversal_history: List[str] = Field(
        default_factory=list,
        description="Log of traversal path for debugging and visualization"
    )
    
    class Config:
        """Pydantic configuration for immutability and validation."""
        validate_assignment = True
        extra = "forbid"
    
    def add_impacted_node(self, node: Dict[str, Any]):
        """Add an impacted node to the tracking list."""
        self.impacted_nodes.append(node)
    
    def add_reasoning_step(self, step: str):
        """Log a reasoning step."""
        self.reasoning_steps.append(step)
    
    def add_traversal_step(self, step: str):
        """Log a traversal step."""
        self.traversal_history.append(step)
    
    def increment_iteration(self):
        """Increment the iteration counter."""
        self.current_iteration += 1
    
    def mark_done(self, reason: str = None):
        """Mark the workflow as complete."""
        self.done_condition = True
        if reason:
            self.add_reasoning_step(f"Termination reason: {reason}")
    
    def calculate_risk_score(self) -> float:
        """
        Calculate architectural risk score based on impacted nodes.
        
        Scoring model:
        - Direct dependency (depth 1): +1.5 per node
        - Secondary step (depth 2): +0.5 per node
        - Tertiary step (depth 3): +0.2 per node
        - Language boundary crossing: +2.0 per occurrence
        
        Returns:
            Risk score capped at 10.0
        """
        if not self.impacted_nodes:
            return 0.0
        
        score = 0.0
        target_language = None
        
        # Get target file language from first impacted node's dependencies
        for node in self.impacted_nodes:
            if node.get("relative_path") == self.target_file:
                target_language = node.get("language")
                break
        
        for node in self.impacted_nodes:
            depth = node.get("depth", 1)
            
            # Base impact allocation by proximity
            if depth == 1:
                score += 1.5
            elif depth == 2:
                score += 0.5
            elif depth >= 3:
                score += 0.2
            
            # Language boundary penalty
            node_language = node.get("language")
            if target_language and node_language and target_language != node_language:
                score += 2.0
                self.add_reasoning_step(
                    f"Language boundary penalty: {target_language} → {node_language}"
                )
        
        # Cap at 10.0
        score = min(10.0, score)
        
        return round(score, 2)
    
    def classify_blast_radius(self) -> str:
        """
        Classify blast radius based on architectural risk score.
        
        Classification thresholds:
        - Score < 2.0: isolated
        - Score 2.0 - 4.0: low
        - Score 4.0 - 6.0: medium
        - Score 6.0 - 8.0: high
        - Score > 8.0: critical
        
        Returns:
            Classification label string
        """
        score = self.architectural_risk_score
        
        if score < 2.0:
            return "isolated"
        elif score < 4.0:
            return "low"
        elif score < 6.0:
            return "medium"
        elif score < 8.0:
            return "high"
        else:
            return "critical"
