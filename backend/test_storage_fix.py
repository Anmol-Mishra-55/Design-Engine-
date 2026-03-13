#!/usr/bin/env python3
"""
Test Storage Fix
Verify all storage operations work correctly
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


async def test_storage_operations():
    """Test all storage operations"""
    print("Testing Storage Operations")
    print("=" * 40)

    # Test 1: Bucket name mapping
    print("1. Testing bucket name mapping:")
    test_buckets = ["files", "previews", "geometry", "compliance"]
    for bucket in test_buckets:
        mapped = get_bucket_name(bucket)
        print(f"   {bucket} -> {mapped}")

    # Test 2: Upload test
    print("\n2. Testing upload functionality:")
    try:
        # Create test data
        test_data = b"Test file content for storage validation"

        # Test upload to files bucket
        result = await upload_to_bucket("files", "test/storage_test.txt", test_data)
        print(f"   Upload successful: {result[:50]}...")

        # Test signed URL generation
        signed_url = get_signed_url("files", "test/storage_test.txt", 300)
        print(f"   Signed URL: {signed_url[:50]}...")

        print("   Storage operations: OK")

    except Exception as e:
        print(f"   Storage test error: {e}")

    # Test 3: All bucket access
    print("\n3. Testing all bucket access:")
    for bucket in test_buckets:
        try:
            # Test with small upload
            test_result = await upload_to_bucket(bucket, f"test/{bucket}_test.txt", b"test")
            print(f"   {bucket}: OK")
        except Exception as e:
            print(f"   {bucket}: ERROR - {str(e)[:30]}...")

    print("\nStorage fix validation complete!")


if __name__ == "__main__":
    asyncio.run(test_storage_operations())
