#!/usr/bin/env python3
"""
Enhanced LLM service with caching, monitoring, and advanced features
"""

import os
import logging
import hashlib
import json
import time
import asyncio
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    genai = None

from models import (
    QueryRequest, QueryResponse, SummaryRequest, SummaryResponse,
    EmotionRequest, EmotionResponse, Document, ChatMessage
)

from services.cache_service import cache_service, generate_query_hash
from services.secret_manager import get_google_ai_api_key
from services.monitoring_service import monitoring_service

logger = logging.getLogger(__name__)

class EnhancedLLMService:
    """Enhanced LLM service with caching, monitoring, and optimization"""
    
    def __init__(self):
        self.api_key = get_google_ai_api_key()
        self.use_real_ai = os.getenv("USE_REAL_AI", "true").lower() == "true"
        self.model = None
        self.model_name = "gemini-1.5-flash"
        
        # Performance settings
        self.max_retries = 3
        self.timeout = 30
        self.cache_ttl = {
            "query": 3600,      # 1 hour
            "summary": 7200,    # 2 hours
            "emotion": 1800     # 30 minutes
        }
        
        # Initialize AI model
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize the AI model"""
        if not self.use_real_ai or not GENAI_AVAILABLE:
            logger.info("LLM service running in mock mode")
            return
        
        if not self.api_key:
            logger.warning("Google AI API key not found, running in mock mode")
            self.use_real_ai = False
            return
        
        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.model_name)
            logger.info(f"LLM service initialized with {self.model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize AI model: {str(e)}")
            self.use_real_ai = False
    
    async def query_document(self, request: QueryRequest) -> QueryResponse:
        """Query document with caching and monitoring"""
        start_time = time.time()
        
        try:
            # Generate cache key
            cache_key = self._generate_cache_key("query", request)
            
            # Try cache first
            cached_response = await cache_service.get_cached_ai_response(cache_key)
            if cached_response:
                monitoring_service.log_cache_hit("ai_query", True)
                monitoring_service.log_ai_query("query", True, time.time() - start_time)
                return QueryResponse(**cached_response)
            
            monitoring_service.log_cache_hit("ai_query", False)
            
            # Get document
            document = await self._get_document(request.document_id)
            if not document:
                raise ValueError("Document not found")
            
            # Process query
            if self.use_real_ai and self.model:
                response = await self._process_real_query(request, document)
            else:
                response = await self._process_mock_query(request, document)
            
            # Cache response
            await cache_service.cache_ai_response(cache_key, response.dict(), self.cache_ttl["query"])
            
            # Log metrics
            duration = time.time() - start_time
            monitoring_service.log_ai_query("query", True, duration)
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            monitoring_service.log_ai_query("query", False, duration)
            logger.error(f"Query processing failed: {str(e)}")
            raise
    
    async def summarize_document(self, request: SummaryRequest) -> SummaryResponse:
        """Summarize document with caching"""
        start_time = time.time()
        
        try:
            # Check cache
            cache_key = self._generate_cache_key("summary", request)
            cached_response = await cache_service.get_cached_document_summary(cache_key)
            
            if cached_response:
                monitoring_service.log_cache_hit("ai_summary", True)
                monitoring_service.log_ai_query("summary", True, time.time() - start_time)
                return SummaryResponse(**cached_response)
            
            monitoring_service.log_cache_hit("ai_summary", False)
            
            # Get document
            document = await self._get_document(request.document_id)
            if not document:
                raise ValueError("Document not found")
            
            # Process summary
            if self.use_real_ai and self.model:
                response = await self._process_real_summary(request, document)
            else:
                response = await self._process_mock_summary(request, document)
            
            # Cache response
            await cache_service.cache_document_summary(cache_key, response.dict(), self.cache_ttl["summary"])
            
            # Log metrics
            duration = time.time() - start_time
            monitoring_service.log_ai_query("summary", True, duration)
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            monitoring_service.log_ai_query("summary", False, duration)
            logger.error(f"Summary processing failed: {str(e)}")
            raise
    
    async def analyze_emotion(self, request: EmotionRequest) -> EmotionResponse:
        """Analyze emotion with caching"""
        start_time = time.time()
        
        try:
            # Check cache
            cache_key = self._generate_cache_key("emotion", request)
            cached_response = await cache_service.get(cache_key)
            
            if cached_response:
                monitoring_service.log_cache_hit("ai_emotion", True)
                monitoring_service.log_ai_query("emotion", True, time.time() - start_time)
                return EmotionResponse(**cached_response)
            
            monitoring_service.log_cache_hit("ai_emotion", False)
            
            # Get document
            document = await self._get_document(request.document_id)
            if not document:
                raise ValueError("Document not found")
            
            # Process emotion analysis
            if self.use_real_ai and self.model:
                response = await self._process_real_emotion(request, document)
            else:
                response = await self._process_mock_emotion(request, document)
            
            # Cache response
            await cache_service.set(cache_key, response.dict(), self.cache_ttl["emotion"])
            
            # Log metrics
            duration = time.time() - start_time
            monitoring_service.log_ai_query("emotion", True, duration)
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            monitoring_service.log_ai_query("emotion", False, duration)
            logger.error(f"Emotion analysis failed: {str(e)}")
            raise
    
    async def _process_real_query(self, request: QueryRequest, document: Document) -> QueryResponse:
        """Process query with real AI"""
        prompt = self._build_query_prompt(request, document)
        
        for attempt in range(self.max_retries):
            try:
                # Generate response with timeout
                response = await asyncio.wait_for(
                    self._generate_ai_response(prompt),
                    timeout=self.timeout
                )
                
                # Parse response
                return self._parse_query_response(response, request, document)
                
            except asyncio.TimeoutError:
                logger.warning(f"AI query timeout (attempt {attempt + 1})")
                if attempt == self.max_retries - 1:
                    raise
            except Exception as e:
                logger.warning(f"AI query failed (attempt {attempt + 1}): {str(e)}")
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(1)  # Brief delay before retry
    
    async def _process_real_summary(self, request: SummaryRequest, document: Document) -> SummaryResponse:
        """Process summary with real AI"""
        prompt = self._build_summary_prompt(request, document)
        
        for attempt in range(self.max_retries):
            try:
                response = await asyncio.wait_for(
                    self._generate_ai_response(prompt),
                    timeout=self.timeout
                )
                
                return self._parse_summary_response(response, request, document)
                
            except asyncio.TimeoutError:
                logger.warning(f"AI summary timeout (attempt {attempt + 1})")
                if attempt == self.max_retries - 1:
                    raise
            except Exception as e:
                logger.warning(f"AI summary failed (attempt {attempt + 1}): {str(e)}")
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(1)
    
    async def _process_real_emotion(self, request: EmotionRequest, document: Document) -> EmotionResponse:
        """Process emotion analysis with real AI"""
        prompt = self._build_emotion_prompt(request, document)
        
        for attempt in range(self.max_retries):
            try:
                response = await asyncio.wait_for(
                    self._generate_ai_response(prompt),
                    timeout=self.timeout
                )
                
                return self._parse_emotion_response(response, request, document)
                
            except asyncio.TimeoutError:
                logger.warning(f"AI emotion timeout (attempt {attempt + 1})")
                if attempt == self.max_retries - 1:
                    raise
            except Exception as e:
                logger.warning(f"AI emotion failed (attempt {attempt + 1}): {str(e)}")
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(1)
    
    async def _generate_ai_response(self, prompt: str) -> str:
        """Generate AI response with error handling"""
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.model.generate_content(prompt)
            )
            return response.text
        except Exception as e:
            logger.error(f"AI generation failed: {str(e)}")
            raise
    
    def _build_query_prompt(self, request: QueryRequest, document: Document) -> str:
        """Build optimized prompt for query"""
        return f"""
