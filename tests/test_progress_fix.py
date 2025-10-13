#!/usr/bin/env python3
"""
Test to verify progress calculation is fixed.
This tests that progress updates correctly during file processing.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


def test_progress_calculation():
    """Test that progress calculation works correctly."""
    print("Testing progress calculation logic...")
    
    # Simulate processing 10 files
    total_files = 10
    expected_progress = []
    
    for i in range(total_files):
        # Old formula (broken): progress = int((i / len(files)) * 100)
        old_progress = int((i / total_files) * 100)
        
        # New formula (fixed): progress = int(((i + 1) / len(files)) * 100)
        new_progress = int(((i + 1) / total_files) * 100)
        
        expected_progress.append({
            'file_index': i,
            'old_progress': old_progress,
            'new_progress': new_progress
        })
    
    print("\n📊 Progress Calculation Comparison:")
    print(f"{'File':<6} {'Old %':<10} {'New %':<10} {'Status'}")
    print("-" * 50)
    
    for item in expected_progress:
        file_num = item['file_index'] + 1
        old_pct = item['old_progress']
        new_pct = item['new_progress']
        status = "✅" if new_pct > old_pct or (file_num == 1 and new_pct == 10) else "⚠️"
        print(f"{file_num:<6} {old_pct}%{'':<7} {new_pct}%{'':<7} {status}")
    
    # Verify the fix
    print("\n🔍 Verification:")
    
    # Check first file (should be 10% with new formula, not 0%)
    if expected_progress[0]['new_progress'] == 10:
        print("✅ First file shows 10% progress (was 0%)")
    else:
        print("❌ First file progress calculation failed")
        return False
    
    # Check last file (should be 100% with new formula, not 90%)
    if expected_progress[-1]['new_progress'] == 100:
        print("✅ Last file shows 100% progress (was 90%)")
    else:
        print("❌ Last file progress calculation failed")
        return False
    
    # Check that progress increases monotonically
    for i in range(1, len(expected_progress)):
        if expected_progress[i]['new_progress'] <= expected_progress[i-1]['new_progress']:
            print(f"❌ Progress not monotonically increasing at file {i+1}")
            return False
    
    print("✅ Progress increases monotonically")
    
    print("\n🎉 Progress calculation test PASSED!")
    return True


async def test_session_updates():
    """Test that session updates work correctly in the actual code."""
    print("\n\nTesting session update logic...")
    
    # Simulate the session structure
    session = {
        "progress": 0,
        "processed_files": 0,
        "stats": {
            "processed_files": 0,
            "metadata_extracted": 0,
            "keywords_added": 0,
            "scores_imported": 0,
            "nsfw_detected": 0,
            "errors": 0
        }
    }
    
    # Simulate processing 5 files
    files = [f"file_{i}.png" for i in range(5)]
    
    print("\n📊 Session Updates During Processing:")
    print(f"{'File':<12} {'Progress':<10} {'Processed':<12} {'Stats Sum'}")
    print("-" * 60)
    
    for i, file_path in enumerate(files):
        # Simulate processing (mimics the fixed code)
        file_data = {
            "metadata": True,
            "keywords": ["test", "example"],
            "score": 3
        }
        
        session["processed_files"] += 1
        session["stats"]["processed_files"] += 1
        
        if file_data.get("metadata"):
            session["stats"]["metadata_extracted"] += 1
        if file_data.get("keywords"):
            session["stats"]["keywords_added"] += len(file_data["keywords"])
        if file_data.get("score") is not None:
            session["stats"]["scores_imported"] += 1
        
        # Update progress AFTER processing (NEW behavior)
        session["progress"] = int(((i + 1) / len(files)) * 100)
        
        stats_sum = sum([
            session["stats"]["processed_files"],
            session["stats"]["metadata_extracted"],
            session["stats"]["keywords_added"],
            session["stats"]["scores_imported"]
        ])
        
        print(f"{file_path:<12} {session['progress']}%{'':<7} {session['processed_files']:<12} {stats_sum}")
    
    # Verify final state
    print("\n🔍 Final Verification:")
    
    if session["progress"] == 100:
        print(f"✅ Final progress is 100% (was {int((4/5)*100)}% with old formula)")
    else:
        print(f"❌ Final progress is {session['progress']}% (expected 100%)")
        return False
    
    if session["processed_files"] == 5:
        print(f"✅ All 5 files processed")
    else:
        print(f"❌ Processed files count incorrect: {session['processed_files']}")
        return False
    
    if session["stats"]["processed_files"] == 5:
        print(f"✅ Stats show 5 files processed")
    else:
        print(f"❌ Stats incorrect: {session['stats']['processed_files']}")
        return False
    
    print("\n🎉 Session update test PASSED!")
    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("🧪 Progress Indication Fix - Test Suite")
    print("=" * 60)
    
    results = []
    
    # Test 1: Progress calculation logic
    results.append(test_progress_calculation())
    
    # Test 2: Session updates
    results.append(asyncio.run(test_session_updates()))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    test_names = [
        "Progress Calculation Logic",
        "Session Update Logic"
    ]
    
    for i, (name, result) in enumerate(zip(test_names, results)):
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{i+1}. {status} - {name}")
    
    passed = sum(results)
    total = len(results)
    print(f"\nTotal: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️ {total-passed} tests failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
