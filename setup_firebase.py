#!/usr/bin/env python3
"""
Firebase Setup and Configuration Script for TalkToYourDocument API
Helps configure Firebase authentication and test the setup
"""

import os
import json
import sys
import subprocess
from pathlib import Path
import requests
from typing import Dict, Any, Optional

class FirebaseSetup:
    """Firebase setup and configuration helper"""
    
    def __init__(self):
        self.project_id = "said-eb2f5"
        self.project_number = "1026546995867"
        self.api_key = "AIzaSyD5Nm1AklgfxFBz3aNmHHohVO-PRPS1nKs"
        self.android_package = "com.example.said_app"
        self.service_account_email = "firebase-adminsdk-fbsvc@said-eb2f5.iam.gserviceaccount.com"
    
    def check_firebase_cli(self):
        """Check if Firebase CLI is installed"""
        try:
            result = subprocess.run(['firebase', '--version'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✅ Firebase CLI installed: {result.stdout.strip()}")
                return True
            else:
                print("❌ Firebase CLI not found")
                return False
        except FileNotFoundError:
            print("❌ Firebase CLI not installed")
            print("📥 Install it with: npm install -g firebase-tools")
            return False
    
    def check_gcloud_cli(self):
        """Check if Google Cloud CLI is installed"""
        try:
            result = subprocess.run(['gcloud', '--version'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✅ Google Cloud CLI installed")
                return True
            else:
                print("❌ Google Cloud CLI not found")
                return False
        except FileNotFoundError:
            print("❌ Google Cloud CLI not installed")
            print("📥 Install it from: https://cloud.google.com/sdk/docs/install")
            return False
    
    def check_firebase_config(self):
        """Check Firebase configuration files"""
        print("\n🔍 Checking Firebase Configuration...")
        
        # Check Flutter config
        flutter_config = Path("flutter_firebase_config.json")
        if flutter_config.exists():
            print("✅ Flutter Firebase config found")
            with open(flutter_config) as f:
                config = json.load(f)
                if config.get("project_info", {}).get("project_id") == self.project_id:
                    print(f"✅ Project ID matches: {self.project_id}")
                else:
                    print(f"⚠️ Project ID mismatch in Flutter config")
        else:
            print("❌ Flutter Firebase config not found")
        
        # Check service account key
        service_account_files = [
            "firebase-service-account.json",
            "service-account-key.json",
            f"{self.project_id}-service-account.json"
        ]
        
        service_account_found = False
        for file_path in service_account_files:
            if Path(file_path).exists():
                print(f"✅ Service account key found: {file_path}")
                service_account_found = True
                break
        
        if not service_account_found:
            print("❌ No service account key file found")
            print("💡 Expected files: " + ", ".join(service_account_files))
        
        # Check environment variables
        env_vars = {
            "FIREBASE_SERVICE_ACCOUNT_KEY": "Firebase service account JSON",
            "GOOGLE_APPLICATION_CREDENTIALS": "Path to service account file",
            "FIREBASE_PROJECT_ID": "Firebase project ID"
        }
        
        print("\n🔍 Checking Environment Variables...")
        for var, description in env_vars.items():
            value = os.getenv(var)
            if value:
                print(f"✅ {var}: Set ({description})")
            else:
                print(f"❌ {var}: Not set ({description})")
    
    def test_firebase_connection(self):
        """Test Firebase connection"""
        print("\n🧪 Testing Firebase Connection...")
        
        try:
            from services.firebase_auth_service import FirebaseAuthService
            
            # Initialize Firebase service
            firebase_service = FirebaseAuthService()
            
            if firebase_service.is_initialized():
                print("✅ Firebase Admin SDK initialized successfully")
                
                # Test token verification in mock mode
                try:
                    import asyncio
                    test_token = "test_token_123"
                    user_info = asyncio.run(firebase_service.verify_id_token(test_token))
                    print("✅ Token verification working (mock mode)")
                    print(f"   Mock user: {user_info.get('email', 'N/A')}")
                except Exception as e:
                    print(f"❌ Token verification failed: {e}")
            else:
                print("⚠️ Firebase running in mock mode (no credentials)")
                print("   This is fine for development and testing")
                
        except ImportError as e:
            print(f"❌ Failed to import Firebase service: {e}")
        except Exception as e:
            print(f"❌ Firebase connection test failed: {e}")
    
    def test_api_endpoints(self):
        """Test API endpoints with Firebase authentication"""
        print("\n🌐 Testing API Endpoints...")
        
        base_url = "http://localhost:8000"
        
        # Test health endpoint
        try:
            response = requests.get(f"{base_url}/", timeout=5)
            if response.status_code == 200:
                print("✅ Health endpoint working")
            else:
                print(f"❌ Health endpoint failed: {response.status_code}")
        except requests.exceptions.RequestException:
            print("❌ API server not running or not accessible")
            print("💡 Start the server with: python -m uvicorn main:app --reload")
            return
        
        # Test protected endpoint without auth
        try:
            response = requests.get(f"{base_url}/auth/me", timeout=5)
            if response.status_code == 401:
                print("✅ Protected endpoint correctly requires authentication")
            else:
                print(f"⚠️ Protected endpoint unexpected response: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"❌ Protected endpoint test failed: {e}")
        
        # Test protected endpoint with mock token
        try:
            headers = {"Authorization": "Bearer test_token_123"}
            response = requests.get(f"{base_url}/auth/me", headers=headers, timeout=5)
            if response.status_code == 200:
                print("✅ Mock authentication working")
                data = response.json()
                print(f"   User: {data.get('email', 'N/A')}")
            elif response.status_code == 401:
                print("⚠️ Mock authentication not working (expected in production)")
            else:
                print(f"❌ Unexpected response: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"❌ Mock auth test failed: {e}")
    
    def generate_service_account_instructions(self):
        """Generate instructions for setting up service account"""
        print("\n📋 Service Account Setup Instructions:")
        print("=" * 50)
        print(f"1. Go to Firebase Console: https://console.firebase.google.com/project/{self.project_id}")
        print("2. Click on 'Project Settings' (gear icon)")
        print("3. Go to 'Service accounts' tab")
        print("4. Click 'Generate new private key'")
        print("5. Save the JSON file as 'firebase-service-account.json' in your project root")
        print("\nAlternatively, set environment variable:")
        print("export FIREBASE_SERVICE_ACCOUNT_KEY='<paste-json-content-here>'")
        print("\nFor Google Cloud deployment:")
        print(f"gcloud iam service-accounts keys create firebase-service-account.json \\")
        print(f"  --iam-account={self.service_account_email}")
    
    def generate_flutter_config(self):
        """Generate Flutter Firebase configuration"""
        print("\n📱 Flutter Firebase Configuration:")
        print("=" * 50)
        
        flutter_config = {
            "project_info": {
                "project_number": self.project_number,
                "project_id": self.project_id,
                "storage_bucket": f"{self.project_id}.firebasestorage.app"
            },
            "client": [{
                "client_info": {
                    "mobilesdk_app_id": f"1:{self.project_number}:android:bfbde1b0537723a9246c3e",
                    "android_client_info": {
                        "package_name": self.android_package
                    }
                },
                "api_key": [{
                    "current_key": self.api_key
                }],
                "services": {
                    "appinvite_service": {
                        "other_platform_oauth_client": [{
                            "client_id": f"{self.project_number}-cflbvuacgl2r4dq1o4cmmkf6dfaidl7e.apps.googleusercontent.com",
                            "client_type": 3
                        }]
                    }
                }
            }],
            "configuration_version": "1"
        }
        
        config_file = "flutter_firebase_config.json"
        with open(config_file, 'w') as f:
            json.dump(flutter_config, f, indent=2)
        
        print(f"✅ Generated {config_file}")
        print("\nFor Flutter app, also add to android/app/google-services.json")
    
    def run_full_setup_check(self):
        """Run complete Firebase setup check"""
        print("🔥 Firebase Setup Check for TalkToYourDocument API")
        print("=" * 60)
        
        # Check CLI tools
        print("\n🛠️ Checking CLI Tools...")
        firebase_cli = self.check_firebase_cli()
        gcloud_cli = self.check_gcloud_cli()
        
        # Check configuration
        self.check_firebase_config()
        
        # Test connection
        self.test_firebase_connection()
        
        # Test API
        self.test_api_endpoints()
        
        # Generate instructions if needed
        if not any(Path(f).exists() for f in ["firebase-service-account.json", "service-account-key.json"]):
            self.generate_service_account_instructions()
        
        # Summary
        print("\n📊 Setup Summary:")
        print("=" * 30)
        print(f"Project ID: {self.project_id}")
        print(f"Project Number: {self.project_number}")
        print(f"Android Package: {self.android_package}")
        print(f"Service Account: {self.service_account_email}")
        
        print("\n🚀 Next Steps:")
        print("1. Ensure service account key is properly configured")
        print("2. Test the API with: python test_firebase_integration.py")
        print("3. Deploy to Google Cloud Run for production")
        print("4. Configure Flutter app with Firebase")

def main():
    """Main function"""
    setup = FirebaseSetup()
    setup.run_full_setup_check()

if __name__ == "__main__":
    main()
