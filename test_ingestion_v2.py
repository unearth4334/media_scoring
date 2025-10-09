#!/usr/bin/env python3
"""
Test script for the new Data Ingestion Tool v2 workflow.
"""

import asyncio
import json
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import requests
from app.services.nsfw_detection import is_nsfw_detection_available


class IngestionWorkflowTest:
    """Test the complete ingestion workflow."""
    
    def __init__(self, base_url="http://127.0.0.1:7864"):
        self.base_url = base_url
        
    def test_nsfw_detection_availability(self):
        """Test NSFW detection availability."""
        print("🔞 Testing NSFW Detection Availability...")
        
        available = is_nsfw_detection_available()
        print(f"   NSFW Detection Available: {'✅ Yes' if available else '❌ No'}")
        
        if not available:
            print("   ⚠️  Note: NSFW detection requires 'timm' and 'torch' packages")
            print("   Install with: pip install timm torch")
        
        return available
    
    def test_directory_listing(self):
        """Test the directory listing API."""
        print("📁 Testing Directory Listing API...")
        
        try:
            response = requests.get(f"{self.base_url}/api/ingest/directories")
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Directory listing works")
                print(f"   Current path: {data.get('path', 'Unknown')}")
                print(f"   Directories found: {len(data.get('directories', []))}")
                print(f"   File summary: {data.get('file_summary', 'No files')}")
                return True
            else:
                print(f"   ❌ Directory listing failed: HTTP {response.status_code}")
                return False
        except Exception as e:
            print(f"   ❌ Directory listing error: {e}")
            return False
    
    def test_processing_workflow(self, test_directory="./media"):
        """Test the complete processing workflow."""
        print("🔄 Testing Processing Workflow...")
        
        # Test parameters
        parameters = {
            "directory": test_directory,
            "pattern": "*.mp4|*.png|*.jpg",
            "enable_nsfw_detection": True,
            "nsfw_threshold": 0.5,
            "extract_metadata": True,
            "extract_keywords": True,
            "import_scores": True,
            "max_files": 5  # Limit for testing
        }
        
        try:
            # Start processing
            print("   📤 Starting processing...")
            response = requests.post(
                f"{self.base_url}/api/ingest/process",
                json={"parameters": parameters},
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"   ❌ Failed to start processing: HTTP {response.status_code}")
                print(f"   Error: {response.text}")
                return False
            
            result = response.json()
            session_id = result["session_id"]
            total_files = result["total_files"]
            
            print(f"   ✅ Processing started")
            print(f"   Session ID: {session_id}")  
            print(f"   Total files: {total_files}")
            
            # Poll for completion
            print("   ⏳ Waiting for processing to complete...")
            max_wait = 300  # 5 minutes
            wait_time = 0
            
            while wait_time < max_wait:
                time.sleep(2)
                wait_time += 2
                
                status_response = requests.get(
                    f"{self.base_url}/api/ingest/status/{session_id}",
                    timeout=10
                )
                
                if status_response.status_code != 200:
                    print(f"   ❌ Failed to get status: HTTP {status_response.status_code}")
                    return False
                
                status = status_response.json()
                progress = status.get("progress", 0)
                current_file = status.get("current_file", "")
                
                print(f"   📊 Progress: {progress}% - {current_file}")
                
                if status["status"] == "completed":
                    print("   ✅ Processing completed successfully!")
                    
                    # Print final stats
                    stats = status.get("stats", {})
                    print(f"   📈 Final Stats:")
                    print(f"      Processed: {stats.get('processed_files', 0)}")
                    print(f"      Metadata: {stats.get('metadata_extracted', 0)}")
                    print(f"      Keywords: {stats.get('keywords_added', 0)}")
                    print(f"      Scores: {stats.get('scores_imported', 0)}")
                    print(f"      NSFW: {stats.get('nsfw_detected', 0)}")
                    print(f"      Errors: {stats.get('errors', 0)}")
                    
                    return session_id
                    
                elif status["status"] == "error":
                    print(f"   ❌ Processing failed: {status.get('error', 'Unknown error')}")
                    return False
            
            print("   ⏰ Processing timed out")
            return False
            
        except Exception as e:
            print(f"   ❌ Processing workflow error: {e}")
            return False
    
    def test_preview_report(self, session_id):
        """Test the preview report generation."""
        print("📄 Testing Preview Report...")
        
        try:
            response = requests.get(
                f"{self.base_url}/api/ingest/report/{session_id}",
                timeout=30
            )
            
            if response.status_code == 200:
                print("   ✅ Preview report generated successfully")
                
                # Check if it's HTML content
                content_type = response.headers.get('content-type', '')
                if 'text/html' in content_type:
                    html_content = response.text
                    if len(html_content) > 1000:  # Reasonable HTML size
                        print(f"   📊 Report size: {len(html_content)} characters")
                        
                        # Check for key sections
                        if "Processing Summary" in html_content:
                            print("   ✅ Report contains processing summary")
                        if "Sample Files Preview" in html_content:
                            print("   ✅ Report contains file preview")
                        if "NSFW Analysis" in html_content:
                            print("   ✅ Report contains NSFW analysis")
                            
                        return True
                    else:
                        print("   ❌ Report seems too small")
                        return False
                else:
                    print(f"   ❌ Unexpected content type: {content_type}")
                    return False
            else:
                print(f"   ❌ Failed to get report: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            print(f"   ❌ Preview report error: {e}")
            return False
    
    def test_cleanup(self, session_id):
        """Test session cleanup."""
        print("🧹 Testing Session Cleanup...")
        
        try:
            response = requests.delete(
                f"{self.base_url}/api/ingest/session/{session_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                print("   ✅ Session cleaned up successfully")
                return True
            else:
                print(f"   ❌ Failed to cleanup session: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            print(f"   ❌ Cleanup error: {e}")
            return False
    
    def run_full_test(self, test_directory="./media"):
        """Run the complete test suite."""
        print("🎬 Data Ingestion Tool v2 - Workflow Test")
        print("=" * 60)
        
        results = []
        
        # Test 1: NSFW Detection Availability
        results.append(self.test_nsfw_detection_availability())
        
        # Test 2: Directory Listing
        results.append(self.test_directory_listing())
        
        # Test 3: Processing Workflow
        session_id = self.test_processing_workflow(test_directory)
        if session_id:
            results.append(True)
            
            # Test 4: Preview Report
            results.append(self.test_preview_report(session_id))
            
            # Test 5: Cleanup
            results.append(self.test_cleanup(session_id))
        else:
            results.extend([False, False, False])  # Failed processing, report, cleanup
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        test_names = [
            "NSFW Detection Availability",
            "Directory Listing API", 
            "Processing Workflow",
            "Preview Report Generation",
            "Session Cleanup"
        ]
        
        passed = sum(results)
        total = len(results)
        
        for i, (name, result) in enumerate(zip(test_names, results)):
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{i+1}. {status} {name}")
        
        print(f"\nTotal: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
        
        if passed == total:
            print("\n🎉 ALL TESTS PASSED! The ingestion workflow is working correctly!")
            return True
        else:
            print(f"\n⚠️ {total-passed} tests failed. Check the output above for details.")
            return False


def main():
    """Main test function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test the Data Ingestion Tool v2")
    parser.add_argument("--url", default="http://127.0.0.1:7864", 
                       help="Base URL of the application")
    parser.add_argument("--directory", default="./media",
                       help="Test directory for processing")
    
    args = parser.parse_args()
    
    # Check if directory exists
    test_dir = Path(args.directory)
    if not test_dir.exists():
        print(f"❌ Test directory does not exist: {test_dir}")
        print("Create some test media files or specify a different directory with --directory")
        return 1
    
    # Run tests
    tester = IngestionWorkflowTest(args.url)
    success = tester.run_full_test(args.directory)
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())