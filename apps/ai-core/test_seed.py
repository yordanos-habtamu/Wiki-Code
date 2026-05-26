import os
import sys

# Redefine sys.stdout to target sys.stderr immediately to enforce 100% zero stdout pollution rules
sys.stdout = sys.stderr

import time
import importlib.util
import sys

# Load the embedding_pipeline module directly
spec = importlib.util.spec_from_file_location("embedding_pipeline", os.path.join(os.path.dirname(__file__), "pipelines", "embedding_pipeline.py"))
embedding_pipeline_module = importlib.util.module_from_spec(spec)
sys.modules["embedding_pipeline"] = embedding_pipeline_module
spec.loader.exec_module(embedding_pipeline_module)
EmbeddingPipeline = embedding_pipeline_module.EmbeddingPipeline

def main():
    print("=================== Starting Semantic Seeding Verification ===================", file=sys.stderr)
    
    # 1. Resolve paths
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "..", "cli", "hub.db")
    chromadb_dir = os.path.join(base_dir, "..", "..", "infrastructure", "chromadb", "db")

    # 2. Instantiate pipeline
    start_time = time.time()
    pipeline = EmbeddingPipeline(db_path=db_path, chromadb_dir=chromadb_dir)
    
    # 3. Seed vectors
    stats = pipeline.run_seeding()
    
    print("\n--- Seeding Diagnostic Metrics ---", file=sys.stderr)
    print(f"Files Indexed:        {stats['files_indexed']}", file=sys.stderr)
    print(f"Symbols Seeded:       {stats['symbols_indexed']}", file=sys.stderr)
    print(f"Dependencies Seeded:  {stats['dependencies_indexed']}", file=sys.stderr)
    print(f"Duration:             {time.time() - start_time:.4f} seconds", file=sys.stderr)

    if stats['files_indexed'] == 0:
        print("\nERROR: Database contains no files to seed. Run the Go CLI scan first.", file=sys.stderr)
        sys.exit(1)

    # 4. Perform Precision-Testing Query (Semantic Search)
    print("\n--- Running Semantic Precision Search Verification ---", file=sys.stderr)
    collection = pipeline.get_or_create_collection()
    
    # Test Query 1: Search for class/struct structures (matching Project or CodeScanner)
    search_query = "class scanner or project structures"
    print(f"Querying: '{search_query}'", file=sys.stderr)
    
    results = collection.query(
        query_texts=[search_query],
        n_results=2
    )
    
    print("\nSearch Query Results:", file=sys.stderr)
    if results and "documents" in results and len(results["documents"]) > 0:
        for idx, (doc, doc_id, distance) in enumerate(zip(results["documents"][0], results["ids"][0], results["distances"][0])):
            print(f"\nResult #{idx+1} [ID: {doc_id}] [Distance Score: {distance:.4f}]:", file=sys.stderr)
            # Indent abstract lines for elegant printing
            indented = "\n".join("  " + line for line in doc.splitlines())
            print(indented, file=sys.stderr)
    else:
        print("No search results returned.", file=sys.stderr)

    print("\n=================== Seeding Verification Completed ===================", file=sys.stderr)

if __name__ == "__main__":
    main()
