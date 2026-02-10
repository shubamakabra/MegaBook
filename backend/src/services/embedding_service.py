"""Embedding service for MegaBook.

Provides vector storage and search using ChromaDB with SQLite backend.
"""
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.utils import embedding_functions

from src.services.llm_provider import LLMProvider


@dataclass
class SearchResult:
    """Result from a vector search."""
    id: str
    content: str
    metadata: Dict
    distance: float
    score: float  # 1.0 - distance (normalized)


class EmbeddingService:
    """Service for managing embeddings and vector search.
    
    Uses ChromaDB with SQLite backend for persistence.
    """
    
    def __init__(
        self,
        db_path: Path,
        llm_provider: Optional[LLMProvider] = None,
        collection_name: str = "megabook_notes",
    ) -> None:
        """Initialize the embedding service.
        
        Args:
            db_path: Path to store the vector database
            llm_provider: LLM provider for generating embeddings (optional)
            collection_name: Name of the ChromaDB collection
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.llm_provider = llm_provider
        self.collection_name = collection_name
        
        # Initialize ChromaDB client with SQLite
        self.client = chromadb.PersistentClient(
            path=str(self.db_path),
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True,
            ),
        )
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
    
    async def add_notes(
        self,
        notes: List[Dict[str, str]],
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> List[str]:
        """Add notes to the vector database.
        
        Args:
            notes: List of notes with 'id', 'content', and 'metadata' keys
            chunk_size: Size of chunks for splitting long notes
            chunk_overlap: Overlap between chunks
            
        Returns:
            List of added document IDs
        """
        all_ids = []
        all_contents = []
        all_metadatas = []
        
        for note in notes:
            note_id = note["id"]
            content = note["content"]
            metadata = note.get("metadata", {})
            
            # Split long content into chunks
            if len(content) > chunk_size:
                chunks = self._split_text(content, chunk_size, chunk_overlap)
                for i, chunk in enumerate(chunks):
                    chunk_id = f"{note_id}_chunk_{i}"
                    all_ids.append(chunk_id)
                    all_contents.append(chunk)
                    chunk_metadata = {
                        **metadata,
                        "note_id": note_id,
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                    }
                    all_metadatas.append(chunk_metadata)
            else:
                all_ids.append(note_id)
                all_contents.append(content)
                all_metadatas.append(metadata)
        
        # Generate embeddings
        if self.llm_provider:
            embeddings = await self.llm_provider.generate_embeddings(all_contents)
        else:
            # Use default ChromaDB embedding function
            ef = embedding_functions.DefaultEmbeddingFunction()
            embeddings = ef(all_contents)
        
        # Add to collection
        self.collection.add(
            ids=all_ids,
            documents=all_contents,
            metadatas=all_metadatas,
            embeddings=embeddings,
        )
        
        return all_ids
    
    async def search(
        self,
        query: str,
        n_results: int = 5,
        filter_dict: Optional[Dict] = None,
    ) -> List[SearchResult]:
        """Search for similar notes.
        
        Args:
            query: Search query
            n_results: Number of results to return
            filter_dict: Optional metadata filter
            
        Returns:
            List of search results
        """
        # Generate query embedding
        if self.llm_provider:
            query_embedding = await self.llm_provider.generate_embeddings([query])
            query_embedding = query_embedding[0]
        else:
            ef = embedding_functions.DefaultEmbeddingFunction()
            query_embedding = ef([query])[0]
        
        # Search
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=filter_dict,
            include=["documents", "metadatas", "distances"],
        )
        
        # Format results
        search_results = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i]
                search_results.append(SearchResult(
                    id=doc_id,
                    content=results["documents"][0][i],
                    metadata=results["metadatas"][0][i],
                    distance=distance,
                    score=1.0 - distance,  # Cosine distance to similarity
                ))
        
        return search_results
    
    def delete_notes(self, note_ids: List[str]) -> None:
        """Delete notes from the vector database.
        
        Args:
            note_ids: List of note IDs to delete
        """
        # Delete exact matches
        self.collection.delete(ids=note_ids)
        
        # Also delete chunks
        for note_id in note_ids:
            self.collection.delete(
                where={"note_id": note_id}
            )
    
    def get_stats(self) -> Dict:
        """Get database statistics.
        
        Returns:
            Dictionary with count and other stats
        """
        return {
            "count": self.collection.count(),
            "collection_name": self.collection_name,
            "db_path": str(self.db_path),
        }
    
    def clear_all(self) -> None:
        """Clear all embeddings from the database."""
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
    
    def rebuild_from_notes(
        self,
        notes_dir: Path,
        llm_provider: LLMProvider,
    ) -> Dict:
        """Rebuild embeddings from notes directory.
        
        Args:
            notes_dir: Path to notes directory
            llm_provider: LLM provider for embeddings
            
        Returns:
            Statistics about the rebuild
        """
        self.clear_all()
        
        notes = []
        for md_file in notes_dir.rglob("*.md"):
            relative_path = str(md_file.relative_to(notes_dir))
            content = md_file.read_text(encoding="utf-8")
            
            notes.append({
                "id": hashlib.md5(relative_path.encode()).hexdigest(),
                "content": content,
                "metadata": {
                    "file_path": relative_path,
                    "title": md_file.stem,
                },
            })
        
        # Temporarily set provider
        old_provider = self.llm_provider
        self.llm_provider = llm_provider
        
        # Add all notes
        import asyncio
        ids = asyncio.run(self.add_notes(notes))
        
        # Restore provider
        self.llm_provider = old_provider
        
        return {
            "total_notes": len(notes),
            "total_chunks": len(ids),
            "db_stats": self.get_stats(),
        }
    
    def _split_text(
        self,
        text: str,
        chunk_size: int,
        chunk_overlap: int,
    ) -> List[str]:
        """Split text into overlapping chunks.
        
        Args:
            text: Text to split
            chunk_size: Size of each chunk
            chunk_overlap: Overlap between chunks
            
        Returns:
            List of text chunks
        """
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            
            # Try to break at paragraph or sentence
            if end < len(text):
                # Look for paragraph break
                paragraph_break = chunk.rfind("\n\n")
                if paragraph_break > chunk_size * 0.5:
                    end = start + paragraph_break
                    chunk = text[start:end]
                else:
                    # Look for sentence break
                    sentence_break = max(
                        chunk.rfind(". "),
                        chunk.rfind("! "),
                        chunk.rfind("? "),
                    )
                    if sentence_break > chunk_size * 0.5:
                        end = start + sentence_break + 1
                        chunk = text[start:end]
            
            chunks.append(chunk.strip())
            start = end - chunk_overlap
        
        return chunks
    
    def export_to_json(self, output_path: Path) -> None:
        """Export all embeddings to JSON for backup.
        
        Args:
            output_path: Path to save JSON file
        """
        data = self.collection.get(include=["documents", "metadatas", "embeddings"])
        
        export_data = {
            "collection_name": self.collection_name,
            "count": len(data["ids"]),
            "documents": [
                {
                    "id": data["ids"][i],
                    "content": data["documents"][i] if data["documents"] else None,
                    "metadata": data["metadatas"][i] if data["metadatas"] else None,
                    "embedding": data["embeddings"][i].tolist() if data["embeddings"] else None,
                }
                for i in range(len(data["ids"]))
            ],
        }
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2)
    
    def import_from_json(self, input_path: Path) -> int:
        """Import embeddings from JSON backup.
        
        Args:
            input_path: Path to JSON file
            
        Returns:
            Number of documents imported
        """
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        documents = data.get("documents", [])
        
        if documents:
            self.collection.add(
                ids=[d["id"] for d in documents],
                documents=[d["content"] for d in documents],
                metadatas=[d["metadata"] for d in documents],
                embeddings=[d["embedding"] for d in documents],
            )
        
        return len(documents)