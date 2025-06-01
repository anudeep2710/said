import os
import json
import logging
from typing import Optional
from google.cloud import storage
from google.cloud.exceptions import NotFound, GoogleCloudError
from models import Document

# Configure logging
logger = logging.getLogger(__name__)

class StorageService:
    def __init__(self):
        """Initialize Google Cloud Storage service"""
        try:
            # Initialize GCS client
            self.client = storage.Client()

            # Get bucket name from environment
            self.bucket_name = os.getenv("GCS_BUCKET_NAME", "said-eb2f5-documents")

            # Get the bucket
            self.bucket = self.client.bucket(self.bucket_name)

            # Verify bucket exists
            if not self.bucket.exists():
                logger.warning(f"Bucket {self.bucket_name} does not exist. Creating it...")
                self.bucket.create(location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"))
                logger.info(f"Created bucket: {self.bucket_name}")

            logger.info(f"StorageService initialized with bucket: {self.bucket_name}")

        except Exception as e:
            logger.error(f"Failed to initialize StorageService: {str(e)}")
            raise Exception(f"Storage service initialization failed: {str(e)}")

    async def store_document(self, document: Document, file_path: str):
        """Store document in Google Cloud Storage"""
        try:
            # Upload the actual file
            file_blob_name = f"documents/{document.document_id}/{document.filename}"
            file_blob = self.bucket.blob(file_blob_name)

            # Upload file with proper content type
            content_type = self._get_content_type(document.filename)
            file_blob.upload_from_filename(file_path, content_type=content_type)

            logger.info(f"Uploaded file: {file_blob_name}")

            # Store metadata as JSON
            metadata_blob_name = f"documents/{document.document_id}/metadata.json"
            metadata_blob = self.bucket.blob(metadata_blob_name)

            # Convert document to JSON
            metadata_json = json.dumps(document.model_dump(), default=str, indent=2)
            metadata_blob.upload_from_string(metadata_json, content_type="application/json")

            logger.info(f"Stored document metadata: {metadata_blob_name}")

        except GoogleCloudError as e:
            logger.error(f"GCS error storing document {document.document_id}: {str(e)}")
            raise Exception(f"Error storing document in GCS: {str(e)}")
        except Exception as e:
            logger.error(f"Error storing document {document.document_id}: {str(e)}")
            raise Exception(f"Error storing document: {str(e)}")

    async def get_document(self, document_id: str) -> Optional[Document]:
        """Retrieve document metadata from Google Cloud Storage"""
        try:
            metadata_blob_name = f"documents/{document_id}/metadata.json"
            metadata_blob = self.bucket.blob(metadata_blob_name)

            if not metadata_blob.exists():
                logger.info(f"Document {document_id} not found")
                return None

            # Download and parse metadata
            metadata_json = metadata_blob.download_as_string()
            metadata = json.loads(metadata_json)

            logger.info(f"Retrieved document metadata: {document_id}")
            return Document(**metadata)

        except NotFound:
            logger.info(f"Document {document_id} not found")
            return None
        except GoogleCloudError as e:
            logger.error(f"GCS error retrieving document {document_id}: {str(e)}")
            raise Exception(f"Error retrieving document from GCS: {str(e)}")
        except Exception as e:
            logger.error(f"Error retrieving document {document_id}: {str(e)}")
            raise Exception(f"Error retrieving document: {str(e)}")

    async def delete_document(self, document_id: str):
        """Delete document and its metadata from Google Cloud Storage"""
        try:
            # List all blobs with the document prefix
            blobs = self.bucket.list_blobs(prefix=f"documents/{document_id}/")

            # Delete each blob
            deleted_count = 0
            for blob in blobs:
                blob.delete()
                deleted_count += 1
                logger.info(f"Deleted blob: {blob.name}")

            if deleted_count > 0:
                logger.info(f"Deleted {deleted_count} blobs for document {document_id}")
            else:
                logger.warning(f"No blobs found for document {document_id}")

        except GoogleCloudError as e:
            logger.error(f"GCS error deleting document {document_id}: {str(e)}")
            raise Exception(f"Error deleting document from GCS: {str(e)}")
        except Exception as e:
            logger.error(f"Error deleting document {document_id}: {str(e)}")
            raise Exception(f"Error deleting document: {str(e)}")

    async def get_document_text(self, document_id: str) -> Optional[str]:
        """Retrieve document text from storage"""
        try:
            document = await self.get_document(document_id)
            if not document:
                return None
            return document.text
        except Exception as e:
            raise Exception(f"Error retrieving document text: {str(e)}")

    async def list_documents(self) -> list:
        """List all documents in Google Cloud Storage"""
        try:
            documents = []
            blobs = self.bucket.list_blobs(prefix="documents/")

            # Group blobs by document ID
            doc_metadata = {}
            for blob in blobs:
                if blob.name.endswith("metadata.json"):
                    # Extract document ID from path: documents/{doc_id}/metadata.json
                    path_parts = blob.name.split("/")
                    if len(path_parts) >= 3:
                        doc_id = path_parts[1]
                        try:
                            metadata_json = blob.download_as_string()
                            metadata = json.loads(metadata_json)
                            doc_metadata[doc_id] = metadata
                        except Exception as e:
                            logger.warning(f"Error loading document {doc_id}: {str(e)}")
                            continue

            # Convert metadata to Document objects
            for doc_id, metadata in doc_metadata.items():
                try:
                    documents.append(Document(**metadata))
                except Exception as e:
                    logger.warning(f"Error creating Document object for {doc_id}: {str(e)}")
                    continue

            logger.info(f"Listed {len(documents)} documents from GCS")
            return documents

        except GoogleCloudError as e:
            logger.error(f"GCS error listing documents: {str(e)}")
            raise Exception(f"Error listing documents from GCS: {str(e)}")
        except Exception as e:
            logger.error(f"Error listing documents: {str(e)}")
            raise Exception(f"Error listing documents: {str(e)}")

    async def retrieve_document(self, document_id: str) -> Optional[Document]:
        """Retrieve document (alias for get_document for compatibility)"""
        return await self.get_document(document_id)

    def _get_content_type(self, filename: str) -> str:
        """Get content type based on file extension"""
        extension = filename.lower().split('.')[-1] if '.' in filename else ''

        content_types = {
            'pdf': 'application/pdf',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'doc': 'application/msword',
            'txt': 'text/plain',
            'json': 'application/json',
            'html': 'text/html',
            'htm': 'text/html'
        }

        return content_types.get(extension, 'application/octet-stream')