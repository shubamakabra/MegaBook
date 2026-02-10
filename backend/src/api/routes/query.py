"""Query API routes for RAG."""
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.dependencies import get_embedding_service, get_llm_provider

router = APIRouter()


class SearchRequest(BaseModel):
    """Search request model."""
    query: str
    n_results: int = 5
    filter_dict: Optional[dict] = None


class SearchResultModel(BaseModel):
    """Search result model."""
    id: str
    content: str
    metadata: dict
    distance: float
    score: float


class RAGQueryRequest(BaseModel):
    """RAG query request model."""
    query: str
    n_results: int = 5
    audience_level: str = "dm"  # or "player"


class RAGQueryResponse(BaseModel):
    """RAG query response model."""
    query: str
    answer: str
    sources: List[SearchResultModel]


@router.post("/search", response_model=List[SearchResultModel])
async def search_notes(request: SearchRequest):
    """Search notes using vector similarity."""
    embedding_service = get_embedding_service()
    
    if not embedding_service:
        raise HTTPException(status_code=503, detail="Embedding service not available")
    
    try:
        results = await embedding_service.search(
            query=request.query,
            n_results=request.n_results,
            filter_dict=request.filter_dict,
        )
        
        return [
            SearchResultModel(
                id=r.id,
                content=r.content,
                metadata=r.metadata,
                distance=r.distance,
                score=r.score,
            )
            for r in results
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rag", response_model=RAGQueryResponse)
async def rag_query(request: RAGQueryRequest):
    """Query using RAG (Retrieval Augmented Generation)."""
    embedding_service = get_embedding_service()
    llm_provider = get_llm_provider()
    
    if not embedding_service:
        raise HTTPException(status_code=503, detail="Embedding service not available")
    
    if not llm_provider:
        raise HTTPException(status_code=503, detail="LLM provider not available")
    
    try:
        # Search for relevant notes
        search_results = await embedding_service.search(
            query=request.query,
            n_results=request.n_results,
        )
        
        if not search_results:
            return RAGQueryResponse(
                query=request.query,
                answer="I don't have enough information to answer that question.",
                sources=[],
            )
        
        # Build context from search results
        context_parts = []
        for i, result in enumerate(search_results, 1):
            context_parts.append(f"Document {i}:\n{result.content}\n")
        
        context = "\n".join(context_parts)
        
        # Generate answer using LLM
        if request.audience_level == "player":
            system_prompt = """You are a helpful assistant answering questions based on provided documents.

Rules:
- Only use information from the provided documents
- If the answer isn't in the documents, say so
- Keep answers concise but complete
- This is for players, so only include information they would know in-character"""
        else:
            system_prompt = """You are a helpful assistant answering questions based on provided documents.

Rules:
- Only use information from the provided documents
- If the answer isn't in the documents, say so
- Keep answers concise but complete
- This is for the DM, so include all relevant details"""
        
        prompt = f"""Based on the following documents, answer this question:

Question: {request.query}

Documents:
{context}

Answer:"""
        
        response = await llm_provider.generate_text(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.3,
        )
        
        return RAGQueryResponse(
            query=request.query,
            answer=response.content,
            sources=[
                SearchResultModel(
                    id=r.id,
                    content=r.content,
                    metadata=r.metadata,
                    distance=r.distance,
                    score=r.score,
                )
                for r in search_results
            ],
        )
    except Exception as e:
        import traceback
        print(f"\n{'='*60}")
        print(f"RAG Query Error: {e}")
        print(traceback.format_exc())
        print(f"{'='*60}\n")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get("/stats")
async def get_embedding_stats():
    """Get embedding database statistics."""
    embedding_service = get_embedding_service()
    
    if not embedding_service:
        raise HTTPException(status_code=503, detail="Embedding service not available")
    
    return embedding_service.get_stats()