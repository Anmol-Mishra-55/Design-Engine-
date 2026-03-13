#!/usr/bin/env python3
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio


async def debug_preview_upload():
    try:
        print("Testing preview upload...")

        # Test data
        test_data = b"fake jpg data for testing"
        spec_id = "spec_e30672ca"
        file_extension = "jpg"
        path = f"{spec_id}.{file_extension}"

        print(f"Uploading to previews bucket: {path}")

        # Upload to bucket
        result = await upload_to_bucket("previews", path, test_data)
        print("Upload result:", result)

        # Get signed URL
        signed_url = await get_signed_url("previews", path, 600)
        print("Signed URL:", signed_url)

        print("SUCCESS: Preview upload works!")

    except Exception as e:
        print("ERROR:", str(e))
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(debug_preview_upload())
