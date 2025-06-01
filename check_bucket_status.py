#!/usr/bin/env python3
"""
Google Cloud Storage Bucket Status Checker
Checks if your bucket exists and is properly configured
"""

import os
import sys
from google.cloud import storage
from google.cloud.exceptions import NotFound, Forbidden
import json

class BucketStatusChecker:
    """Check Google Cloud Storage bucket status"""
    
    def __init__(self):
        self.project_id = "said-eb2f5"
        self.bucket_name = "said-eb2f5-documents"
        self.location = "us-central1"
        self.client = None
    
    def check_authentication(self):
        """Check if we can authenticate with Google Cloud"""
        print("🔐 Checking Google Cloud Authentication...")
        
        try:
            # Try to initialize the storage client
            self.client = storage.Client(project=self.project_id)
            print(f"✅ Successfully authenticated with project: {self.client.project}")
            return True
        except Exception as e:
            print(f"❌ Authentication failed: {e}")
            print("💡 Make sure you have:")
            print("   - Service account key file (firebase-service-account.json)")
            print("   - Or GOOGLE_APPLICATION_CREDENTIALS environment variable set")
            print("   - Or gcloud auth application-default login")
            return False
    
    def check_bucket_exists(self):
        """Check if the bucket exists"""
        print(f"\n🪣 Checking if bucket '{self.bucket_name}' exists...")
        
        try:
            bucket = self.client.bucket(self.bucket_name)
            if bucket.exists():
                print(f"✅ Bucket '{self.bucket_name}' exists!")
                return bucket
            else:
                print(f"❌ Bucket '{self.bucket_name}' does not exist")
                return None
        except Forbidden as e:
            print(f"❌ Access denied to bucket '{self.bucket_name}': {e}")
            print("💡 Check your permissions for this bucket")
            return None
        except Exception as e:
            print(f"❌ Error checking bucket: {e}")
            return None
    
    def get_bucket_info(self, bucket):
        """Get detailed bucket information"""
        print(f"\n📋 Bucket Information:")
        
        try:
            # Reload bucket to get latest info
            bucket.reload()
            
            print(f"   Name: {bucket.name}")
            print(f"   Location: {bucket.location}")
            print(f"   Storage Class: {bucket.storage_class}")
            print(f"   Created: {bucket.time_created}")
            print(f"   Project: {bucket.project_number}")
            
            # Check versioning
            versioning = bucket.versioning_enabled
            print(f"   Versioning: {'Enabled' if versioning else 'Disabled'}")
            
            # Check public access
            try:
                iam_policy = bucket.get_iam_policy()
                public_access = any(
                    'allUsers' in binding.get('members', []) or 
                    'allAuthenticatedUsers' in binding.get('members', [])
                    for binding in iam_policy.bindings
                )
                print(f"   Public Access: {'Yes' if public_access else 'No'}")
            except:
                print(f"   Public Access: Unable to check")
            
            return True
        except Exception as e:
            print(f"❌ Error getting bucket info: {e}")
            return False
    
    def test_bucket_operations(self, bucket):
        """Test basic bucket operations"""
        print(f"\n🧪 Testing Bucket Operations...")
        
        try:
            # Test listing objects
            blobs = list(bucket.list_blobs(max_results=5))
            print(f"✅ Can list objects: {len(blobs)} objects found")
            
            # Test creating a test file
            test_blob_name = "test/connection_test.txt"
            test_content = f"Connection test from Python at {os.environ.get('COMPUTERNAME', 'unknown')}"
            
            blob = bucket.blob(test_blob_name)
            blob.upload_from_string(test_content, content_type='text/plain')
            print(f"✅ Can upload files: Created {test_blob_name}")
            
            # Test reading the file
            downloaded_content = blob.download_as_string().decode('utf-8')
            if downloaded_content == test_content:
                print(f"✅ Can download files: Content matches")
            else:
                print(f"⚠️ Download content mismatch")
            
            # Test deleting the file
            blob.delete()
            print(f"✅ Can delete files: Removed {test_blob_name}")
            
            return True
            
        except Exception as e:
            print(f"❌ Bucket operations failed: {e}")
            return False
    
    def create_bucket_if_needed(self):
        """Create bucket if it doesn't exist"""
        print(f"\n🏗️ Creating bucket '{self.bucket_name}'...")
        
        try:
            bucket = self.client.bucket(self.bucket_name)
            bucket.storage_class = "STANDARD"
            bucket.location = self.location
            
            bucket = self.client.create_bucket(bucket, location=self.location)
            print(f"✅ Successfully created bucket '{self.bucket_name}'")
            print(f"   Location: {self.location}")
            print(f"   Storage Class: STANDARD")
            
            return bucket
            
        except Exception as e:
            print(f"❌ Failed to create bucket: {e}")
            print("💡 You may need to:")
            print("   - Enable the Cloud Storage API")
            print("   - Check your project permissions")
            print("   - Ensure the bucket name is globally unique")
            return None
    
    def check_api_enabled(self):
        """Check if required APIs are enabled"""
        print(f"\n🔧 Checking Required APIs...")
        
        try:
            # Try to list buckets to check if Storage API is enabled
            buckets = list(self.client.list_buckets())
            print(f"✅ Cloud Storage API is enabled ({len(buckets)} buckets in project)")
            return True
        except Exception as e:
            print(f"❌ Cloud Storage API may not be enabled: {e}")
            print("💡 Enable it with: gcloud services enable storage.googleapis.com")
            return False
    
    def run_full_check(self):
        """Run complete bucket status check"""
        print("🪣 Google Cloud Storage Bucket Status Check")
        print("=" * 50)
        print(f"Project ID: {self.project_id}")
        print(f"Bucket Name: {self.bucket_name}")
        print(f"Expected Location: {self.location}")
        print("=" * 50)
        
        # Check authentication
        if not self.check_authentication():
            return False
        
        # Check if APIs are enabled
        if not self.check_api_enabled():
            return False
        
        # Check if bucket exists
        bucket = self.check_bucket_exists()
        
        if bucket:
            # Bucket exists, get info and test operations
            if self.get_bucket_info(bucket):
                if self.test_bucket_operations(bucket):
                    print("\n🎉 Bucket Status: FULLY OPERATIONAL")
                    print("✅ Your Google Cloud Storage bucket is ready to use!")
                    return True
                else:
                    print("\n⚠️ Bucket Status: EXISTS BUT OPERATIONS FAILED")
                    return False
            else:
                print("\n⚠️ Bucket Status: EXISTS BUT INFO UNAVAILABLE")
                return False
        else:
            # Bucket doesn't exist, try to create it
            print("\n🏗️ Bucket doesn't exist. Attempting to create...")
            bucket = self.create_bucket_if_needed()
            
            if bucket:
                print("\n🎉 Bucket Status: CREATED AND OPERATIONAL")
                print("✅ Your Google Cloud Storage bucket has been created!")
                return True
            else:
                print("\n❌ Bucket Status: CREATION FAILED")
                return False
    
    def generate_setup_instructions(self):
        """Generate setup instructions if bucket setup fails"""
        print("\n📋 Manual Bucket Setup Instructions:")
        print("=" * 40)
        print("1. Enable Cloud Storage API:")
        print("   gcloud services enable storage.googleapis.com")
        print()
        print("2. Create the bucket manually:")
        print(f"   gsutil mb -p {self.project_id} -c STANDARD -l {self.location} gs://{self.bucket_name}/")
        print()
        print("3. Set bucket permissions (if needed):")
        print(f"   gsutil iam ch serviceAccount:firebase-adminsdk-fbsvc@{self.project_id}.iam.gserviceaccount.com:objectAdmin gs://{self.bucket_name}")
        print()
        print("4. Test bucket access:")
        print(f"   gsutil ls gs://{self.bucket_name}/")

def main():
    """Main function"""
    checker = BucketStatusChecker()
    
    success = checker.run_full_check()
    
    if not success:
        checker.generate_setup_instructions()
        print("\n❌ Bucket setup incomplete. Please follow the instructions above.")
        sys.exit(1)
    else:
        print("\n🚀 Ready for Production!")
        print("Your bucket is properly configured for the TalkToYourDocument API.")

if __name__ == "__main__":
    main()
