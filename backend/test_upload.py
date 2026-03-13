#!/usr/bin/env python3
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_upload():
    try:
        # Test uploading a small file to the files bucket
        import uuid

        test_data = b"Hello, this is a test file!"
        unique_filename = f"test_{uuid.uuid4().hex[:8]}.txt"
        result = await upload_to_bucket("files", unique_filename, test_data)
        print("SUCCESS: Upload successful! Buckets are working.")
        print("Result:", result)
    except Exception as e:
        print("ERROR: Upload failed:", e)


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_upload())
