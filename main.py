from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
import os
from datetime import datetime
import uuid
from models import Document, QueryRequest, SummaryRequest, EmotionRequest, User
from services.document_service import DocumentService
from services.llm_service import LLMService
from services.storage_service import StorageService
from services.mock_storage_service import MockStorageService
from auth.dependencies import get_current_user, get_current_user_optional, get_user_uid

app = FastAPI(title="TalkToYourDocument API")

# Helper function to validate document ownership
async def validate_document_ownership(document_id: str, user_id: str) -> Document:
    """
    Validate that the user owns the document and return the document

    Args:
        document_id: ID of the document to validate
        user_id: ID of the user requesting access

    Returns:
        Document object if user owns it

    Raises:
        HTTPException: If document not found or user doesn't own it
    """
    document = await document_service.get_document(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if document.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: You can only access your own documents"
        )

    return document

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize storage service first
USE_MOCK_STORAGE = os.getenv("USE_MOCK_STORAGE", "false").lower() == "true"
storage_service = MockStorageService() if USE_MOCK_STORAGE else StorageService()

# Initialize other services with storage service
document_service = DocumentService(storage_service)
llm_service = LLMService()

@app.get("/")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.get("/auth/me")
async def get_current_user_info(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get current authenticated user information"""
    return {
        "uid": current_user["uid"],
        "email": current_user.get("email"),
        "email_verified": current_user.get("email_verified", False),
        "name": current_user.get("name"),
        "picture": current_user.get("picture")
    }

@app.get("/documents")
async def list_documents(current_user: Dict[str, Any] = Depends(get_current_user)):
    """List documents for authenticated user only"""
    user_id = current_user["uid"]
    return await document_service.list_documents(user_id=user_id)

@app.get("/documents/{document_id}")
async def get_document(
    document_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get a specific document (requires authentication and ownership)"""
    try:
        user_id = current_user["uid"]

        # Validate document ownership and return the document
        document = await validate_document_ownership(document_id, user_id)
        return document
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Upload and process a document (requires authentication)"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    # Generate unique document ID
    doc_id = str(uuid.uuid4())
    user_id = current_user["uid"]  # Always required now

    # Save file temporarily (Windows compatible)
    import tempfile
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, f"{doc_id}_{file.filename}")
    try:
        with open(temp_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        # Process document
        document = await document_service.process_document(temp_path, doc_id, file.filename, user_id)

        # Store document
        await storage_service.store_document(document, temp_path)

        # Clean up temp file
        os.remove(temp_path)

        return document
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/documents/{document_id}/chat")
async def chat_with_document(
    document_id: str,
    request: QueryRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Chat with a specific document using AI (requires authentication and ownership)"""
    try:
        user_id = current_user["uid"]

        # Validate document ownership
        await validate_document_ownership(document_id, user_id)

        # Ensure the document_id in the request matches the path parameter
        if request.document_id != document_id:
            raise HTTPException(status_code=400, detail="Document ID mismatch")

        response = await llm_service.query_document(
            document_id=request.document_id,
            query=request.query,
            query_language=request.query_language,
            target_language=request.target_language
        )
        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/query")
async def query_document(
    request: QueryRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Query a document using natural language (requires authentication) - Legacy endpoint"""
    try:
        user_id = current_user["uid"]

        # Validate document ownership
        await validate_document_ownership(request.document_id, user_id)

        response = await llm_service.query_document(
            document_id=request.document_id,
            query=request.query,
            query_language=request.query_language,
            target_language=request.target_language
        )
        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/summary")
async def summarize_document(
    request: SummaryRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Generate a summary of the document (requires authentication)"""
    try:
        user_id = current_user["uid"]

        # Validate document ownership
        await validate_document_ownership(request.document_id, user_id)

        response = await llm_service.summarize_document(
            document_id=request.document_id,
            target_language=request.target_language
        )
        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/emotion")
async def analyze_emotion(
    request: EmotionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Analyze emotional tone of the document (requires authentication)"""
    try:
        user_id = current_user["uid"]

        # Validate document ownership
        await validate_document_ownership(request.document_id, user_id)

        response = await llm_service.analyze_emotion(
            document_id=request.document_id
        )
        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Delete a document (requires authentication and ownership)"""
    try:
        user_id = current_user["uid"]

        # Validate document ownership
        await validate_document_ownership(document_id, user_id)

        await document_service.delete_document(document_id)
        await storage_service.delete_document(document_id)
        return {"status": "success", "message": f"Document {document_id} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)