import os
import sys
import chromadb
from chromadb.utils import embedding_functions
from typing import List, Dict, Any
import importlib.util

# Load the project_repository module directly
spec = importlib.util.spec_from_file_location("project_repository", os.path.join(os.path.dirname(os.path.dirname(__file__)), "repositories", "project_repository.py"))
project_repository_module = importlib.util.module_from_spec(spec)
sys.modules["project_repository"] = project_repository_module
spec.loader.exec_module(project_repository_module)
ProjectRepository = project_repository_module.ProjectRepository

class EmbeddingPipeline:
    def __init__(self, db_path: str = None, chromadb_dir: str = None):
        """
        Initializes the embedding pipeline.
        - db_path: Path to the SQLite hub.db
        - chromadb_dir: Directory where ChromaDB indexes are persisted locally.
        """
        # Configure Project Repository
        self.repository = ProjectRepository(db_path=db_path)
        
        if chromadb_dir is None:
            # Fallback to standard monorepo path
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            chromadb_dir = os.path.join(base_dir, "infrastructure", "chromadb", "db")
            
        self.chromadb_dir = chromadb_dir
        
        # Ensure directories exist
        os.makedirs(self.chromadb_dir, exist_ok=True)
        
        print(f"Initializing Persistent ChromaDB Client at '{self.chromadb_dir}'", file=sys.stderr)
        self.chroma_client = chromadb.PersistentClient(path=self.chromadb_dir)
        
        # Standard lightweight embedding function
        self.embedding_function = embedding_functions.DefaultEmbeddingFunction()

    def get_or_create_collection(self, name: str = "codebase_entities"):
        """Gets or creates the target vector storage collection."""
        return self.chroma_client.get_or_create_collection(
            name=name,
            embedding_function=self.embedding_function
        )

    def generate_abstract(self, file_path: str, language: str, symbols: List[Dict[str, Any]], dependencies: List[str]) -> str:
        """
        Synthesizes a clean high-density text abstract matching the Project Constitution's format layout.
        This provides structural contexts to downstream LLM requests without revealing raw code lines.
        """
        abstract_lines = []
        abstract_lines.append(f"File: {file_path}")
        abstract_lines.append(f"Language: {language}")
        
        abstract_lines.append("Exposed Symbols:")
        if len(symbols) == 0:
            abstract_lines.append("  - (None)")
        else:
            for sym in symbols:
                kind = sym.get("kind", "unknown")
                name = sym.get("name", "unknown")
                start = sym.get("start_line", 0)
                end = sym.get("end_line", 0)
                sig = sym.get("signature", "").strip()
                abstract_lines.append(f"  - {kind} {name} (Lines {start}-{end}) -> Signature: {sig}")
                
        abstract_lines.append("Imported Dependencies:")
        if len(dependencies) == 0:
            abstract_lines.append("  - (None)")
        else:
            for dep in dependencies:
                abstract_lines.append(f"  - {dep}")
                
        return "\n".join(abstract_lines)

    def run_seeding(self, collection_name: str = "codebase_entities") -> Dict[str, Any]:
        """
        Walks all files extracted by the repository layer, converts them to abstracts,
        and saves them into the local ChromaDB vector collection.
        Returns statistical summaries of the seed operation.
        """
        print("Starting ChromaDB Seeding Pipeline...", file=sys.stderr)
        
        # Fetch data from Isolation Layer
        files = self.repository.get_all_files()
        if len(files) == 0:
            print("Warning: No files discovered in SQLite database. Ensure scanner has run first.", file=sys.stderr)
            return {"files_indexed": 0, "symbols_indexed": 0, "dependencies_indexed": 0}

        collection = self.get_or_create_collection(collection_name)
        
        ids = []
        documents = []
        metadatas = []
        
        total_symbols = 0
        total_deps = 0

        for f in files:
            rel_path = f["relative_path"]
            lang = f["language"]
            f_hash = f["file_hash"]
            f_size = f["file_size"]
            
            # Fetch relational records safely
            symbols = self.repository.get_symbols_for_file(rel_path)
            dependencies = self.repository.get_dependencies_for_file(rel_path)
            
            total_symbols += len(symbols)
            total_deps += len(dependencies)
            
            # Generate the token-compressed structural abstract
            abstract = self.generate_abstract(rel_path, lang, symbols, dependencies)
            
            ids.append(rel_path)
            documents.append(abstract)
            metadatas.append({
                "relative_path": rel_path,
                "language": lang,
                "file_hash": f_hash,
                "file_size": f_size,
                "entity_count": len(symbols) + len(dependencies)
            })

        print(f"Upserting {len(ids)} abstracts into ChromaDB collection '{collection_name}'...", file=sys.stderr)
        
        # Perform chunked upserting to handle potentially large repositories comfortably
        chunk_size = 200
        for i in range(0, len(ids), chunk_size):
            end_idx = min(i + chunk_size, len(ids))
            collection.upsert(
                ids=ids[i:end_idx],
                documents=documents[i:end_idx],
                metadatas=metadatas[i:end_idx]
            )

        print("ChromaDB Seeding completed successfully.", file=sys.stderr)
        return {
            "files_indexed": len(ids),
            "symbols_indexed": total_symbols,
            "dependencies_indexed": total_deps
        }
