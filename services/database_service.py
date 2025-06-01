#!/usr/bin/env python3
"""
Database service with PostgreSQL primary and Firestore fallback
"""

import os
import json
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
from abc import ABC, abstractmethod

# Database imports
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False
    asyncpg = None

try:
    from google.cloud import firestore
    FIRESTORE_AVAILABLE = True
except ImportError:
    FIRESTORE_AVAILABLE = False
    firestore = None

from models import Document

logger = logging.getLogger(__name__)

class DatabaseInterface(ABC):
    """Abstract database interface"""
    
    @abstractmethod
    async def save_document(self, document: Document) -> bool:
        pass
    
    @abstractmethod
    async def get_document(self, document_id: str) -> Optional[Document]:
        pass
    
    @abstractmethod
    async def list_documents(self, user_id: Optional[str] = None, limit: int = 100) -> List[Document]:
        pass
    
    @abstractmethod
    async def delete_document(self, document_id: str) -> bool:
        pass
    
    @abstractmethod
    async def update_document(self, document: Document) -> bool:
        pass
    
    @abstractmethod
    async def search_documents(self, query: str, user_id: Optional[str] = None) -> List[Document]:
        pass

class PostgreSQLDatabase(DatabaseInterface):
    """PostgreSQL database implementation"""
    
    def __init__(self):
        self.connection_string = os.getenv("DATABASE_URL")
        self.pool = None
        
    async def initialize(self):
        """Initialize database connection pool"""
        if not self.connection_string:
            raise ValueError("DATABASE_URL environment variable not set")
        
        try:
            self.pool = await asyncpg.create_pool(
                self.connection_string,
                min_size=1,
                max_size=10,
                command_timeout=60
            )
            await self._create_tables()
            logger.info("PostgreSQL database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL: {str(e)}")
            raise
    
    async def _create_tables(self):
        """Create database tables if they don't exist"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    document_id VARCHAR(255) PRIMARY KEY,
                    filename VARCHAR(500) NOT NULL,
                    title VARCHAR(1000),
                    text TEXT,
                    user_id VARCHAR(255),
                    meta JSONB,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    detected_language VARCHAR(10),
                    chat_history JSONB DEFAULT '[]'::jsonb,
                    search_vector tsvector
                );
            """)
            
            # Create indexes for better performance
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents(user_id);
                CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at);
                CREATE INDEX IF NOT EXISTS idx_documents_search_vector ON documents USING GIN(search_vector);
            """)
            
            # Create trigger for search vector updates
            await conn.execute("""
                CREATE OR REPLACE FUNCTION update_search_vector() RETURNS trigger AS $$
                BEGIN
                    NEW.search_vector := to_tsvector('english', COALESCE(NEW.title, '') || ' ' || COALESCE(NEW.text, ''));
                    NEW.updated_at := NOW();
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
            """)
            
            await conn.execute("""
                DROP TRIGGER IF EXISTS update_documents_search_vector ON documents;
                CREATE TRIGGER update_documents_search_vector
                    BEFORE INSERT OR UPDATE ON documents
                    FOR EACH ROW EXECUTE FUNCTION update_search_vector();
            """)
    
    async def save_document(self, document: Document) -> bool:
        """Save document to PostgreSQL"""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO documents (
                        document_id, filename, title, text, user_id, meta,
                        detected_language, chat_history
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (document_id) DO UPDATE SET
                        filename = EXCLUDED.filename,
                        title = EXCLUDED.title,
                        text = EXCLUDED.text,
                        user_id = EXCLUDED.user_id,
                        meta = EXCLUDED.meta,
                        detected_language = EXCLUDED.detected_language,
                        chat_history = EXCLUDED.chat_history,
                        updated_at = NOW()
                """, 
                    document.document_id,
                    document.filename,
                    document.title,
                    document.text,
                    document.user_id,
                    json.dumps(document.meta) if document.meta else None,
                    document.detected_language,
                    json.dumps([msg.dict() for msg in document.chat_history])
                )
            return True
        except Exception as e:
            logger.error(f"Failed to save document to PostgreSQL: {str(e)}")
            return False
    
    async def get_document(self, document_id: str) -> Optional[Document]:
        """Get document from PostgreSQL"""
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM documents WHERE document_id = $1",
                    document_id
                )
                if row:
                    return self._row_to_document(row)
                return None
        except Exception as e:
            logger.error(f"Failed to get document from PostgreSQL: {str(e)}")
            return None
    
    async def list_documents(self, user_id: Optional[str] = None, limit: int = 100) -> List[Document]:
        """List documents from PostgreSQL"""
        try:
            async with self.pool.acquire() as conn:
                if user_id:
                    rows = await conn.fetch(
                        "SELECT * FROM documents WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2",
                        user_id, limit
                    )
                else:
                    rows = await conn.fetch(
                        "SELECT * FROM documents ORDER BY created_at DESC LIMIT $1",
                        limit
                    )
                return [self._row_to_document(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to list documents from PostgreSQL: {str(e)}")
            return []
    
    async def delete_document(self, document_id: str) -> bool:
        """Delete document from PostgreSQL"""
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute(
                    "DELETE FROM documents WHERE document_id = $1",
                    document_id
                )
                return result == "DELETE 1"
        except Exception as e:
            logger.error(f"Failed to delete document from PostgreSQL: {str(e)}")
            return False
    
    async def update_document(self, document: Document) -> bool:
        """Update document in PostgreSQL"""
        return await self.save_document(document)
    
    async def search_documents(self, query: str, user_id: Optional[str] = None) -> List[Document]:
        """Search documents using full-text search"""
        try:
            async with self.pool.acquire() as conn:
                if user_id:
                    rows = await conn.fetch("""
                        SELECT *, ts_rank(search_vector, plainto_tsquery('english', $1)) as rank
                        FROM documents 
                        WHERE search_vector @@ plainto_tsquery('english', $1) AND user_id = $2
                        ORDER BY rank DESC, created_at DESC
                        LIMIT 50
                    """, query, user_id)
                else:
                    rows = await conn.fetch("""
                        SELECT *, ts_rank(search_vector, plainto_tsquery('english', $1)) as rank
                        FROM documents 
                        WHERE search_vector @@ plainto_tsquery('english', $1)
                        ORDER BY rank DESC, created_at DESC
                        LIMIT 50
                    """, query)
                return [self._row_to_document(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to search documents in PostgreSQL: {str(e)}")
            return []
    
    def _row_to_document(self, row) -> Document:
        """Convert database row to Document object"""
        from models import ChatMessage
        
        chat_history = []
        if row['chat_history']:
            chat_data = json.loads(row['chat_history']) if isinstance(row['chat_history'], str) else row['chat_history']
            chat_history = [ChatMessage(**msg) for msg in chat_data]
        
        meta = json.loads(row['meta']) if row['meta'] and isinstance(row['meta'], str) else row['meta'] or {}
        
        return Document(
            document_id=row['document_id'],
            filename=row['filename'],
            title=row['title'],
            text=row['text'],
            user_id=row['user_id'],
            meta=meta,
            created_at=row['created_at'].isoformat() if row['created_at'] else None,
            updated_at=row['updated_at'].isoformat() if row['updated_at'] else None,
            chat_history=chat_history,
            detected_language=row['detected_language']
        )

class FirestoreDatabase(DatabaseInterface):
    """Firestore database implementation (fallback)"""
    
    def __init__(self):
        self.db = None
        
    async def initialize(self):
        """Initialize Firestore client"""
        try:
            self.db = firestore.Client()
            logger.info("Firestore database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Firestore: {str(e)}")
            raise
    
    async def save_document(self, document: Document) -> bool:
        """Save document to Firestore"""
        try:
            doc_ref = self.db.collection('documents').document(document.document_id)
            doc_data = document.dict()
            doc_data['created_at'] = firestore.SERVER_TIMESTAMP
            doc_data['updated_at'] = firestore.SERVER_TIMESTAMP
            doc_ref.set(doc_data, merge=True)
            return True
        except Exception as e:
            logger.error(f"Failed to save document to Firestore: {str(e)}")
            return False
    
    async def get_document(self, document_id: str) -> Optional[Document]:
        """Get document from Firestore"""
        try:
            doc_ref = self.db.collection('documents').document(document_id)
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                return Document(**data)
            return None
        except Exception as e:
            logger.error(f"Failed to get document from Firestore: {str(e)}")
            return None
    
    async def list_documents(self, user_id: Optional[str] = None, limit: int = 100) -> List[Document]:
        """List documents from Firestore"""
        try:
            query = self.db.collection('documents')
            if user_id:
                query = query.where('user_id', '==', user_id)
            query = query.order_by('created_at', direction=firestore.Query.DESCENDING).limit(limit)
            
            docs = query.stream()
            return [Document(**doc.to_dict()) for doc in docs]
        except Exception as e:
            logger.error(f"Failed to list documents from Firestore: {str(e)}")
            return []
    
    async def delete_document(self, document_id: str) -> bool:
        """Delete document from Firestore"""
        try:
            doc_ref = self.db.collection('documents').document(document_id)
            doc_ref.delete()
            return True
        except Exception as e:
            logger.error(f"Failed to delete document from Firestore: {str(e)}")
            return False
    
    async def update_document(self, document: Document) -> bool:
        """Update document in Firestore"""
        return await self.save_document(document)
    
    async def search_documents(self, query: str, user_id: Optional[str] = None) -> List[Document]:
        """Search documents (basic text matching for Firestore)"""
        try:
            # Basic search implementation - in production, use Algolia or similar
            docs = await self.list_documents(user_id)
            query_lower = query.lower()
            return [
                doc for doc in docs 
                if query_lower in (doc.title or "").lower() or query_lower in (doc.text or "").lower()
            ]
        except Exception as e:
            logger.error(f"Failed to search documents in Firestore: {str(e)}")
            return []

class DatabaseService:
    """Main database service with automatic fallback"""
    
    def __init__(self):
        self.primary_db = None
        self.fallback_db = None
        self.current_db = None
        
    async def initialize(self):
        """Initialize database with fallback strategy"""
        # Try PostgreSQL first
        if ASYNCPG_AVAILABLE and os.getenv("DATABASE_URL"):
            try:
                self.primary_db = PostgreSQLDatabase()
                await self.primary_db.initialize()
                self.current_db = self.primary_db
                logger.info("Using PostgreSQL as primary database")
                return
            except Exception as e:
                logger.warning(f"PostgreSQL initialization failed: {str(e)}")
        
        # Fallback to Firestore
        if FIRESTORE_AVAILABLE:
            try:
                self.fallback_db = FirestoreDatabase()
                await self.fallback_db.initialize()
                self.current_db = self.fallback_db
                logger.info("Using Firestore as fallback database")
                return
            except Exception as e:
                logger.warning(f"Firestore initialization failed: {str(e)}")
        
        # If both fail, raise error
        raise RuntimeError("No database backend available")
    
    async def save_document(self, document: Document) -> bool:
        """Save document using current database"""
        return await self.current_db.save_document(document)
    
    async def get_document(self, document_id: str) -> Optional[Document]:
        """Get document using current database"""
        return await self.current_db.get_document(document_id)
    
    async def list_documents(self, user_id: Optional[str] = None, limit: int = 100) -> List[Document]:
        """List documents using current database"""
        return await self.current_db.list_documents(user_id, limit)
    
    async def delete_document(self, document_id: str) -> bool:
        """Delete document using current database"""
        return await self.current_db.delete_document(document_id)
    
    async def update_document(self, document: Document) -> bool:
        """Update document using current database"""
        return await self.current_db.update_document(document)
    
    async def search_documents(self, query: str, user_id: Optional[str] = None) -> List[Document]:
        """Search documents using current database"""
        return await self.current_db.search_documents(query, user_id)
    
    def get_database_type(self) -> str:
        """Get current database type"""
        if isinstance(self.current_db, PostgreSQLDatabase):
            return "postgresql"
        elif isinstance(self.current_db, FirestoreDatabase):
            return "firestore"
        else:
            return "unknown"
