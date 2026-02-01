"""Fast RAG pipeline with ChromaDB and sentence transformers."""
import logging
from typing import List, Dict, Optional
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import hashlib

from .config import config

logger = logging.getLogger(__name__)

class RAGPipeline:
    def __init__(self):
        self.client = None
        self.collection = None
        self.embedder = None
        self._init_components()
    
    def _init_components(self):
        """Initialize ChromaDB and embeddings."""
        try:
            # Initialize ChromaDB
            self.client = chromadb.PersistentClient(
                path=config.chroma_persist_dir,
                settings=Settings(anonymized_telemetry=False)
            )
            
            # Get or create collection
            self.collection = self.client.get_or_create_collection(
                name="knowledge_base",
                metadata={"hnsw:space": "cosine"}
            )
            
            # Initialize fast embedder
            self.embedder = SentenceTransformer(config.embedding_model)
            
            logger.info("RAG pipeline initialized")
            
        except Exception as e:
            logger.error(f"RAG initialization failed: {e}")
            self.client = None
    
    def _generate_id(self, text: str) -> str:
        """Generate unique ID for document."""
        return hashlib.md5(text.encode()).hexdigest()
    
    async def add_document(self, text: str, metadata: Optional[Dict] = None):
        """Add document to knowledge base."""
        if not self.client:
            return False
        
        try:
            doc_id = self._generate_id(text)
            embedding = self.embedder.encode([text])[0].tolist()
            
            self.collection.upsert(
                ids=[doc_id],
                embeddings=[embedding],
                documents=[text],
                metadatas=[metadata or {}]
            )
            
            logger.info(f"Document added: {doc_id[:8]}...")
            return True
            
        except Exception as e:
            logger.error(f"Document add error: {e}")
            return False
    
    async def query(self, query_text: str, n_results: int = None) -> List[Dict]:
        """Query knowledge base for relevant documents."""
        if not self.client:
            return []
        
        n_results = n_results or config.max_rag_results
        
        try:
            # Generate query embedding
            query_embedding = self.embedder.encode([query_text])[0].tolist()
            
            # Search
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                include=["documents", "metadatas", "distances"]
            )
            
            # Format results
            formatted_results = []
            for i, doc in enumerate(results["documents"][0]):
                formatted_results.append({
                    "content": doc,
                    "metadata": results["metadatas"][0][i],
                    "score": 1 - results["distances"][0][i]  # Convert distance to similarity
                })
            
            logger.info(f"RAG query returned {len(formatted_results)} results")
            return formatted_results
            
        except Exception as e:
            logger.error(f"RAG query error: {e}")
            return []
    
    async def get_context(self, query: str) -> str:
        """Get formatted context for LLM."""
        results = await self.query(query)
        
        if not results:
            return ""
        
        context_parts = []
        for i, result in enumerate(results, 1):
            context_parts.append(f"[Context {i}]: {result['content']}")
        
        return "\n\n".join(context_parts)
    
    def get_stats(self) -> Dict:
        """Get collection statistics."""
        if not self.collection:
            return {"documents": 0, "status": "unavailable"}
        
        try:
            count = self.collection.count()
            return {"documents": count, "status": "ready"}
        except Exception as e:
            return {"documents": 0, "status": f"error: {e}"}

# Global instance
rag = RAGPipeline()