"""
CodeSmellDetectorAgent - Structural validation step for code quality auditing.
Evaluates language-specific structural flaws using token-compressed abstracts only.

Supports dual-mode operation:
- Heuristic mode (default): Rule-based detection using structural metrics
- LLM mode (optional): AI-powered analysis via LLMRouter when providers are configured
"""

import os
import sys
import json
import importlib.util
from typing import Dict, Any, List

# Add project root to path
current_file = os.path.abspath(__file__)
if 'apps' in current_file and 'ai-core' in current_file:
    apps_idx = current_file.find('apps')
    project_root = current_file[:apps_idx].rstrip('/')
else:
    project_root = os.path.dirname(os.path.dirname(current_file))
sys.path.insert(0, project_root)


class CodeSmellDetectorAgent:
    """
    Structural validation agent that analyzes code abstracts for anti-patterns.
    
    This agent supports dual-mode operation:
    1. Heuristic mode (default): Rule-based detection using structural metrics
    2. LLM mode (optional): AI-powered analysis via LLMRouter when providers configured
    
    This agent:
    1. Inspects target file's exposed signatures and dependency metrics
    2. Flags architectural decay indicators
    3. Compiles findings into structured smell dictionaries
    4. Appends to state's detected_smells array
    
    IMPORTANT: Operates ONLY on token-compressed abstracts - never raw source code.
    """
    
    def __init__(self, use_llm: bool = False, model_id: str = None):
        """
        Initialize the CodeSmellDetectorAgent.
        
        Args:
            use_llm: Enable LLM-powered analysis (default: False, uses heuristics)
            model_id: Model identifier for LLMRouter (e.g., "gemini/gemini-2.0-flash")
        """
        self.use_llm = use_llm
        self.model_id = model_id or "gemini/gemini-2.0-flash"
        self.llm_router = None
        
        # Initialize LLMRouter if requested
        if self.use_llm:
            try:
                llm_router_path = os.path.join(project_root, "apps", "ai-core", "llm", "llm_router.py")
                spec = importlib.util.spec_from_file_location("llm_router", llm_router_path)
                llm_router_module = importlib.util.module_from_spec(spec)
                sys.modules["llm_router"] = llm_router_module
                spec.loader.exec_module(llm_router_module)
                
                self.llm_router = llm_router_module.LLMRouter()
                if self.llm_router.initialize():
                    print(f"CodeSmellDetectorAgent: LLM mode enabled with {self.model_id}", file=sys.stderr)
                else:
                    print("CodeSmellDetectorAgent: LLM initialization failed, falling back to heuristics", file=sys.stderr)
                    self.use_llm = False
                    self.llm_router = None
            except Exception as e:
                print(f"CodeSmellDetectorAgent: LLM setup failed: {e}, using heuristics", file=sys.stderr)
                self.use_llm = False
                self.llm_router = None
        
        print(f"CodeSmellDetectorAgent initialized (mode={'LLM' if self.use_llm else 'heuristic'})", file=sys.stderr)
    
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main agent execution method. Analyzes target file abstract for code smells.
        
        Args:
            state: Current graph state dictionary with target_file and retrieved_abstracts
        
        Returns:
            Updated state with detected_smells appended
        """
        print("\n=== CodeSmellDetectorAgent Execution ===", file=sys.stderr)
        
        # Extract state fields
        target_file = state.get("target_file", "")
        retrieved_abstracts = state.get("retrieved_abstracts", [])
        detected_smells = state.get("detected_smells", [])
        reasoning_steps = state.get("reasoning_steps", [])
        
        reasoning_steps.append(f"Analyzing target file: {target_file}")
        
        # Find the target file's abstract
        target_abstract = None
        for abstract in retrieved_abstracts:
            if abstract.get("relative_path") == target_file:
                target_abstract = abstract
                break
        
        if not target_abstract:
            error_msg = f"Target file '{target_file}' not found in retrieved abstracts"
            print(f"Error: {error_msg}", file=sys.stderr)
            reasoning_steps.append(error_msg)
            return {
                "detected_smells": detected_smells,
                "reasoning_steps": reasoning_steps,
                "last_error": error_msg
            }
        
        print(f"Analyzing abstract for: {target_file}", file=sys.stderr)
        print(f"Language: {target_abstract.get('language', 'unknown')}", file=sys.stderr)
        print(f"Mode: {'LLM' if self.use_llm else 'Heuristic'}", file=sys.stderr)
        
        # Perform structural analysis based on mode
        if self.use_llm and self.llm_router:
            smells = self._analyze_with_llm(target_abstract)
        else:
            smells = self._analyze_abstract(target_abstract)
        
        # Append detected smells to state
        detected_smells.extend(smells)
        
        reasoning_steps.append(f"Detected {len(smells)} code smell(s)")
        
        # Calculate quality score
        quality_score = self._calculate_quality_score(smells)
        
        # Determine refactoring priority
        priority = self._determine_priority(smells)
        
        print(f"Detected {len(smells)} smell(s)", file=sys.stderr)
        print(f"Quality score: {quality_score:.1f}/10.0", file=sys.stderr)
        print(f"Priority: {priority}", file=sys.stderr)
        
        for smell in smells:
            print(f"  - [{smell['severity']}] {smell['type']}: {smell['description']}", file=sys.stderr)
        
        return {
            "detected_smells": detected_smells,
            "quality_score": quality_score,
            "refactoring_priority": priority,
            "reasoning_steps": reasoning_steps
        }
    
    def _analyze_abstract(self, abstract: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Analyze a token-compressed abstract for structural code smells.
        
        Args:
            abstract: Dictionary containing file metadata and structural abstract
        
        Returns:
            List of detected smell dictionaries
        """
        smells = []
        
        language = abstract.get("language", "unknown")
        entity_count = abstract.get("entity_count", 0)
        abstract_text = abstract.get("abstract", "")
        
        # Parse abstract to extract metrics
        symbol_count = self._count_symbols(abstract_text)
        dependency_count = self._count_dependencies(abstract_text)
        
        # Smell 1: High dependency-to-symbol ratio (God Object / Tight Coupling)
        if symbol_count > 0 and dependency_count > 0:
            ratio = dependency_count / symbol_count
            if ratio > 2.0:
                smells.append({
                    "type": "High Cyclomatic Coupling",
                    "severity": "high" if ratio > 3.0 else "medium",
                    "description": f"Dependency-to-symbol ratio is {ratio:.1f}:1 (threshold: 2.0:1). Module may have excessive external dependencies.",
                    "metric": f"ratio={ratio:.2f}",
                    "file": abstract.get("relative_path", "unknown")
                })
        
        # Smell 2: Excessive exposed interfaces (Interface Segregation Deficit)
        class_count = self._count_classes(abstract_text)
        if class_count > 5:
            smells.append({
                "type": "Interface Segregation Deficit",
                "severity": "medium",
                "description": f"File contains {class_count} classes/interfaces. Consider splitting into focused modules.",
                "metric": f"classes={class_count}",
                "file": abstract.get("relative_path", "unknown")
            })
        
        # Smell 3: Large file complexity (based on entity count)
        if entity_count > 15:
            smells.append({
                "type": "Excessive Module Complexity",
                "severity": "high" if entity_count > 25 else "medium",
                "description": f"File has {entity_count} total entities (symbols + dependencies). Consider decomposition.",
                "metric": f"entities={entity_count}",
                "file": abstract.get("relative_path", "unknown")
            })
        
        # Smell 4: Language-specific violations
        lang_smells = self._check_language_violations(language, abstract_text)
        smells.extend(lang_smells)
        
        # Smell 5: No symbols detected (empty or data-only file)
        if symbol_count == 0 and entity_count > 0:
            smells.append({
                "type": "Data-Only Module",
                "severity": "low",
                "description": "File contains dependencies but no exposed symbols. May be a configuration or data file.",
                "metric": "symbols=0",
                "file": abstract.get("relative_path", "unknown")
            })
        
        return smells
    
    def _count_symbols(self, abstract_text: str) -> int:
        """Count exposed symbols from abstract text."""
        count = 0
        lines = abstract_text.split('\n')
        for line in lines:
            if line.strip().startswith('- class ') or \
               line.strip().startswith('- function ') or \
               line.strip().startswith('- struct ') or \
               line.strip().startswith('- interface '):
                count += 1
        return count
    
    def _count_dependencies(self, abstract_text: str) -> int:
        """Count imported dependencies from abstract text."""
        count = 0
        in_dependencies = False
        lines = abstract_text.split('\n')
        for line in lines:
            if 'Imported Dependencies:' in line:
                in_dependencies = True
                continue
            if in_dependencies and line.strip().startswith('- '):
                if '(None)' not in line:
                    count += 1
        return count
    
    def _count_classes(self, abstract_text: str) -> int:
        """Count classes/interfaces from abstract text."""
        count = 0
        lines = abstract_text.split('\n')
        for line in lines:
            if line.strip().startswith('- class ') or \
               line.strip().startswith('- struct ') or \
               line.strip().startswith('- interface '):
                count += 1
        return count
    
    def _check_language_violations(self, language: str, abstract_text: str) -> List[Dict[str, Any]]:
        """Check for language-specific structural violations."""
        smells = []
        
        if language == "Python":
            # Check for potential __init__ overload
            init_count = abstract_text.count('__init__')
            if init_count > 1:
                smells.append({
                    "type": "Python Anti-Pattern",
                    "severity": "medium",
                    "description": f"Multiple __init__ methods detected ({init_count}). Possible class duplication.",
                    "metric": f"init_count={init_count}",
                    "file": "unknown"
                })
        
        elif language == "TypeScript/JavaScript":
            # Check for excessive exports
            export_count = abstract_text.count('export ')
            if export_count > 10:
                smells.append({
                    "type": "JavaScript Anti-Pattern",
                    "severity": "medium",
                    "description": f"Excessive exports ({export_count}). Module may lack focus.",
                    "metric": f"exports={export_count}",
                    "file": "unknown"
                })
        
        elif language == "Go":
            # Check for exported symbols (capitalized)
            exported_count = 0
            lines = abstract_text.split('\n')
            for line in lines:
                if 'Signature:' in line:
                    sig = line.split('Signature:')[1].strip()
                    if sig and sig[0].isupper():
                        exported_count += 1
            
            if exported_count > 8:
                smells.append({
                    "type": "Go Anti-Pattern",
                    "severity": "medium",
                    "description": f"Excessive exported symbols ({exported_count}). Consider reducing public API surface.",
                    "metric": f"exported={exported_count}",
                    "file": "unknown"
                })
        
        return smells
    
    def _calculate_quality_score(self, smells: List[Dict[str, Any]]) -> float:
        """
        Calculate overall code quality score based on detected smells.
        
        Args:
            smells: List of detected smell dictionaries
        
        Returns:
            Quality score from 0.0 (poor) to 10.0 (excellent)
        """
        if not smells:
            return 10.0
        
        # Deduct points based on severity
        deductions = 0.0
        for smell in smells:
            severity = smell.get("severity", "low")
            if severity == "critical":
                deductions += 3.0
            elif severity == "high":
                deductions += 2.0
            elif severity == "medium":
                deductions += 1.0
            else:  # low
                deductions += 0.5
        
        score = max(0.0, 10.0 - deductions)
        return round(score, 1)
    
    def _determine_priority(self, smells: List[Dict[str, Any]]) -> str:
        """
        Determine refactoring priority based on detected smells.
        
        Args:
            smells: List of detected smell dictionaries
        
        Returns:
            Priority level: low, medium, high, critical
        """
        if not smells:
            return "low"
        
        severities = [smell.get("severity", "low") for smell in smells]
        
        if "critical" in severities:
            return "critical"
        elif "high" in severities:
            return "high"
        elif "medium" in severities:
            return "medium"
        else:
            return "low"
    
    def _analyze_with_llm(self, abstract: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Analyze abstract using LLM-powered detection with graceful fallback.
        
        Args:
            abstract: Dictionary containing file metadata and structural abstract
        
        Returns:
            List of detected smell dictionaries
        """
        try:
            # Import prompt templates
            prompts_path = os.path.join(project_root, "apps", "ai-core", "llm", "prompts.py")
            spec = importlib.util.spec_from_file_location("prompts", prompts_path)
            prompts_module = importlib.util.module_from_spec(spec)
            sys.modules["prompts"] = prompts_module
            spec.loader.exec_module(prompts_module)
            
            # Extract metadata from abstract
            relative_path = abstract.get("relative_path", "unknown")
            language = abstract.get("language", "unknown")
            entity_count = abstract.get("entity_count", 0)
            abstract_text = abstract.get("abstract", "")
            
            # Parse symbols and dependencies from abstract
            symbols_text = self._extract_symbols_text(abstract_text)
            dependencies_text = self._extract_dependencies_text(abstract_text)
            
            # Assemble prompt
            prompt = prompts_module.assemble_smell_detection_prompt(
                relative_path=relative_path,
                language=language,
                entity_count=entity_count,
                symbols_text=symbols_text,
                dependencies_text=dependencies_text
            )
            
            print(f"Invoking LLM for smell detection: {self.model_id}", file=sys.stderr)
            
            # Call LLMRouter
            response = self.llm_router.complete(
                prompt=prompt,
                model_id=self.model_id,
                options={"temperature": 0.1, "max_tokens": 2000}
            )
            
            # Parse JSON response
            content = response.content.strip()
            
            # Extract JSON from response (handle markdown code blocks)
            if content.startswith("```"):
                content = content.split("\n", 1)[1]  # Remove opening ```
                if content.endswith("```"):
                    content = content.rsplit("\n", 1)[0]  # Remove closing ```
            
            result = json.loads(content)
            
            # Extract smells from response
            smells = result.get("smells", [])
            
            # Add file path to each smell
            for smell in smells:
                smell["file"] = relative_path
            
            print(f"LLM detected {len(smells)} smell(s)", file=sys.stderr)
            
            # Log token usage if middleware is available
            self._log_token_usage(response, "quality_audit")
            
            return smells
            
        except Exception as e:
            # GRACEFUL FALLBACK: Log error and use heuristic detection
            print(
                f"CodeSmellDetectorAgent: LLM analysis failed: {e}",
                file=sys.stderr
            )
            print("Falling back to heuristic detection", file=sys.stderr)
            
            # Disable LLM mode for future calls
            self.use_llm = False
            
            # Fall back to heuristic analysis
            return self._analyze_abstract(abstract)
    
    def _extract_symbols_text(self, abstract_text: str) -> str:
        """Extract symbols section from abstract text."""
        lines = abstract_text.split('\n')
        symbols_lines = []
        in_symbols = False
        
        for line in lines:
            if 'Exposed Symbols:' in line:
                in_symbols = True
                continue
            if 'Imported Dependencies:' in line:
                in_symbols = False
                break
            if in_symbols and line.strip().startswith('- '):
                symbols_lines.append(line.strip())
        
        return '\n'.join(symbols_lines) if symbols_lines else "  (No exposed symbols)"
    
    def _extract_dependencies_text(self, abstract_text: str) -> str:
        """Extract dependencies section from abstract text."""
        lines = abstract_text.split('\n')
        deps_lines = []
        in_deps = False
        
        for line in lines:
            if 'Imported Dependencies:' in line:
                in_deps = True
                continue
            if in_deps and line.strip().startswith('- '):
                deps_lines.append(line.strip())
        
        return '\n'.join(deps_lines) if deps_lines else "  (No imported dependencies)"
    
    def _log_token_usage(self, response, operation_type: str):
        """Log token usage to repository if available."""
        try:
            token_repo_path = os.path.join(project_root, "apps", "ai-core", "repositories", "token_usage_repository.py")
            spec = importlib.util.spec_from_file_location("token_usage_repository", token_repo_path)
            token_repo_module = importlib.util.module_from_spec(spec)
            sys.modules["token_usage_repository"] = token_repo_module
            spec.loader.exec_module(token_repo_module)
            
            TokenUsageRecord = token_repo_module.TokenUsageRecord
            TokenUsageRepository = token_repo_module.TokenUsageRepository
            
            db_path = os.path.join(project_root, "apps", "cli", "hub.db")
            repository = TokenUsageRepository(db_path=db_path)
            
            usage_record = TokenUsageRecord(
                operation_type=operation_type,
                provider=response.provider,
                model_used=response.model_used,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                total_tokens=response.total_tokens
            )
            
            repository.log_usage(usage_record)
            
            print(
                f"Token usage logged: {response.total_tokens} tokens for {operation_type}",
                file=sys.stderr
            )
        except Exception as e:
            print(f"Warning: Failed to log token usage: {e}", file=sys.stderr)
