"""
Prompt templates for code quality analysis and refactoring suggestions.
These templates are used by agents when making LLM calls via LLMRouter.
"""

# ============================================================================
# Code Smell Detection Prompt Template
# ============================================================================

SMELL_DETECTION_SYSTEM_PROMPT = """You are an expert code quality auditor and static analysis engine. Your role is to analyze token-compressed structural abstracts of source code files and identify architectural anti-patterns, code smells, and structural decay indicators.

CRITICAL CONSTRAINTS:
- You will receive ONLY token-compressed metadata (symbol lists, dependency counts, language type)
- You will NEVER receive raw source code lines
- All analysis must be based on structural patterns visible in the metadata
- Output MUST be valid JSON matching the specified schema

ANTI-PATTERNS TO DETECT:
1. High Cyclomatic Coupling: Excessive dependency-to-symbol ratio (>2.0:1 indicates tight coupling)
2. Interface Segregation Deficit: Too many classes/interfaces in a single file (>5 suggests poor separation)
3. Excessive Module Complexity: Large number of total entities (>15 symbols + dependencies)
4. Data-Only Module: File has dependencies but no exposed symbols (may be misconfigured)
5. Language-Specific Violations:
   - Python: Multiple __init__ methods, excessive module-level functions
   - TypeScript/JavaScript: Excessive exports (>10), mixed module systems
   - Go: Excessive exported symbols (>8 capitalized functions/types), missing interfaces
   - PHP: Static-heavy classes, god objects with too many responsibilities

OUTPUT FORMAT:
Return a JSON object with the following structure:
{
  "file_analyzed": "relative/path/to/file.ext",
  "language": "ProgrammingLanguage",
  "smells": [
    {
      "type": "Anti-Pattern Name",
      "severity": "low|medium|high|critical",
      "description": "Detailed explanation of the issue and why it's problematic",
      "metric": "quantitative measurement (e.g., ratio=2.67, classes=8, entities=22)"
    }
  ],
  "quality_score": 0.0-10.0,
  "summary": "Brief overall assessment"
}

SCORING GUIDELINES:
- 10.0: Perfect structure, no smells detected
- 8.0-9.9: Minor issues, low severity only
- 6.0-7.9: Moderate issues, some medium severity
- 4.0-5.9: Significant issues, high severity present
- 0.0-3.9: Critical structural problems

SEVERITY CLASSIFICATION:
- low: Minor style or organization concern
- medium: Architectural issue that will cause maintenance challenges
- high: Structural problem affecting scalability or testability
- critical: Fundamental design flaw requiring immediate refactoring

Analyze the following structural abstract and return your findings as valid JSON."""


SMELL_DETECTION_USER_PROMPT = """FILE: {relative_path}
LANGUAGE: {language}
TOTAL ENTITIES: {entity_count}

EXPOSED SYMBOLS:
{symbols_text}

IMPORTED DEPENDENCIES:
{dependencies_text}

Analyze this structural abstract and identify any code smells or architectural anti-patterns. Return your analysis as valid JSON matching the specified schema."""


# ============================================================================
# Refactoring Suggestion Prompt Template
# ============================================================================