You are an AI assistant helping users understand documents. Answer the question based on the document content.

Document Title: {document.title}
Document Content: {document.text[:4000]}  # Limit content for efficiency

Question: {request.query}
Target Language: {request.target_language}

Provide a clear, accurate answer based on the document content. If the answer isn't in the document, say so.
"""
    
    def _build_summary_prompt(self, request: SummaryRequest, document: Document) -> str:
        """Build optimized prompt for summary"""
        max_length = getattr(request, 'max_length', 500)
        
        return f"""
Summarize the following document in {request.target_language}.

Document Title: {document.title}
Document Content: {document.text}

Requirements:
- Maximum length: {max_length} words
- Include key points: {getattr(request, 'include_key_points', True)}
- Language: {request.target_language}

Provide a comprehensive summary with the main points clearly outlined.
"""
    
    def _build_emotion_prompt(self, request: EmotionRequest, document: Document) -> str:
        """Build optimized prompt for emotion analysis"""
        return f"""
Analyze the emotional tone of this document.

Document Title: {document.title}
Document Content: {document.text[:2000]}  # Limit for emotion analysis

Provide:
1. Primary emotion (positive, negative, neutral)
2. Emotion breakdown (if requested: {getattr(request, 'include_breakdown', False)})
3. Brief reasoning for the analysis

