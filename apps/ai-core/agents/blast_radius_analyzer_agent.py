"""
BlastRadiusAnalyzerAgent - Recursive relationship tracking node for impact analysis.
Calculates structural modification impact profiles using repository metadata only.
"""

import os
import sys
from typing import Dict, Any, List, Set

# Add project root to path
current_file = os.path.abspath(__file__)
if 'apps' in current_file and 'ai-core' in current_file:
    apps_idx = current_file.find('apps')
    project_root = current_file[:apps_idx].rstrip('/')
else:
    project_root = os.path.dirname(os.path.dirname(current_file))
sys.path.insert(0, project_root)

from repositories.project_repository import ProjectRepository


class BlastRadiusAnalyzerAgent:
    """
    Recursive dependency traversal agent that calculates blast radius impact.
    
    This agent:
    1. Reads target_file from state context
    2. Queries repository for all files depending on target
    3. Recursively follows reference tree up to max_traversal_depth
    4. Documents affected nodes with name, language, and distance index
    
    IMPORTANT: Uses ONLY repository metadata - never reads raw source code.
    """
    
    def __init__(self, db_path: str = None):
        """
        Initialize the BlastRadiusAnalyzerAgent.
        
        Args:
            db_path: Path to SQLite hub.db
        """
        if db_path is None:
            db_path = os.path.join(project_root, "apps", "cli", "hub.db")
        
        self.repository = ProjectRepository(db_path=db_path)
        
        print(f"BlastRadiusAnalyzerAgent initialized with db: {db_path}", file=sys.stderr)
    
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main agent execution method. Performs recursive dependency traversal.
        
        Args:
            state: Current graph state dictionary with target_file and max_traversal_depth
        
        Returns:
            Updated state with impacted_nodes and risk metrics
        """
        print("\n=== BlastRadiusAnalyzerAgent Execution ===", file=sys.stderr)
        
        # Extract state fields
        target_file = state.get("target_file", "")
        max_depth = state.get("max_traversal_depth", 3)
        reasoning_steps = state.get("reasoning_steps", [])
        
        if not target_file:
            error_msg = "No target file specified for blast radius analysis"
            print(f"Error: {error_msg}", file=sys.stderr)
            reasoning_steps.append(error_msg)
            return {
                "impacted_nodes": [],
                "architectural_risk_score": 0.0,
                "blast_radius_classification": "isolated",
                "reasoning_steps": reasoning_steps
            }
        
        reasoning_steps.append(f"Starting blast radius analysis for: {target_file}")
        reasoning_steps.append(f"Max traversal depth: {max_depth}")
        
        print(f"Analyzing blast radius for: {target_file}", file=sys.stderr)
        print(f"Max traversal depth: {max_depth}", file=sys.stderr)
        
        # Perform recursive traversal
        impacted_nodes = []
        visited: Set[str] = set()
        
        self._traverse_dependencies(
            target_file=target_file,
            current_depth=1,
            max_depth=max_depth,
            impacted_nodes=impacted_nodes,
            visited=visited,
            reasoning_steps=reasoning_steps
        )
        
        print(f"Traversal complete: {len(impacted_nodes)} impacted node(s) found", file=sys.stderr)
        
        # Calculate risk score
        risk_score = self._calculate_risk_score(impacted_nodes, target_file)
        
        # Classify blast radius
        classification = self._classify_blast_radius(risk_score)
        
        reasoning_steps.append(f"Architectural risk score: {risk_score}/10.0")
        reasoning_steps.append(f"Blast radius classification: {classification}")
        
        print(f"Risk score: {risk_score}/10.0", file=sys.stderr)
        print(f"Classification: {classification}", file=sys.stderr)
        
        return {
            "impacted_nodes": impacted_nodes,
            "architectural_risk_score": risk_score,
            "blast_radius_classification": classification,
            "reasoning_steps": reasoning_steps
        }
    
    def _traverse_dependencies(
        self,
        target_file: str,
        current_depth: int,
        max_depth: int,
        impacted_nodes: List[Dict[str, Any]],
        visited: Set[str],
        reasoning_steps: List[str]
    ):
        """
        Recursively traverse dependency tree to find all impacted files.
        
        Args:
            target_file: Current file being analyzed
            current_depth: Current traversal depth (1-based)
            max_depth: Maximum depth to traverse
            impacted_nodes: List to accumulate impacted nodes
            visited: Set of already visited files (prevents cycles)
            reasoning_steps: Log of traversal steps
        """
        # Check depth limit
        if current_depth > max_depth:
            reasoning_steps.append(f"Depth limit reached at {max_depth}, stopping traversal")
            print(f"Depth limit reached: {current_depth}/{max_depth}", file=sys.stderr)
            return
        
        # Check if already visited (cycle detection)
        if target_file in visited:
            reasoning_steps.append(f"Cycle detected: {target_file} already visited")
            print(f"Cycle detected, skipping: {target_file}", file=sys.stderr)
            return
        
        # Mark as visited
        visited.add(target_file)
        
        # Find all files that depend on target_file
        dependents = self.repository.get_dependents_for_file(target_file)
        
        if not dependents:
            if current_depth == 1:
                reasoning_steps.append(f"{target_file} has no dependents (isolated)")
                print(f"No dependents found for: {target_file}", file=sys.stderr)
            return
        
        print(f"\nDepth {current_depth}: Found {len(dependents)} dependent(s) for {target_file}", file=sys.stderr)
        reasoning_steps.append(f"Depth {current_depth}: {len(dependents)} dependent(s) of {target_file}")
        
        # Process each dependent
        for dependent in dependents:
            source_file = dependent.get("source_file", "unknown")
            language = dependent.get("language", "unknown")
            
            # Document impacted node
            node_info = {
                "relative_path": source_file,
                "language": language,
                "depth": current_depth,
                "depends_on": target_file
            }
            
            impacted_nodes.append(node_info)
            
            print(f"  [{current_depth}] {source_file} ({language})", file=sys.stderr)
            reasoning_steps.append(f"  Depth {current_depth}: {source_file} ({language})")
            
            # Recursively traverse further
            if current_depth < max_depth:
                self._traverse_dependencies(
                    target_file=source_file,
                    current_depth=current_depth + 1,
                    max_depth=max_depth,
                    impacted_nodes=impacted_nodes,
                    visited=visited,
                    reasoning_steps=reasoning_steps
                )
    
    def _calculate_risk_score(
        self,
        impacted_nodes: List[Dict[str, Any]],
        target_file: str
    ) -> float:
        """
        Calculate architectural risk score based on impacted nodes.
        
        Scoring model:
        - Direct dependency (depth 1): +1.5 per node
        - Secondary step (depth 2): +0.5 per node
        - Tertiary step (depth 3+): +0.2 per node
        - Language boundary crossing: +2.0 per occurrence
        
        Args:
            impacted_nodes: List of impacted node dictionaries
            target_file: Original target file path
        
        Returns:
            Risk score capped at 10.0
        """
        if not impacted_nodes:
            return 0.0
        
        # Get target file language
        target_language = None
        all_files = self.repository.get_all_files()
        for file_info in all_files:
            if file_info.get("relative_path") == target_file:
                target_language = file_info.get("language")
                break
        
        score = 0.0
        
        for node in impacted_nodes:
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
                print(f"  Language boundary penalty: {target_language} → {node_language}", file=sys.stderr)
        
        # Cap at 10.0
        score = min(10.0, score)
        
        return round(score, 2)
    
    def _classify_blast_radius(self, risk_score: float) -> str:
        """
        Classify blast radius based on architectural risk score.
        
        Classification thresholds:
        - Score < 2.0: isolated
        - Score 2.0 - 4.0: low
        - Score 4.0 - 6.0: medium
        - Score 6.0 - 8.0: high
        - Score > 8.0: critical
        
        Args:
            risk_score: Calculated risk score (0.0 - 10.0)
        
        Returns:
            Classification label string
        """
        if risk_score < 2.0:
            return "isolated"
        elif risk_score < 4.0:
            return "low"
        elif risk_score < 6.0:
            return "medium"
        elif risk_score < 8.0:
            return "high"
        else:
            return "critical"
