package main

import (
	"fmt"
	"os"
	"path/filepath"
)

// Project represents a simple project structure
type Project struct {
	ID   string
	Path string
}

func main() {
	fmt.Println("Starting sample Go app")
}

// ProcessFiles walks a list of files
func ProcessFiles(files []string) error {
	for _, f := range files {
		fmt.Printf("Processing %s\n", f)
	}
	return nil
}
