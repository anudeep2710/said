#!/usr/bin/env python3
"""
Secret management service using Google Secret Manager with fallback to environment variables
"""

import os
import json
import logging
from typing import Optional, Dict, Any
from functools import lru_cache

try:
    from google.cloud import secretmanager
    SECRET_MANAGER_AVAILABLE = True
except ImportError:
    SECRET_MANAGER_AVAILABLE = False
    secretmanager = None

logger = logging.getLogger(__name__)

class SecretManager:
    """Secure secret management with Google Secret Manager"""
    
    def __init__(self):
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "said-eb2f5")
        self.client = None
        self.use_secret_manager = SECRET_MANAGER_AVAILABLE and os.getenv("USE_SECRET_MANAGER", "true").lower() == "true"
        
        if self.use_secret_manager:
            try:
                self.client = secretmanager.SecretManagerServiceClient()
                logger.info("Google Secret Manager initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Secret Manager: {str(e)}")
                self.use_secret_manager = False
    
    @lru_cache(maxsize=128)
    def get_secret(self, secret_name: str, version: str = "latest") -> Optional[str]:
        """Get secret value with caching"""
        if self.use_secret_manager and self.client:
            try:
                name = f"projects/{self.project_id}/secrets/{secret_name}/versions/{version}"
                response = self.client.access_secret_version(request={"name": name})
                secret_value = response.payload.data.decode("UTF-8")
                logger.debug(f"Retrieved secret '{secret_name}' from Secret Manager")
                return secret_value
            except Exception as e:
                logger.warning(f"Failed to get secret '{secret_name}' from Secret Manager: {str(e)}")
        
        # Fallback to environment variable
        env_value = os.getenv(secret_name)
        if env_value:
            logger.debug(f"Retrieved secret '{secret_name}' from environment variable")
            return env_value
        
        logger.warning(f"Secret '{secret_name}' not found in Secret Manager or environment")
        return None
    
    def get_json_secret(self, secret_name: str, version: str = "latest") -> Optional[Dict[str, Any]]:
        """Get JSON secret and parse it"""
        secret_value = self.get_secret(secret_name, version)
        if secret_value:
            try:
                return json.loads(secret_value)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON secret '{secret_name}': {str(e)}")
        return None
    
    def create_secret(self, secret_name: str, secret_value: str) -> bool:
        """Create a new secret in Secret Manager"""
        if not self.use_secret_manager or not self.client:
            logger.warning("Secret Manager not available for creating secrets")
            return False
        
        try:
            parent = f"projects/{self.project_id}"
            
            # Create the secret
            secret = {"replication": {"automatic": {}}}
            response = self.client.create_secret(
                request={"parent": parent, "secret_id": secret_name, "secret": secret}
            )
            logger.info(f"Created secret: {response.name}")
            
            # Add the secret version
            response = self.client.add_secret_version(
                request={"parent": response.name, "payload": {"data": secret_value.encode("UTF-8")}}
            )
            logger.info(f"Added secret version: {response.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create secret '{secret_name}': {str(e)}")
            return False
    
    def update_secret(self, secret_name: str, secret_value: str) -> bool:
        """Update an existing secret in Secret Manager"""
        if not self.use_secret_manager or not self.client:
            logger.warning("Secret Manager not available for updating secrets")
            return False
        
        try:
            parent = f"projects/{self.project_id}/secrets/{secret_name}"
            response = self.client.add_secret_version(
                request={"parent": parent, "payload": {"data": secret_value.encode("UTF-8")}}
            )
            logger.info(f"Updated secret version: {response.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update secret '{secret_name}': {str(e)}")
            return False
    
    def delete_secret(self, secret_name: str) -> bool:
        """Delete a secret from Secret Manager"""
        if not self.use_secret_manager or not self.client:
            logger.warning("Secret Manager not available for deleting secrets")
            return False
        
        try:
            name = f"projects/{self.project_id}/secrets/{secret_name}"
            self.client.delete_secret(request={"name": name})
            logger.info(f"Deleted secret: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete secret '{secret_name}': {str(e)}")
            return False
    
    def list_secrets(self) -> list:
        """List all secrets in the project"""
        if not self.use_secret_manager or not self.client:
            logger.warning("Secret Manager not available for listing secrets")
            return []
        
        try:
            parent = f"projects/{self.project_id}"
            secrets = []
            for secret in self.client.list_secrets(request={"parent": parent}):
                secrets.append(secret.name.split("/")[-1])
            return secrets
            
        except Exception as e:
            logger.error(f"Failed to list secrets: {str(e)}")
            return []

