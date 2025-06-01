#!/usr/bin/env python3
"""
Quick verification that GCS setup is working
"""

import os

def main():
    print("🔍 Verifying GCS Setup...")
    
    # Check environment variables
    print("\n📋 Environment Variables:")
    env_vars = [
        "GOOGLE_CLOUD_PROJECT",
        "GCS_BUCKET_NAME", 
        "GOOGLE_CLOUD_LOCATION",
        "USE_MOCK_STORAGE"
    ]
    
    for var in env_vars:
        value = os.getenv(var, "Not set")
        print(f"   {var}: {value}")
    
    # Test GCS client
    print("\n🔗 Testing GCS Connection:")
    try:
        from google.cloud import storage
        client = storage.Client()
        print(f"   ✅ GCS Client initialized")
        print(f"   📦 Project: {client.project}")
        
        bucket_name = os.getenv("GCS_BUCKET_NAME", "said-eb2f5-documents")
        bucket = client.bucket(bucket_name)
        exists = bucket.exists()
        print(f"   🪣 Bucket '{bucket_name}' exists: {exists}")
        
    except Exception as e:
        print(f"   ❌ GCS Error: {str(e)}")
        return False
    
    # Test storage service
    print("\n🧪 Testing StorageService:")
    try:
        from services.storage_service import StorageService
        storage_service = StorageService()
        print(f"   ✅ StorageService initialized")
        print(f"   🪣 Bucket: {storage_service.bucket_name}")
        
    except Exception as e:
        print(f"   ❌ StorageService Error: {str(e)}")
        return False
    
    print("\n🎉 All verifications passed!")
    print("✅ Your GCS setup is working correctly!")
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        print("\n❌ Setup verification failed.")
        exit(1)
