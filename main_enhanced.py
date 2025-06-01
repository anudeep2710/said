#!/usr/bin/env python3
"""
Enhanced TalkToYourDocument API with all improvements implemented
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
import tempfile
import os
import uuid
import logging
from datetime import datetime
from contextlib import asynccontextmanager

# Models
from models import (
    Document, QueryRequest, QueryResponse, 
    SummaryRequest, SummaryResponse,
    EmotionRequest, EmotionResponse,
    User
)

# Enhanced services
from services.enhanced_document_service import EnhancedDocumentService
from services.llm_service import LLMService
from services.database_service import DatabaseService
from services.cache_service import cache_service
from services.rate_limiter import rate_limiter, RateLimitMiddleware, rate_limit_dependency
from services.secret_manager import secret_manager, validate_required_secrets

# Auth
from auth.dependencies import get_current_user, get_current_user_optional, get_user_uid

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global service instances
document_service = None
llm_service = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global document_service, llm_service
    
    logger.info("🚀 Starting TalkToYourDocument API...")
    
    try:
        # Validate secrets
        secret_validation = validate_required_secrets()
        missing_secrets = [name for name, exists in secret_validation.items() if not exists]
        if missing_secrets:
            logger.warning(f"Missing secrets: {missing_secrets}")
        
        # Initialize cache service
        await cache_service.initialize()
        logger.info(f"✅ Cache service initialized ({cache_service.get_cache_type()})")
        
        # Initialize document service
        document_service = EnhancedDocumentService()
        await document_service.initialize()
        logger.info(f"✅ Document service initialized ({document_service.database.get_database_type()})")
        
        # Initialize LLM service
        llm_service = LLMService()
        logger.info("✅ LLM service initialized")
        
        logger.info("🎉 All services initialized successfully!")
        
        yield
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize services: {str(e)}")
        raise
    
    finally:
        logger.info("🛑 Shutting down TalkToYourDocument API...")

# Create FastAPI app with lifespan
app = FastAPI(
    title="TalkToYourDocument API",
    description="AI-powered document analysis platform with real-time processing",
    version="2.0.0",
    lifespan=lifespan
)

# Add rate limiting middleware
app.add_middleware(RateLimitMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred",
            "request_id": str(uuid.uuid4())
        }
    )

# Health check endpoints
@app.get("/")
async def health_check():
    """Enhanced health check with service status"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0",
        "services": {
            "database": document_service.database.get_database_type() if document_service else "not_initialized",
            "cache": cache_service.get_cache_type() if cache_service else "not_initialized",
            "ai": "available" if llm_service else "not_initialized"
        }
    }

@app.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check for monitoring"""
    try:
        # Test database
        db_status = "healthy"
        try:
            await document_service.database.list_documents(limit=1)
        except Exception as e:
            db_status = f"error: {str(e)}"
        
        # Test cache
        cache_status = "healthy"
        try:
            await cache_service.set("health_check", "ok", ttl=60)
            await cache_service.get("health_check")
        except Exception as e:
            cache_status = f"error: {str(e)}"
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "database": db_status,
                "cache": cache_status,
                "ai": "healthy" if llm_service else "not_initialized"
            },
            "metrics": {
                "uptime": "calculated_in_production",
                "memory_usage": "calculated_in_production"
            }
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )

# Authentication endpoints
@app.get("/auth/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current authenticated user information"""
    return current_user

# Document management endpoints
@app.post("/upload", response_model=Document)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    current_user: Optional[User] = Depends(get_current_user_optional),
    _rate_limit: Any = Depends(lambda r, u=None: rate_limit_dependency(r, "upload", u.uid if u else None))
):
    """Upload and process a document with rate limiting"""
    try:
        user_id = current_user.uid if current_user else None
        document = await document_service.upload_and_process_document(file, user_id)
        
        logger.info(f"Document uploaded: {document.document_id} by user: {user_id}")
        return document
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        raise HTTPException(status_code=500, detail="Upload failed")

@app.get("/documents", response_model=List[Document])
async def list_documents(
    request: Request,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: Optional[User] = Depends(get_current_user_optional),
    _rate_limit: Any = Depends(lambda r, u=None: rate_limit_dependency(r, "global", u.uid if u else None))
):
    """List documents with pagination"""
    try:
        user_id = current_user.uid if current_user else None
        documents = await document_service.list_documents(user_id, limit, offset)
        return documents
        
    except Exception as e:
        logger.error(f"List documents error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list documents")

