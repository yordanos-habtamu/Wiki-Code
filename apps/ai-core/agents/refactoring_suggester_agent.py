"""
RefactoringSuggesterAgent - Synthesis node for architectural improvement suggestions.
Reads detected smells and fabricates improved interface signatures using abstracts only.
"""

import os
import sys
from typing import Dict, Any, List

# Add project root to path
current_file = os.path.abspath(__file__)
if 'apps' in current_file and 'ai-core' in current_file:
    apps_idx = current_file.find('apps')
    project_root = current_file[:apps_idx].rstrip('/')
else:
    project_root = os.path.dirname(os.path.dirname(current_file))
sys.path.insert(0, project_root)


class RefactoringSuggesterAgent:
    """
    Synthesis agent that generates refactoring proposals based on detected code smells.
    
    This agent:
    1. Reviews structural abstract alongside active anti-pattern log
    2. Synthesizes decoupled architectural fixes
    3. Emits normalized refactoring structural manifesto
    4. Preserves backwards compatibility in all suggestions
    
    IMPORTANT: Operates ONLY on token-compressed abstracts - never raw source code.
    """
    
    def __init__(self):
        """Initialize the RefactoringSuggesterAgent."""
        print("RefactoringSuggesterAgent initialized", file=sys.stderr)
    
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main agent execution method. Generates refactoring proposals for detected smells.
        
        Args:
            state: Current graph state with detected_smells and retrieved_abstracts
        
        Returns:
            Updated state with proposed_architecture appended
        """
        print("\n=== RefactoringSuggesterAgent Execution ===", file=sys.stderr)
        
        # Extract state fields
        target_file = state.get("target_file", "")
        detected_smells = state.get("detected_smells", [])
        retrieved_abstracts = state.get("retrieved_abstracts", [])
        proposed_architecture = state.get("proposed_architecture", [])
        reasoning_steps = state.get("reasoning_steps", [])
        
        reasoning_steps.append(f"Generating refactoring proposals for: {target_file}")
        
        if not detected_smells:
            reasoning_steps.append("No code smells detected - no refactoring needed")
            print("No code smells to address", file=sys.stderr)
            return {
                "proposed_architecture": proposed_architecture,
                "reasoning_steps": reasoning_steps
            }
        
        # Find the target file's abstract
        target_abstract = None
        for abstract in retrieved_abstracts:
            if abstract.get("relative_path") == target_file:
                target_abstract = abstract
                break
        
        if not target_abstract:
            error_msg = f"Target file '{target_file}' not found for refactoring"
            print(f"Error: {error_msg}", file=sys.stderr)
            reasoning_steps.append(error_msg)
            return {
                "proposed_architecture": proposed_architecture,
                "reasoning_steps": reasoning_steps,
                "last_error": error_msg
            }
        
        print(f"Generating proposals for {len(detected_smells)} smell(s)", file=sys.stderr)
        
        # Generate refactoring proposals for each smell
        proposals = []
        for smell in detected_smells:
            proposal = self._generate_proposal(smell, target_abstract)
            if proposal:
                proposals.append(proposal)
        
        # Append proposals to state
        proposed_architecture.extend(proposals)
        
        reasoning_steps.append(f"Generated {len(proposals)} refactoring proposal(s)")
        
        print(f"Generated {len(proposals)} proposal(s)", file=sys.stderr)
        for proposal in proposals:
            print(f"  - [{proposal['priority']}] {proposal['title']}", file=sys.stderr)
        
        return {
            "proposed_architecture": proposed_architecture,
            "reasoning_steps": reasoning_steps
        }
    
    def _generate_proposal(self, smell: Dict[str, Any], abstract: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a refactoring proposal for a specific code smell.
        
        Args:
            smell: Detected smell dictionary
            abstract: Target file's structural abstract
        
        Returns:
            Refactoring proposal dictionary
        """
        smell_type = smell.get("type", "")
        
        if "High Cyclomatic Coupling" in smell_type:
            return self._propose_dependency_reduction(smell, abstract)
        elif "Interface Segregation Deficit" in smell_type:
            return self._propose_interface_splitting(smell, abstract)
        elif "Excessive Module Complexity" in smell_type:
            return self._propose_module_decomposition(smell, abstract)
        elif "Data-Only Module" in smell_type:
            return self._propose_data_module_organization(smell, abstract)
        else:
            return self._propose_generic_improvement(smell, abstract)
    
    def _propose_dependency_reduction(self, smell: Dict[str, Any], abstract: Dict[str, Any]) -> Dict[str, Any]:
        """Propose dependency reduction for high coupling."""
        return {
            "title": "Reduce External Dependencies",
            "smell_addressed": smell["type"],
            "priority": smell["severity"],
            "description": (
                "Introduce dependency injection or facade pattern to reduce direct imports. "
                "Group related dependencies into cohesive modules."
            ),
            "proposed_changes": [
                "Create a facade module that aggregates related dependencies",
                "Use dependency injection to decouple direct imports",
                "Implement interface segregation for unused dependencies"
            ],
            "backwards_compatibility": "High - existing imports can be gradually migrated",
            "estimated_effort": "Medium",
            "target_symbols": self._extract_symbols(abstract)
        }
    
    def _propose_interface_splitting(self, smell: Dict[str, Any], abstract: Dict[str, Any]) -> Dict[str, Any]:
        """Propose interface splitting for excessive classes."""
        return {
            "title": "Split Large Interface",
            "smell_addressed": smell["type"],
            "priority": smell["severity"],
            "description": (
                "Decompose large interface into focused, role-specific interfaces. "
                "Apply Interface Segregation Principle (ISP)."
            ),
            "proposed_changes": [
                "Identify cohesive groups of methods/properties",
                "Create separate interfaces for each responsibility",
                "Implement composition over inheritance where applicable"
            ],
            "backwards_compatibility": "Medium - requires interface migration strategy",
            "estimated_effort": "High",
            "target_symbols": self._extract_symbols(abstract)
        }
    
    def _propose_module_decomposition(self, smell: Dict[str, Any], abstract: Dict[str, Any]) -> Dict[str, Any]:
        """Propose module decomposition for excessive complexity."""
        return {
            "title": "Decompose Complex Module",
            "smell_addressed": smell["type"],
            "priority": smell["severity"],
            "description": (
                "Break down monolithic module into focused sub-modules. "
                "Apply Single Responsibility Principle (SRP)."
            ),
            "proposed_changes": [
                "Group related symbols into cohesive sub-modules",
                "Create clear public API boundaries",
                "Move internal helpers to private modules"
            ],
            "backwards_compatibility": "Medium - requires re-export strategy for public API",
            "estimated_effort": "High",
            "target_symbols": self._extract_symbols(abstract)
        }
    
    def _propose_data_module_organization(self, smell: Dict[str, Any], abstract: Dict[str, Any]) -> Dict[str, Any]:
        """Propose organization for data-only modules."""
        return {
            "title": "Organize Data Module",
            "smell_addressed": smell["type"],
            "priority": smell["severity"],
            "description": (
                "If this is a configuration/data file, consider using structured formats (JSON/YAML). "
                "If it should contain logic, add appropriate symbols."
            ),
            "proposed_changes": [
                "Convert to structured data format if pure configuration",
                "Add factory/builder patterns if object creation is needed",
                "Document the module's intended purpose clearly"
            ],
            "backwards_compatibility": "High - non-breaking change",
            "estimated_effort": "Low",
            "target_symbols": []
        }
    
    def _propose_generic_improvement(self, smell: Dict[str, Any], abstract: Dict[str, Any]) -> Dict[str, Any]:
        """Propose generic improvement for unclassified smells."""
        return {
            "title": f"Address: {smell['type']}",
            "smell_addressed": smell["type"],
            "priority": smell["severity"],
            "description": smell.get("description", "Apply best practices for code quality improvement."),
            "proposed_changes": [
                "Review code structure and apply language-specific best practices",
                "Consider design patterns appropriate for the use case",
                "Add documentation to clarify intent"
            ],
            "backwards_compatibility": "Medium",
            "estimated_effort": "Medium",
            "target_symbols": self._extract_symbols(abstract)
        }
    
    def _extract_symbols(self, abstract: Dict[str, Any]) -> List[str]:
        """Extract symbol names from abstract for targeting."""
        symbols = []
        abstract_text = abstract.get("abstract", "")
        lines = abstract_text.split('\n')
        
        for line in lines:
            if line.strip().startswith('- class ') or \
               line.strip().startswith('- function ') or \
               line.strip().startswith('- struct ') or \
               line.strip().startswith('- interface '):
                # Extract symbol name
                parts = line.strip().split()
                if len(parts) >= 3:
                    symbols.append(parts[2])
        
        return symbols
