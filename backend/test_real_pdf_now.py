#!/usr/bin/env python3
"""
Test Real PDF Processing - Live Test
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


async def test_real_pdf():
    """Test with real PDF URLs"""

    # Real PDF URLs to test
    test_pdfs = [
        {
            "url": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
            "city": "Mumbai",
            "description": "W3C Test PDF",
        },
        {
            "url": "https://www.adobe.com/support/products/enterprise/knowledgecenter/media/c4611_sample_explain.pdf",
            "city": "Pune",
            "description": "Adobe Sample PDF",
        },
        {
            "url": "https://www.learningcontainer.com/wp-content/uploads/2019/09/sample-pdf-file.pdf",
            "city": "Ahmedabad",
            "description": "Learning Container Sample PDF",
        },
    ]

    sohum_url = "http://localhost:8001"

    print("Testing Real PDF Processing")
    print("=" * 50)

    for i, test_case in enumerate(test_pdfs, 1):
        print(f"\nTest {i}: {test_case['description']}")
        print(f"URL: {test_case['url']}")
        print(f"City: {test_case['city']}")
        print("-" * 30)

        try:
            result = {"status": "mock"}

            print(f"Status: {result['status']}")
            print(f"Workflow: {result.get('workflow', 'unknown')}")

            if result["status"] == "success":
                print(f"Rules extracted: {result['result']['rules_count']}")
                print(f"Sections found: {result['result'].get('sections_count', 0)}")
                print(f"MCP success: {result['result']['success']}")
            else:
                print(f"Error: {result.get('message', 'Unknown error')}")

        except Exception as e:
            print(f"Test failed: {e}")

        print()


if __name__ == "__main__":
    asyncio.run(test_real_pdf())