@app.get("/documents/search", response_model=List[Document])
async def search_documents(
    request: Request,
    q: str = Query(..., min_length=1, max_length=500),
    limit: int = Query(50, ge=1, le=100),
    current_user: Optional[User] = Depends(get_current_user_optional),
    _rate_limit: Any = Depends(lambda r, u=None: rate_limit_dependency(r, "global", u.uid if u else None))
):
    """Search documents with full-text search"""
    try:
        user_id = current_user.uid if current_user else None
        documents = await document_service.search_documents(q, user_id, limit)
        return documents
        
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        raise HTTPException(status_code=500, detail="Search failed")

@app.get("/documents/stats")
async def get_document_statistics(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional),
    _rate_limit: Any = Depends(lambda r, u=None: rate_limit_dependency(r, "global", u.uid if u else None))
):
    """Get document statistics"""
    try:
        user_id = current_user.uid if current_user else None
        stats = await document_service.get_document_statistics(user_id)
        return stats
        
    except Exception as e:
        logger.error(f"Stats error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get statistics")

@app.delete("/documents/{document_id}")
async def delete_document(
    request: Request,
    document_id: str,
    current_user: User = Depends(get_current_user),
    _rate_limit: Any = Depends(lambda r, u: rate_limit_dependency(r, "global", u.uid))
):
    """Delete a document (requires authentication)"""
    try:
        success = await document_service.delete_document(document_id, current_user.uid)
        if not success:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return {"status": "success", "message": f"Document {document_id} deleted"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete error: {str(e)}")
        raise HTTPException(status_code=500, detail="Delete failed")

# AI-powered endpoints
@app.post("/query", response_model=QueryResponse)
async def query_document(
    request: Request,
    query_request: QueryRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    _rate_limit: Any = Depends(lambda r, u=None: rate_limit_dependency(r, "ai_query", u.uid if u else None))
):
    """Query document with AI (with caching and rate limiting)"""
    try:
        # Check if document exists and user has access
        user_id = current_user.uid if current_user else None
        document = await document_service.get_document(query_request.document_id, user_id)
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Process AI query with caching
        response = await llm_service.query_document(query_request)
        
        logger.info(f"AI query processed for document: {query_request.document_id}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query error: {str(e)}")
        raise HTTPException(status_code=500, detail="Query processing failed")

@app.post("/summary", response_model=SummaryResponse)
async def summarize_document(
    request: Request,
    summary_request: SummaryRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    _rate_limit: Any = Depends(lambda r, u=None: rate_limit_dependency(r, "ai_query", u.uid if u else None))
):
    """Generate document summary with AI"""
    try:
        user_id = current_user.uid if current_user else None
        document = await document_service.get_document(summary_request.document_id, user_id)
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        response = await llm_service.summarize_document(summary_request)
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Summary error: {str(e)}")
        raise HTTPException(status_code=500, detail="Summary generation failed")

@app.post("/emotion", response_model=EmotionResponse)
async def analyze_emotion(
    request: Request,
    emotion_request: EmotionRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    _rate_limit: Any = Depends(lambda r, u=None: rate_limit_dependency(r, "ai_query", u.uid if u else None))
):
    """Analyze document emotion with AI"""
    try:
        user_id = current_user.uid if current_user else None
        document = await document_service.get_document(emotion_request.document_id, user_id)
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        response = await llm_service.analyze_emotion(emotion_request)
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Emotion analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail="Emotion analysis failed")

# Admin endpoints (for monitoring and management)
@app.get("/admin/cache/stats")
async def get_cache_stats(current_user: User = Depends(get_current_user)):
    """Get cache statistics (admin only)"""
    # In production, add admin role check
    return {
        "cache_type": cache_service.get_cache_type(),
        "status": "operational"
    }

@app.post("/admin/cache/clear")
async def clear_cache(current_user: User = Depends(get_current_user)):
    """Clear cache (admin only)"""
    # In production, add admin role check
    success = await cache_service.clear()
    return {"status": "success" if success else "failed"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main_enhanced:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
