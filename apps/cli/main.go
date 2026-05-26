package main

import (
	"flag"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"strings"
	"time"
)

func main() {
	if len(os.Args) < 2 {
		printUsageAndExit()
	}

	command := os.Args[1]
	switch command {
	case "init":
		runInit()
	case "parse":
		runParse(os.Args[2:])
	default:
		fmt.Printf("Unknown command: %s\n", command)
		printUsageAndExit()
	}
}

func printUsageAndExit() {
	fmt.Println("WikiHub CLI - The Muscle")
	fmt.Println("Usage:")
	fmt.Println("  go run main.go init                   Initialize the SQLite hub.db database schema")
	fmt.Println("  go run main.go parse --path <path>    Walk, parse, and index codebase entities in SQLite")
	os.Exit(1)
}

func runInit() {
	dbPath := "hub.db"
	fmt.Printf("Initializing database at '%s'...\n", dbPath)

	db, err := InitDB(dbPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error initializing database: %v\n", err)
		os.Exit(1)
	}
	defer db.Close()

	fmt.Println("Database initialized successfully with relational schema:")
	fmt.Println("  - files (relative_path, language, last_sync, entity_count, file_hash, file_size)")
	fmt.Println("  - symbols (file_path, name, kind, start_line, end_line, signature)")
	fmt.Println("  - dependencies (source_file, import_path)")
}

func runParse(args []string) {
	parseCmd := flag.NewFlagSet("parse", flag.ExitOnError)
	pathFlag := parseCmd.String("path", "", "Target directory path to parse")

	err := parseCmd.Parse(args)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error parsing flags: %v\n", err)
		os.Exit(1)
	}

	if *pathFlag == "" {
		fmt.Fprintln(os.Stderr, "Error: --path parameter is required.")
		parseCmd.Usage()
		os.Exit(1)
	}

	targetPath, err := filepath.Abs(*pathFlag)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error resolving absolute path: %v\n", err)
		os.Exit(1)
	}

	// Verify target exists
	info, err := os.Stat(targetPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error target path not found: %v\n", err)
		os.Exit(1)
	}
	if !info.IsDir() {
		fmt.Fprintf(os.Stderr, "Error target path must be a directory.\n")
		os.Exit(1)
	}

	dbPath := "hub.db"
	db, err := InitDB(dbPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error connecting to database: %v\n", err)
		os.Exit(1)
	}
	defer db.Close()

	// Apply optimized PRAGMAs for massive scan throughput
	db.Exec("PRAGMA journal_mode=WAL;")
	db.Exec("PRAGMA synchronous=NORMAL;")

	fmt.Printf("Scanning directory: %s\n", targetPath)
	startTime := time.Now()

	var filesToScan []string

	// 1. Walk directory and collect matching paths (filtering ignores at directory walker step for speed)
	err = filepath.WalkDir(targetPath, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() {
			name := d.Name()
			if name == ".git" || name == "node_modules" || name == "vendor" || name == ".gemini" || name == "dist" || name == "target" || name == ".nuxt" {
				return filepath.SkipDir
			}
			return nil
		}

		ext := strings.ToLower(filepath.Ext(path))
		if ext == ".go" || ext == ".py" || ext == ".ts" || ext == ".tsx" || ext == ".js" || ext == ".jsx" || ext == ".php" {
			filesToScan = append(filesToScan, path)
		}
		return nil
	})

	if err != nil {
		fmt.Fprintf(os.Stderr, "Error walking directory: %v\n", err)
		os.Exit(1)
	}

	totalFiles := len(filesToScan)
	fmt.Printf("Discovered %d match files. Starting AST & dependency parsing...\n", totalFiles)

	parsedCount := 0
	symbolCount := 0
	dependencyCount := 0

	// 2. Parse collected files and commit to database
	for _, absPath := range filesToScan {
		relPath, err := filepath.Rel(targetPath, absPath)
		if err != nil {
			relPath = absPath
		}

		res, err := ParseFile(absPath, relPath)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Warning: failed to parse %s: %v\n", relPath, err)
			continue
		}
		if res == nil {
			continue
		}

		err = db.SaveScanResult(res)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error saving scan results for %s: %v\n", relPath, err)
			os.Exit(1)
		}

		parsedCount++
		symbolCount += len(res.Symbols)
		dependencyCount += len(res.Dependencies)
	}

	duration := time.Since(startTime)

	fmt.Println("\n================ Scan Complete ================")
	fmt.Printf("Total Files Synced:       %d\n", parsedCount)
	fmt.Printf("Total Symbols Extracted:  %d\n", symbolCount)
	fmt.Printf("Total Dependencies:       %d\n", dependencyCount)
	fmt.Printf("Total Scan Duration:      %s\n", duration)
	fmt.Println("===============================================")
}
