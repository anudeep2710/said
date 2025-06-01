import os
import json
from typing import Optional, Dict, Any
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, auth
from fastapi import HTTPException, status
import logging

logger = logging.getLogger(__name__)

class FirebaseAuthService:
    """Service for Firebase Authentication integration"""

    def __init__(self):
        self.app = None
        self.initialize_firebase()

    def initialize_firebase(self):
        """Initialize Firebase Admin SDK"""
        try:
            # Check if Firebase is already initialized
            if not firebase_admin._apps:
                cred = None

                # 1. Try service account file first
                service_account_file = "firebase-service-account.json"
                if os.path.exists(service_account_file):
                    try:
                        cred = credentials.Certificate(service_account_file)
                        logger.info("Using Firebase service account file")
                    except Exception as e:
                        logger.warning(f"Failed to load service account file: {str(e)}")

                # 2. Try environment variable (JSON string)
                if not cred:
                    service_account_key = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY")
                    if service_account_key:
                        try:
                            service_account_info = json.loads(service_account_key)
                            cred = credentials.Certificate(service_account_info)
                            logger.info("Using Firebase service account from environment variable")
                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to parse service account JSON: {str(e)}")

                # 3. Try Application Default Credentials (for Google Cloud environments)
                if not cred:
                    try:
                        cred = credentials.ApplicationDefault()
                        logger.info("Using Application Default Credentials for Firebase")
                    except Exception as e:
                        logger.warning(f"Application Default Credentials failed: {str(e)}")

                # 4. Fall back to mock mode
                if not cred:
                    logger.warning("No Firebase credentials found. Running in mock mode.")
                    self.app = None
                    return

                # Initialize Firebase app
                self.app = firebase_admin.initialize_app(cred)
                logger.info("Firebase Admin SDK initialized successfully")
            else:
                self.app = firebase_admin.get_app()
                logger.info("Using existing Firebase Admin SDK instance")

        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {str(e)}")
            self.app = None

    async def verify_id_token(self, id_token: str) -> Dict[str, Any]:
        """
        Verify Firebase ID token and return user information

        Args:
            id_token: Firebase ID token from client

        Returns:
            Dict containing user information (uid, email, etc.)

        Raises:
            HTTPException: If token is invalid or verification fails
        """
        if not self.app:
            # Mock mode for development/testing
            return self._mock_verify_token(id_token)

        try:
            # Verify the ID token
            decoded_token = auth.verify_id_token(id_token)

            # Extract user information
            user_info = {
                "uid": decoded_token.get("uid"),
                "email": decoded_token.get("email"),
                "email_verified": decoded_token.get("email_verified", False),
                "name": decoded_token.get("name"),
                "picture": decoded_token.get("picture"),
                "firebase": {
                    "sign_in_provider": decoded_token.get("firebase", {}).get("sign_in_provider"),
                    "auth_time": decoded_token.get("auth_time"),
                    "exp": decoded_token.get("exp"),
                    "iat": decoded_token.get("iat")
                }
            }

            logger.info(f"Successfully verified token for user: {user_info['uid']}")
            return user_info

        except auth.InvalidIdTokenError:
            logger.error("Invalid Firebase ID token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )
        except auth.ExpiredIdTokenError:
            logger.error("Expired Firebase ID token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication token has expired"
            )
        except Exception as e:
            logger.error(f"Token verification failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed"
            )

    def _mock_verify_token(self, id_token: str) -> Dict[str, Any]:
        """
        Mock token verification for development/testing

        Args:
            id_token: Token to mock verify

        Returns:
            Mock user information
        """
        # Simple mock validation - in real development, you might want more sophisticated mocking
        if not id_token or id_token == "invalid_token":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )

        # Return production mock user data (for development/testing only)
        mock_user = {
            "uid": f"dev_user_{hash(id_token) % 10000}",  # Generate unique dev user ID
            "email": "developer@talktoyourdocument.com",
            "email_verified": True,
            "name": "Development User",
            "picture": None,
            "firebase": {
                "sign_in_provider": "development",
                "auth_time": int(datetime.utcnow().timestamp()),
                "exp": int(datetime.utcnow().timestamp()) + 3600,
                "iat": int(datetime.utcnow().timestamp())
            }
        }

        logger.info(f"Mock token verification for user: {mock_user['uid']}")
        return mock_user

    async def get_user_by_uid(self, uid: str) -> Optional[Dict[str, Any]]:
        """
        Get user information by UID

        Args:
            uid: Firebase user UID

        Returns:
            User information or None if not found
        """
        if not self.app:
            # Mock mode - return development user data
            return {
                "uid": uid,
                "email": "developer@talktoyourdocument.com",
                "email_verified": True,
                "display_name": "Development User"
            }

        try:
            user_record = auth.get_user(uid)
            return {
                "uid": user_record.uid,
                "email": user_record.email,
                "email_verified": user_record.email_verified,
                "display_name": user_record.display_name,
                "photo_url": user_record.photo_url,
                "disabled": user_record.disabled,
                "creation_time": user_record.user_metadata.creation_timestamp,
                "last_sign_in_time": user_record.user_metadata.last_sign_in_timestamp
            }
        except auth.UserNotFoundError:
            logger.error(f"User not found: {uid}")
            return None
        except Exception as e:
            logger.error(f"Error getting user {uid}: {str(e)}")
            return None

    def is_initialized(self) -> bool:
        """Check if Firebase is properly initialized"""
        return self.app is not None