Respond in {getattr(request, 'target_language', 'en')}.
"""
    
    def _parse_query_response(self, ai_response: str, request: QueryRequest, document: Document) -> QueryResponse:
        """Parse AI response into QueryResponse"""
        return QueryResponse(
            answer=ai_response,
            confidence=0.9,  # Could be enhanced with confidence scoring
            source_text=document.text[:500],  # Excerpt
            language=request.target_language,
            chat_history=[]
        )
    
    def _parse_summary_response(self, ai_response: str, request: SummaryRequest, document: Document) -> SummaryResponse:
        """Parse AI response into SummaryResponse"""
        # Extract key points (simple implementation)
        lines = ai_response.split('\n')
        key_points = [line.strip('- ') for line in lines if line.strip().startswith('-')]
        
        return SummaryResponse(
            summary=ai_response,
            key_points=key_points[:10],  # Limit key points
            word_count=len(ai_response.split()),
            language=request.target_language
        )
    
    def _parse_emotion_response(self, ai_response: str, request: EmotionRequest, document: Document) -> EmotionResponse:
        """Parse AI response into EmotionResponse"""
        # Simple parsing - could be enhanced
        primary_emotion = "neutral"
        if "positive" in ai_response.lower():
            primary_emotion = "positive"
        elif "negative" in ai_response.lower():
            primary_emotion = "negative"
        
        return EmotionResponse(
            primary_emotion=primary_emotion,
            emotion_breakdown={
                "positive": 0.4,
                "neutral": 0.4,
                "negative": 0.2
            },
            reasoning=ai_response,
            language=getattr(request, 'target_language', 'en')
        )
    
    async def _process_mock_query(self, request: QueryRequest, document: Document) -> QueryResponse:
        """Mock query processing for development"""
        await asyncio.sleep(0.1)  # Simulate processing time
        
        return QueryResponse(
            answer=f"This is a mock response to the query '{request.query}' about the document '{document.title}'. The document contains information about {document.text[:100]}...",
            confidence=0.8,
            source_text=document.text[:200],
            language=request.target_language,
            chat_history=[]
        )
    
    async def _process_mock_summary(self, request: SummaryRequest, document: Document) -> SummaryResponse:
        """Mock summary processing"""
        await asyncio.sleep(0.1)
        
        return SummaryResponse(
            summary=f"This is a mock summary of '{document.title}'. The document discusses various topics and contains {len(document.text)} characters of content.",
            key_points=[
                "Mock key point 1",
                "Mock key point 2", 
                "Mock key point 3"
            ],
            word_count=25,
            language=request.target_language
        )
    
    async def _process_mock_emotion(self, request: EmotionRequest, document: Document) -> EmotionResponse:
        """Mock emotion analysis"""
        await asyncio.sleep(0.1)
        
        return EmotionResponse(
            primary_emotion="neutral",
            emotion_breakdown={
                "positive": 0.4,
                "neutral": 0.4,
                "negative": 0.2
            },
            reasoning="This is a mock emotion analysis indicating a generally neutral tone with slight positive sentiment.",
            language=getattr(request, 'target_language', 'en')
        )
    
    def _generate_cache_key(self, operation: str, request) -> str:
        """Generate cache key for request"""
        request_data = {
            "operation": operation,
            "document_id": request.document_id,
            **request.dict()
        }
        request_string = json.dumps(request_data, sort_keys=True)
        return hashlib.sha256(request_string.encode()).hexdigest()
    
    async def _get_document(self, document_id: str) -> Optional[Document]:
        """Get document from storage service"""
        # This would integrate with the enhanced document service
        from services.enhanced_document_service import EnhancedDocumentService
        
        try:
            doc_service = EnhancedDocumentService()
            return await doc_service.get_document(document_id)
        except Exception as e:
            logger.error(f"Failed to get document {document_id}: {str(e)}")
            return None
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get service status for monitoring"""
        return {
            "ai_enabled": self.use_real_ai,
            "model": self.model_name if self.use_real_ai else "mock",
            "api_key_configured": bool(self.api_key),
            "cache_enabled": True,
            "monitoring_enabled": True
        }