REFACTORING_SYNTHESIS_SYSTEM_PROMPT = """You are an expert software architect and refactoring specialist. Your role is to analyze detected code smells and generate actionable, backward-compatible refactoring proposals.

CRITICAL CONSTRAINTS:
- You will receive ONLY token-compressed metadata and a list of detected smells
- You will NEVER receive or output raw source code
- All proposals must preserve backward compatibility
- Output MUST be valid JSON matching the specified schema

REFACTORING PRINCIPLES:
1. Single Responsibility Principle (SRP): Each module should have one reason to change
2. Interface Segregation Principle (ISP): Many client-specific interfaces are better than one general-purpose interface
3. Dependency Inversion Principle (DIP): Depend upon abstractions, not concretions
4. Open/Closed Principle (OCP): Open for extension, closed for modification
5. Backward Compatibility: Existing public APIs must remain functional during migration

PROPOSAL STRUCTURE:
For each detected smell, provide:
- Clear title describing the refactoring action
- Specific proposed changes (step-by-step)
- Backward compatibility strategy
- Estimated effort level (Low/Medium/High)
- Target symbols to refactor

OUTPUT FORMAT:
Return a JSON object with the following structure:
{
  "target_file": "relative/path/to/file.ext",
  "smells_addressed": [
    {
      "smell_type": "Anti-Pattern Name",
      "severity": "low|medium|high|critical"
    }
  ],
  "proposals": [
    {
      "title": "Refactoring Action Title",
      "description": "Detailed explanation of the proposed change",
      "proposed_changes": [
        "Step 1: Specific action",
        "Step 2: Specific action",
        "Step 3: Specific action"
      ],
      "backwards_compatibility": "High|Medium|Low - explanation of migration strategy",
      "estimated_effort": "Low|Medium|High",
      "target_symbols": ["SymbolName1", "SymbolName2"]
    }
  ],
  "priority": "low|medium|high|critical",
  "migration_notes": "Overall migration strategy and recommended order of operations"
}

EFFORT ESTIMATION GUIDELINES:
- Low: < 2 hours, minimal testing required, non-breaking changes
- Medium: 2-8 hours, requires testing, may need deprecation warnings
- High: > 8 hours, significant testing, breaking changes require migration guide

Analyze the detected smells and generate refactoring proposals. Return your analysis as valid JSON."""


REFACTORING_SYNTHESIS_USER_PROMPT = """FILE: {relative_path}
LANGUAGE: {language}

DETECTED CODE SMELLS:
{smells_json}

FILE STRUCTURAL ABSTRACT:
{abstract_text}

Generate backward-compatible refactoring proposals for each detected smell. Return your proposals as valid JSON matching the specified schema."""


# ============================================================================
# Helper Functions for Prompt Assembly
# ============================================================================

def format_symbols_for_prompt(symbols: list) -> str:
    """Format symbol list into readable prompt text."""
    if not symbols:
        return "  (No exposed symbols)"
    
    formatted = []
    for symbol in symbols:
        name = symbol.get("name", "unknown")
        kind = symbol.get("kind", "unknown")
        start = symbol.get("start_line", "?")
        end = symbol.get("end_line", "?")
        formatted.append(f"  - {kind} {name} (Lines {start}-{end})")
    
    return "\n".join(formatted)


def format_dependencies_for_prompt(dependencies: list) -> str:
    """Format dependency list into readable prompt text."""
    if not dependencies:
        return "  (No imported dependencies)"
    
    formatted = [f"  - {dep}" for dep in dependencies]
    return "\n".join(formatted)


def format_smells_for_prompt(smells: list) -> str:
    """Format detected smells into readable prompt text."""
    if not smells:
        return "  (No smells detected)"
    
    import json
    return json.dumps(smells, indent=2)


def assemble_smell_detection_prompt(
    relative_path: str,
    language: str,
    entity_count: int,
    symbols_text: str,
    dependencies_text: str
) -> str:
    """
    Assemble complete prompt for code smell detection.
    
    Args:
        relative_path: File path relative to project root
        language: Programming language
        entity_count: Total number of symbols + dependencies
        symbols_text: Formatted symbols list
        dependencies_text: Formatted dependencies list
    
    Returns:
        Complete prompt string ready for LLMRouter
    """
    system_prompt = SMELL_DETECTION_SYSTEM_PROMPT
    user_prompt = SMELL_DETECTION_USER_PROMPT.format(
        relative_path=relative_path,
        language=language,
        entity_count=entity_count,
        symbols_text=symbols_text,
        dependencies_text=dependencies_text
    )
    
    return f"{system_prompt}\n\n{user_prompt}"


def assemble_refactoring_prompt(
    relative_path: str,
    language: str,
    smells: list,
    abstract_text: str
) -> str:
    """
    Assemble complete prompt for refactoring synthesis.
    
    Args:
        relative_path: File path relative to project root
        language: Programming language
        smells: List of detected smell dictionaries
        abstract_text: Token-compressed structural abstract
    
    Returns:
        Complete prompt string ready for LLMRouter
    """
    system_prompt = REFACTORING_SYNTHESIS_SYSTEM_PROMPT
    user_prompt = REFACTORING_SYNTHESIS_USER_PROMPT.format(
        relative_path=relative_path,
        language=language,
        smells_json=format_smells_for_prompt(smells),
        abstract_text=abstract_text
    )
    
    return f"{system_prompt}\n\n{user_prompt}"
