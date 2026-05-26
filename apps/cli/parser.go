package main

import (
	"crypto/sha256"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

// SymbolResult represents metadata of a single symbol
type SymbolResult struct {
	Name      string
	Kind      string
	StartLine int
	EndLine   int
	Signature string
}

// FileScanResult represents metadata of a single scanned file
type FileScanResult struct {
	RelativePath string
	Language     string
	FileHash     string
	FileSize     int64
	Symbols      []SymbolResult
	Dependencies []string
}

// Precompile regex patterns for high-speed reuse
var (
	// Go Patterns
	goFuncRegex   = regexp.MustCompile(`^func\s+(?:\([^)]+\)\s+)?([A-Za-z0-9_]+)\s*\(`)
	goTypeRegex   = regexp.MustCompile(`^type\s+([A-Za-z0-9_]+)\s+(struct|interface)`)
	goSingleImp   = regexp.MustCompile(`import\s+"([^"]+)"`)
	goBlockImp    = regexp.MustCompile(`import\s*\(([\s\S]*?)\)`)
	strQuoteRegex = regexp.MustCompile(`"([^"]+)"`)

	// Python Patterns
	pyDefRegex   = regexp.MustCompile(`^\s*def\s+([A-Za-z0-9_]+)\s*\(`)
	pyClassRegex = regexp.MustCompile(`^\s*class\s+([A-Za-z0-9_]+)`)
	pyFromImp    = regexp.MustCompile(`(?m)^from\s+([A-Za-z0-9_.]+)\s+import`)
	pyImportImp  = regexp.MustCompile(`(?m)^import\s+([A-Za-z0-9_., ]+)`)

	// TS/JS Patterns
	jsClassRegex  = regexp.MustCompile(`^(?:export\s+)?(?:default\s+)?class\s+([A-Za-z0-9_]+)`)
	jsFuncRegex   = regexp.MustCompile(`^(?:export\s+)?(?:default\s+)?function\s+([A-Za-z0-9_]+)\s*\(`)
	jsArrowRegex  = regexp.MustCompile(`^(?:export\s+)?(?:const|let|var)\s+([A-Za-z0-9_]+)\s*=\s*(?:\([^)]*\)|[A-Za-z0-9_]+)?\s*=>`)
	jsInterface   = regexp.MustCompile(`^(?:export\s+)?interface\s+([A-Za-z0-9_]+)`)
	jsImportFrom  = regexp.MustCompile(`import\s+[\s\S]*?from\s+['"]([^'"]+)['"]`)
	jsImportBasic = regexp.MustCompile(`import\s+['"]([^'"]+)['"]`)
	jsImportDyn   = regexp.MustCompile(`import\s*\(\s*['"]([^'"]+)['"]\s*\)`)
	jsRequire     = regexp.MustCompile(`require\s*\(\s*['"]([^'"]+)['"]\s*\)`)

	// PHP Patterns
	phpClassRegex = regexp.MustCompile(`^(?:abstract\s+|final\s+)?(?:class|interface|trait)\s+([A-Za-z0-9_]+)`)
	phpFuncRegex  = regexp.MustCompile(`^(?:public\s+|private\s+|protected\s+|static\s+)*function\s+([A-Za-z0-9_]+)\s*\(`)
	phpUseRegex   = regexp.MustCompile(`use\s+([A-Za-z0-9_\\]+)\s*;`)
	phpReqInc     = regexp.MustCompile(`(?:require|include)(?:_once)?\s*\(?\s*['"]([^'"]+)['"]\s*\)?`)
)

// ParseFile runs language-specific scanning and regex parsing on the target file
func ParseFile(absPath, relPath string) (*FileScanResult, error) {
	data, err := os.ReadFile(absPath)
	if err != nil {
		return nil, err
	}

	// Compute SHA-256 hash for freshness tracking
	hashBytes := sha256.Sum256(data)
	fileHash := fmt.Sprintf("%x", hashBytes)

	// Determine language
	ext := strings.ToLower(filepath.Ext(absPath))
	lang := "unknown"
	switch ext {
	case ".go":
		lang = "Go"
	case ".py":
		lang = "Python"
	case ".ts", ".tsx", ".js", ".jsx":
		lang = "TypeScript/JavaScript"
	case ".php":
		lang = "PHP"
	default:
		return nil, nil // Ignore unsupported file types
	}

	content := string(data)
	lines := strings.Split(content, "\n")

	var symbols []SymbolResult
	var deps []string

	// Language-specific parsers
	switch lang {
	case "Go":
		symbols = parseGoSymbols(lines)
		deps = parseGoImports(content)
	case "Python":
		symbols = parsePythonSymbols(lines)
		deps = parsePythonImports(content)
	case "TypeScript/JavaScript":
		symbols = parseJSSymbols(lines)
		deps = parseJSImports(content)
	case "PHP":
		symbols = parsePHPSymbols(lines)
		deps = parsePHPImports(content)
	}

	return &FileScanResult{
		RelativePath: relPath,
		Language:     lang,
		FileHash:     fileHash,
		FileSize:     int64(len(data)),
		Symbols:      symbols,
		Dependencies: deps,
	}, nil
}

// Helper: Estimate end line using brace counting (Go, JS/TS, PHP)
func estimateBraceEndLine(lines []string, startIndex int) int {
	braceCount := 0
	foundBrace := false

	// Search up to 500 lines downstream to avoid unbounded searches on massive/malformed files
	maxSearch := startIndex + 500
	if maxSearch > len(lines) {
		maxSearch = len(lines)
	}

	for idx := startIndex; idx < maxSearch; idx++ {
		line := lines[idx]
		for _, char := range line {
			if char == '{' {
				braceCount++
				foundBrace = true
			} else if char == '}' {
				braceCount--
			}
		}
		if foundBrace && braceCount <= 0 {
			return idx + 1 // 1-based index
		}
	}
	return startIndex + 1 // Default to start line if not closed
}

// Helper: Estimate end line for Python using indentation levels
func estimatePythonEndLine(lines []string, startIndex int) int {
	defLine := lines[startIndex]
	
	// Measure base indentation (spaces or tabs)
	baseIndent := 0
	for _, char := range defLine {
		if char == ' ' {
			baseIndent++
		} else if char == '\t' {
			baseIndent += 4 // normalize tab to 4 spaces
		} else {
			break
		}
	}

	maxSearch := len(lines)
	endLine := startIndex + 1

	for idx := startIndex + 1; idx < maxSearch; idx++ {
		line := lines[idx]
		trimmed := strings.TrimSpace(line)
		
		// Skip empty lines and comments
		if trimmed == "" || strings.HasPrefix(trimmed, "#") {
			continue
		}

		// Measure current line indentation
		lineIndent := 0
		for _, char := range line {
			if char == ' ' {
				lineIndent++
			} else if char == '\t' {
				lineIndent += 4
			} else {
				break
			}
		}

		// If current line indentation is less than or equal to definition line, block has ended
		if lineIndent <= baseIndent {
			break
		}
		endLine = idx + 1
	}

	return endLine
}

// === GO PARSER ===
func parseGoSymbols(lines []string) []SymbolResult {
	var symbols []SymbolResult
	for idx, line := range lines {
		trimmed := strings.TrimSpace(line)
		// Skip empty or simple comments
		if trimmed == "" || strings.HasPrefix(trimmed, "//") {
			continue
		}

		if match := goFuncRegex.FindStringSubmatch(trimmed); len(match) > 1 {
			startLine := idx + 1
			endLine := estimateBraceEndLine(lines, idx)
			symbols = append(symbols, SymbolResult{
				Name:      match[1],
				Kind:      "function",
				StartLine: startLine,
				EndLine:   endLine,
				Signature: trimmed,
			})
		} else if match := goTypeRegex.FindStringSubmatch(trimmed); len(match) > 2 {
			startLine := idx + 1
			endLine := estimateBraceEndLine(lines, idx)
			symbols = append(symbols, SymbolResult{
				Name:      match[1],
				Kind:      match[2], // "struct" or "interface"
				StartLine: startLine,
				EndLine:   endLine,
				Signature: trimmed,
			})
		}
	}
	return symbols
}

func parseGoImports(content string) []string {
	var imports []string
	seen := make(map[string]bool)

	// Handle single-line imports
	for _, match := range goSingleImp.FindAllStringSubmatch(content, -1) {
		if len(match) > 1 && !seen[match[1]] {
			seen[match[1]] = true
			imports = append(imports, match[1])
		}
	}

	// Handle block imports
	for _, blockMatch := range goBlockImp.FindAllStringSubmatch(content, -1) {
		if len(blockMatch) > 1 {
			for _, match := range strQuoteRegex.FindAllStringSubmatch(blockMatch[1], -1) {
				if len(match) > 1 && !seen[match[1]] {
					seen[match[1]] = true
					imports = append(imports, match[1])
				}
			}
		}
	}

	return imports
}

// === PYTHON PARSER ===
func parsePythonSymbols(lines []string) []SymbolResult {
	var symbols []SymbolResult
	for idx, line := range lines {
		trimmed := strings.TrimSpace(line)
		if trimmed == "" || strings.HasPrefix(trimmed, "#") {
			continue
		}

		if match := pyDefRegex.FindStringSubmatch(line); len(match) > 1 {
			startLine := idx + 1
			endLine := estimatePythonEndLine(lines, idx)
			symbols = append(symbols, SymbolResult{
				Name:      match[1],
				Kind:      "function",
				StartLine: startLine,
				EndLine:   endLine,
				Signature: trimmed,
			})
		} else if match := pyClassRegex.FindStringSubmatch(line); len(match) > 1 {
			startLine := idx + 1
			endLine := estimatePythonEndLine(lines, idx)
			symbols = append(symbols, SymbolResult{
				Name:      match[1],
				Kind:      "class",
				StartLine: startLine,
				EndLine:   endLine,
				Signature: trimmed,
			})
		}
	}
	return symbols
}

func parsePythonImports(content string) []string {
	var imports []string
	seen := make(map[string]bool)

	// from module import ...
	for _, match := range pyFromImp.FindAllStringSubmatch(content, -1) {
		if len(match) > 1 && !seen[match[1]] {
			seen[match[1]] = true
			imports = append(imports, match[1])
		}
	}

	// import module1, module2
	for _, match := range pyImportImp.FindAllStringSubmatch(content, -1) {
		if len(match) > 1 {
			parts := strings.Split(match[1], ",")
			for _, p := range parts {
				name := strings.TrimSpace(p)
				if name != "" && !seen[name] {
					seen[name] = true
					imports = append(imports, name)
				}
			}
		}
	}

	return imports
}

// === TS/JS PARSER ===
func parseJSSymbols(lines []string) []SymbolResult {
	var symbols []SymbolResult
	for idx, line := range lines {
		trimmed := strings.TrimSpace(line)
		if trimmed == "" || strings.HasPrefix(trimmed, "//") || strings.HasPrefix(trimmed, "/*") {
			continue
		}

		if match := jsClassRegex.FindStringSubmatch(trimmed); len(match) > 1 {
			startLine := idx + 1
			endLine := estimateBraceEndLine(lines, idx)
			symbols = append(symbols, SymbolResult{
				Name:      match[1],
				Kind:      "class",
				StartLine: startLine,
				EndLine:   endLine,
				Signature: trimmed,
			})
		} else if match := jsFuncRegex.FindStringSubmatch(trimmed); len(match) > 1 {
			startLine := idx + 1
			endLine := estimateBraceEndLine(lines, idx)
			symbols = append(symbols, SymbolResult{
				Name:      match[1],
				Kind:      "function",
				StartLine: startLine,
				EndLine:   endLine,
				Signature: trimmed,
			})
		} else if match := jsArrowRegex.FindStringSubmatch(trimmed); len(match) > 1 {
			startLine := idx + 1
			endLine := estimateBraceEndLine(lines, idx)
			symbols = append(symbols, SymbolResult{
				Name:      match[1],
				Kind:      "function",
				StartLine: startLine,
				EndLine:   endLine,
				Signature: trimmed,
			})
		} else if match := jsInterface.FindStringSubmatch(trimmed); len(match) > 1 {
			startLine := idx + 1
			endLine := estimateBraceEndLine(lines, idx)
			symbols = append(symbols, SymbolResult{
				Name:      match[1],
				Kind:      "interface",
				StartLine: startLine,
				EndLine:   endLine,
				Signature: trimmed,
			})
		}
	}
	return symbols
}

func parseJSImports(content string) []string {
	var imports []string
	seen := make(map[string]bool)

	addImp := func(val string) {
		val = strings.TrimSpace(val)
		if val != "" && !seen[val] {
			seen[val] = true
			imports = append(imports, val)
		}
	}

	// import { x } from "mod"
	for _, match := range jsImportFrom.FindAllStringSubmatch(content, -1) {
		if len(match) > 1 {
			addImp(match[1])
		}
	}

	// import "mod"
	for _, match := range jsImportBasic.FindAllStringSubmatch(content, -1) {
		if len(match) > 1 {
			addImp(match[1])
		}
	}

	// import("mod")
	for _, match := range jsImportDyn.FindAllStringSubmatch(content, -1) {
		if len(match) > 1 {
			addImp(match[1])
		}
	}

	// require("mod")
	for _, match := range jsRequire.FindAllStringSubmatch(content, -1) {
		if len(match) > 1 {
			addImp(match[1])
		}
	}

	return imports
}

// === PHP PARSER ===
func parsePHPSymbols(lines []string) []SymbolResult {
	var symbols []SymbolResult
	for idx, line := range lines {
		trimmed := strings.TrimSpace(line)
		if trimmed == "" || strings.HasPrefix(trimmed, "//") || strings.HasPrefix(trimmed, "#") || strings.HasPrefix(trimmed, "/*") {
			continue
		}

		if match := phpClassRegex.FindStringSubmatch(trimmed); len(match) > 1 {
			startLine := idx + 1
			endLine := estimateBraceEndLine(lines, idx)
			symbols = append(symbols, SymbolResult{
				Name:      match[1],
				Kind:      "class",
				StartLine: startLine,
				EndLine:   endLine,
				Signature: trimmed,
			})
		} else if match := phpFuncRegex.FindStringSubmatch(trimmed); len(match) > 1 {
			startLine := idx + 1
			endLine := estimateBraceEndLine(lines, idx)
			symbols = append(symbols, SymbolResult{
				Name:      match[1],
				Kind:      "function",
				StartLine: startLine,
				EndLine:   endLine,
				Signature: trimmed,
			})
		}
	}
	return symbols
}

func parsePHPImports(content string) []string {
	var imports []string
	seen := make(map[string]bool)

	// use Namespace\Class;
	for _, match := range phpUseRegex.FindAllStringSubmatch(content, -1) {
		if len(match) > 1 && !seen[match[1]] {
			seen[match[1]] = true
			imports = append(imports, match[1])
		}
	}

	// require/include
	for _, match := range phpReqInc.FindAllStringSubmatch(content, -1) {
		if len(match) > 1 && !seen[match[1]] {
			seen[match[1]] = true
			imports = append(imports, match[1])
		}
	}

	return imports
}
