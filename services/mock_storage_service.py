import os
import json
import shutil
from datetime import datetime
from typing import List, Optional
from models import Document

class MockStorageService:
    """Mock storage service for local testing without Google Cloud dependencies"""

    def __init__(self):
        self.storage_dir = "mock_storage"
        self.metadata_dir = os.path.join(self.storage_dir, "metadata")
        self.documents_dir = os.path.join(self.storage_dir, "documents")

        # Create necessary directories
        os.makedirs(self.metadata_dir, exist_ok=True)
        os.makedirs(self.documents_dir, exist_ok=True)

    async def store_document(self, document: Document, file_path: str) -> None:
        """Store document and its metadata"""
        try:
            # Copy document file
            doc_path = os.path.join(self.documents_dir, f"{document.document_id}_{document.filename}")
            shutil.copy2(file_path, doc_path)

            # Store metadata
            metadata_path = os.path.join(self.metadata_dir, f"{document.document_id}.json")
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(document.model_dump(), f, ensure_ascii=False, indent=2, default=str)

        except Exception as e:
            raise Exception(f"Error storing document: {str(e)}")

    async def retrieve_document(self, document_id: str) -> Optional[Document]:
        """Retrieve document metadata"""
        try:
            metadata_path = os.path.join(self.metadata_dir, f"{document_id}.json")
            if not os.path.exists(metadata_path):
                return None

            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
                return Document(**metadata)

        except Exception as e:
            raise Exception(f"Error retrieving document: {str(e)}")

    async def delete_document(self, document_id: str) -> None:
        """Delete document and its metadata"""
        try:
            # Delete metadata
            metadata_path = os.path.join(self.metadata_dir, f"{document_id}.json")
            if os.path.exists(metadata_path):
                os.remove(metadata_path)

            # Delete document file
            doc = await self.retrieve_document(document_id)
            if doc:
                doc_path = os.path.join(self.documents_dir, f"{document_id}_{doc.filename}")
                if os.path.exists(doc_path):
                    os.remove(doc_path)

        except Exception as e:
            raise Exception(f"Error deleting document: {str(e)}")

    async def list_documents(self) -> List[Document]:
        """List all documents"""
        try:
            documents = []
            for filename in os.listdir(self.metadata_dir):
                if filename.endswith(".json"):
                    document_id = filename[:-5]  # Remove .json extension
                    doc = await self.retrieve_document(document_id)
                    if doc:
                        documents.append(doc)
            return documents

        except Exception as e:
            raise Exception(f"Error listing documents: {str(e)}")

    async def get_document_content(self, document_id: str) -> str:
        """Get document content"""
        try:
            doc = await self.retrieve_document(document_id)
            if not doc:
                raise Exception(f"Document {document_id} not found")

            doc_path = os.path.join(self.documents_dir, f"{document_id}_{doc.filename}")
            if not os.path.exists(doc_path):
                raise Exception(f"Document file not found: {doc_path}")

            with open(doc_path, "r", encoding="utf-8") as f:
                return f.read()

        except Exception as e:
            raise Exception(f"Error getting document content: {str(e)}")