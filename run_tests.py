#!/usr/bin/env python3
"""
Test runner for TalkToYourDocument API
Runs unit tests, integration tests, and provides a comprehensive test report
"""

import subprocess
import sys
import os
import time
import argparse
from pathlib import Path

class TestRunner:
    """Test runner for the API"""
    
    def __init__(self, api_url="http://localhost:8000"):
        self.api_url = api_url
        self.test_results = {}
    
    def run_unit_tests(self):
        """Run unit tests using pytest"""
        print("🧪 Running Unit Tests...")
        print("=" * 50)
        
        try:
            # Run pytest with verbose output
            result = subprocess.run([
                sys.executable, "-m", "pytest", 
                "test_api.py", 
                "test_storage_service.py",
                "-v", 
                "--tb=short"
            ], capture_output=True, text=True, timeout=300)
            
            print(result.stdout)
            if result.stderr:
                print("STDERR:", result.stderr)
            
            self.test_results['unit_tests'] = {
                'success': result.returncode == 0,
                'output': result.stdout,
                'errors': result.stderr
            }
            
            if result.returncode == 0:
                print("✅ Unit tests passed!")
            else:
                print("❌ Unit tests failed!")
                
        except subprocess.TimeoutExpired:
            print("❌ Unit tests timed out!")
            self.test_results['unit_tests'] = {
                'success': False,
                'output': '',
                'errors': 'Tests timed out after 300 seconds'
            }
        except Exception as e:
            print(f"❌ Error running unit tests: {e}")
            self.test_results['unit_tests'] = {
                'success': False,
                'output': '',
                'errors': str(e)
            }
    
    def check_api_running(self):
        """Check if the API is running"""
        print(f"🔍 Checking if API is running at {self.api_url}...")
        
        try:
            import requests
            response = requests.get(f"{self.api_url}/", timeout=10)
            if response.status_code == 200:
                print("✅ API is running!")
                return True
            else:
                print(f"❌ API returned status code: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ API is not accessible: {e}")
            return False
    
    def start_api_server(self):
        """Start the API server for testing"""
        print("🚀 Starting API server...")
        
        try:
            # Check if main.py exists
            if not Path("main.py").exists():
                print("❌ main.py not found!")
                return None
            
            # Start the server
            process = subprocess.Popen([
                sys.executable, "-m", "uvicorn", 
                "main:app", 
                "--host", "0.0.0.0", 
                "--port", "8000",
                "--reload"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Wait a bit for the server to start
            time.sleep(5)
            
            # Check if it's running
            if self.check_api_running():
                return process
            else:
                process.terminate()
                return None
                
        except Exception as e:
            print(f"❌ Error starting API server: {e}")
            return None
    
    def run_integration_tests(self):
        """Run integration tests"""
        print("🌐 Running Integration Tests...")
        print("=" * 50)
        
        # Check if API is running
        api_running = self.check_api_running()
        server_process = None
        
        if not api_running:
            print("API not running, attempting to start it...")
            server_process = self.start_api_server()
            if not server_process:
                print("❌ Could not start API server for integration tests")
                self.test_results['integration_tests'] = {
                    'success': False,
                    'output': '',
                    'errors': 'Could not start API server'
                }
                return
        
        try:
            # Run integration tests
            result = subprocess.run([
                sys.executable, "test_integration.py", 
                "--url", self.api_url
            ], capture_output=True, text=True, timeout=600)
            
            print(result.stdout)
            if result.stderr:
                print("STDERR:", result.stderr)
            
            self.test_results['integration_tests'] = {
                'success': result.returncode == 0,
                'output': result.stdout,
                'errors': result.stderr
            }
            
            if result.returncode == 0:
                print("✅ Integration tests passed!")
            else:
                print("❌ Integration tests failed!")
                
        except subprocess.TimeoutExpired:
            print("❌ Integration tests timed out!")
            self.test_results['integration_tests'] = {
                'success': False,
                'output': '',
                'errors': 'Tests timed out after 600 seconds'
            }
        except Exception as e:
            print(f"❌ Error running integration tests: {e}")
            self.test_results['integration_tests'] = {
                'success': False,
                'output': '',
                'errors': str(e)
            }
        finally:
            # Clean up server process if we started it
            if server_process:
                print("🛑 Stopping test server...")
                server_process.terminate()
                try:
                    server_process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server_process.kill()
    
    def run_simple_api_test(self):
        """Run a simple API test without the full integration suite"""
        print("🔧 Running Simple API Test...")
        print("=" * 50)
        
        try:
            import requests
            import tempfile
            
            # Test health endpoint
            print("Testing health endpoint...")
            response = requests.get(f"{self.api_url}/")
            assert response.status_code == 200
            print("✅ Health check passed")
            
            # Test document upload (if possible)
            print("Testing document upload...")
            test_content = "This is a test document for API testing."
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(test_content)
                temp_file_path = f.name
            
            try:
                with open(temp_file_path, 'rb') as f:
                    files = {'file': ('test.txt', f, 'text/plain')}
                    response = requests.post(f"{self.api_url}/upload", files=files)
                
                if response.status_code == 200:
                    print("✅ Document upload passed")
                    doc_data = response.json()
                    doc_id = doc_data.get('document_id')
                    
                    # Test document listing
                    print("Testing document listing...")
                    response = requests.get(f"{self.api_url}/documents")
                    if response.status_code in [200, 401]:  # 401 is expected if auth required
                        print("✅ Document listing endpoint accessible")
                    
                elif response.status_code == 401:
                    print("ℹ️ Upload requires authentication (expected)")
                else:
                    print(f"⚠️ Upload failed: {response.status_code}")
                    
            finally:
                os.unlink(temp_file_path)
            
            self.test_results['simple_api_test'] = {
                'success': True,
                'output': 'Simple API test completed',
                'errors': ''
            }
            
        except Exception as e:
            print(f"❌ Simple API test failed: {e}")
            self.test_results['simple_api_test'] = {
                'success': False,
                'output': '',
                'errors': str(e)
            }
    
    def generate_report(self):
        """Generate a comprehensive test report"""
        print("\n" + "=" * 60)
        print("📊 TEST REPORT")
        print("=" * 60)
        
        total_suites = len(self.test_results)
        passed_suites = sum(1 for result in self.test_results.values() if result['success'])
        
        print(f"Test Suites Run: {total_suites}")
        print(f"Passed: {passed_suites}")
        print(f"Failed: {total_suites - passed_suites}")
        
        for suite_name, result in self.test_results.items():
            status = "✅ PASSED" if result['success'] else "❌ FAILED"
            print(f"\n{suite_name}: {status}")
            if not result['success'] and result['errors']:
                print(f"  Error: {result['errors']}")
        
        print("\n" + "=" * 60)
        
        if passed_suites == total_suites:
            print("🎉 All test suites passed!")
            return True
        else:
            print("⚠️ Some test suites failed!")
            return False
    
    def run_all_tests(self, skip_integration=False):
        """Run all available tests"""
        print("🚀 Starting TalkToYourDocument API Test Suite")
        print(f"🌐 API URL: {self.api_url}")
        print("=" * 60)
        
        # Run unit tests
        self.run_unit_tests()
        
        # Run integration tests or simple API test
        if not skip_integration:
            if self.check_api_running():
                self.run_integration_tests()
            else:
                print("⚠️ API not running, running simple test instead")
                self.run_simple_api_test()
        else:
            print("⏭️ Skipping integration tests")
        
        # Generate report
        return self.generate_report()

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Run TalkToYourDocument API tests')
    parser.add_argument('--url', default='http://localhost:8000', 
                       help='API URL (default: http://localhost:8000)')
    parser.add_argument('--skip-integration', action='store_true',
                       help='Skip integration tests')
    parser.add_argument('--unit-only', action='store_true',
                       help='Run only unit tests')
    
    args = parser.parse_args()
    
    runner = TestRunner(args.url)
    
    if args.unit_only:
        runner.run_unit_tests()
        success = runner.test_results.get('unit_tests', {}).get('success', False)
    else:
        success = runner.run_all_tests(args.skip_integration)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
