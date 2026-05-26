package main

import (
	"database/sql"
	"fmt"
	"os"
	"path/filepath"

	_ "github.com/mattn/go-sqlite3"
)

// DbInstance wraps the SQLite connection
type DbInstance struct {
	*sql.DB
}

// InitDB initializes the SQLite database at the specified path
func InitDB(dbPath string) (*DbInstance, error) {
	// Ensure directory exists
	dir := filepath.Dir(dbPath)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create db directory: %w", err)
	}

	db, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		return nil, fmt.Errorf("failed to open database: %w", err)
	}

	// Set connection limits to handle potential concurrency safely
	db.SetMaxOpenConns(1)

	dbi := &DbInstance{DB: db}
	if err := dbi.createSchema(); err != nil {
		db.Close()
		return nil, err
	}

	return dbi, nil
}

// createSchema sets up the required tables and indexes
func (db *DbInstance) createSchema() error {
	schema := `
	CREATE TABLE IF NOT EXISTS files (
		relative_path TEXT PRIMARY KEY,
		language TEXT NOT NULL,
		last_sync DATETIME DEFAULT CURRENT_TIMESTAMP,
		entity_count INTEGER DEFAULT 0,
		file_hash TEXT NOT NULL,
		file_size INTEGER DEFAULT 0
	);

	CREATE TABLE IF NOT EXISTS symbols (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		file_path TEXT NOT NULL,
		name TEXT NOT NULL,
		kind TEXT NOT NULL,
		start_line INTEGER NOT NULL,
		end_line INTEGER NOT NULL,
		signature TEXT NOT NULL,
		FOREIGN KEY(file_path) REFERENCES files(relative_path) ON DELETE CASCADE
	);

	CREATE TABLE IF NOT EXISTS dependencies (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		source_file TEXT NOT NULL,
		import_path TEXT NOT NULL,
		FOREIGN KEY(source_file) REFERENCES files(relative_path) ON DELETE CASCADE
	);

	CREATE INDEX IF NOT EXISTS idx_symbols_file_path ON symbols(file_path);
	CREATE INDEX IF NOT EXISTS idx_dependencies_source_file ON dependencies(source_file);
	`

	_, err := db.Exec(schema)
	if err != nil {
		return fmt.Errorf("failed to execute schema: %w", err)
	}
	return nil
}

// SaveScanResult writes a parsed file, its symbols, and its dependencies into SQLite atomically using a transaction
func (db *DbInstance) SaveScanResult(res *FileScanResult) error {
	tx, err := db.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback()

	// 1. Insert or replace file record
	fileQuery := `
	INSERT OR REPLACE INTO files (relative_path, language, last_sync, entity_count, file_hash, file_size)
	VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?, ?)`
	
	_, err = tx.Exec(fileQuery, res.RelativePath, res.Language, len(res.Symbols)+len(res.Dependencies), res.FileHash, res.FileSize)
	if err != nil {
		return fmt.Errorf("failed to save file record: %w", err)
	}

	// 2. Clear out old entries for this file to ensure clean sync (idempotency)
	_, err = tx.Exec("DELETE FROM symbols WHERE file_path = ?", res.RelativePath)
	if err != nil {
		return fmt.Errorf("failed to clear symbols: %w", err)
	}
	_, err = tx.Exec("DELETE FROM dependencies WHERE source_file = ?", res.RelativePath)
	if err != nil {
		return fmt.Errorf("failed to clear dependencies: %w", err)
	}

	// 3. Batch insert symbols
	if len(res.Symbols) > 0 {
		stmt, err := tx.Prepare(`
		INSERT INTO symbols (file_path, name, kind, start_line, end_line, signature)
		VALUES (?, ?, ?, ?, ?, ?)`)
		if err != nil {
			return fmt.Errorf("failed to prepare symbol statement: %w", err)
		}
		defer stmt.Close()

		for _, sym := range res.Symbols {
			_, err = stmt.Exec(res.RelativePath, sym.Name, sym.Kind, sym.StartLine, sym.EndLine, sym.Signature)
			if err != nil {
				return fmt.Errorf("failed to insert symbol: %w", err)
			}
		}
	}

	// 4. Batch insert dependencies
	if len(res.Dependencies) > 0 {
		stmt, err := tx.Prepare(`
		INSERT INTO dependencies (source_file, import_path)
		VALUES (?, ?)`)
		if err != nil {
			return fmt.Errorf("failed to prepare dependency statement: %w", err)
		}
		defer stmt.Close()

		for _, dep := range res.Dependencies {
			_, err = stmt.Exec(res.RelativePath, dep)
			if err != nil {
				return fmt.Errorf("failed to insert dependency: %w", err)
			}
		}
	}

	return tx.Commit()
}