# Global secret manager instance
secret_manager = SecretManager()

# Convenience functions for common secrets
def get_google_ai_api_key() -> Optional[str]:
    """Get Google AI API key"""
    return secret_manager.get_secret("GOOGLE_AI_API_KEY")

def get_database_url() -> Optional[str]:
    """Get database connection URL"""
    return secret_manager.get_secret("DATABASE_URL")

def get_firebase_service_account() -> Optional[Dict[str, Any]]:
    """Get Firebase service account JSON"""
    return secret_manager.get_json_secret("FIREBASE_SERVICE_ACCOUNT")

def get_openai_api_key() -> Optional[str]:
    """Get OpenAI API key (for future use)"""
    return secret_manager.get_secret("OPENAI_API_KEY")

def get_jwt_secret_key() -> Optional[str]:
    """Get JWT secret key"""
    return secret_manager.get_secret("JWT_SECRET_KEY")

def get_encryption_key() -> Optional[str]:
    """Get encryption key for sensitive data"""
    return secret_manager.get_secret("ENCRYPTION_KEY")

def get_webhook_secret() -> Optional[str]:
    """Get webhook secret for validating incoming webhooks"""
    return secret_manager.get_secret("WEBHOOK_SECRET")

def get_redis_url() -> Optional[str]:
    """Get Redis connection URL for caching"""
    return secret_manager.get_secret("REDIS_URL")

def get_smtp_config() -> Optional[Dict[str, Any]]:
    """Get SMTP configuration for email notifications"""
    return secret_manager.get_json_secret("SMTP_CONFIG")

def get_third_party_api_keys() -> Optional[Dict[str, str]]:
    """Get third-party API keys (Dropbox, Google Drive, etc.)"""
    return secret_manager.get_json_secret("THIRD_PARTY_API_KEYS")

# Secret validation functions
def validate_required_secrets() -> Dict[str, bool]:
    """Validate that all required secrets are available"""
    required_secrets = {
        "GOOGLE_AI_API_KEY": get_google_ai_api_key(),
        "FIREBASE_SERVICE_ACCOUNT": get_firebase_service_account(),
        "JWT_SECRET_KEY": get_jwt_secret_key(),
    }
    
    validation_results = {}
    for secret_name, secret_value in required_secrets.items():
        validation_results[secret_name] = secret_value is not None
        if not secret_value:
            logger.warning(f"Required secret '{secret_name}' is missing")
    
    return validation_results

def setup_development_secrets():
    """Set up development secrets if they don't exist"""
    import secrets
    import string
    
    # Generate JWT secret if not exists
    if not get_jwt_secret_key():
        jwt_secret = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(64))
        secret_manager.create_secret("JWT_SECRET_KEY", jwt_secret)
        logger.info("Created development JWT secret key")
    
    # Generate encryption key if not exists
    if not get_encryption_key():
        encryption_key = secrets.token_urlsafe(32)
        secret_manager.create_secret("ENCRYPTION_KEY", encryption_key)
        logger.info("Created development encryption key")
    
    # Generate webhook secret if not exists
    if not get_webhook_secret():
        webhook_secret = secrets.token_urlsafe(32)
        secret_manager.create_secret("WEBHOOK_SECRET", webhook_secret)
        logger.info("Created development webhook secret")

# Initialize secrets on import
if __name__ != "__main__":
    validation_results = validate_required_secrets()
    missing_secrets = [name for name, exists in validation_results.items() if not exists]
    
    if missing_secrets:
        logger.warning(f"Missing required secrets: {missing_secrets}")
        if os.getenv("ENVIRONMENT") == "development":
            setup_development_secrets()
    else:
        logger.info("All required secrets are available")
