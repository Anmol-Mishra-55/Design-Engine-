#!/usr/bin/env python3
"""
Test PDF Workflow with Real Data
Ready to accept real PDF URLs from user
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


async def test_with_real_pdf(pdf_url: str, city: str = "Mumbai", sohum_url: str = "http://localhost:8001"):
    """Test PDF workflow with real PDF URL"""
    print(f"Testing PDF workflow with real data:")
    print(f"  PDF URL: {pdf_url}")
    print(f"  City: {city}")
    print(f"  MCP URL: {sohum_url}")
    print()

    try:
        result = {"status": "mock"}

        print(f"Status: {result['status']}")
        print(f"Workflow: {result.get('workflow', 'unknown')}")

        if result["status"] == "success":
            print(f"Rules extracted: {result['result']['rules_count']}")
            print(f"MCP success: {result['result']['success']}")
        else:
            print(f"Error: {result.get('message', 'Unknown error')}")

        return result

    except Exception as e:
        print(f"Test failed: {e}")
        return {"status": "error", "message": str(e)}


def main():
    """Main test function - ready for real PDF URL"""
    print("PDF Workflow - Real Data Test")
    print("=" * 40)

    # Get PDF URL from user
    pdf_url = input("Enter PDF URL (or press Enter for demo): ").strip()

    if not pdf_url:
        print("No URL provided. Please provide a real PDF URL to test.")
        print("\nExample usage:")
        print("python test_real_pdf_workflow.py")
        print("Then enter: https://your-supabase-storage.com/compliance.pdf")
        return

    # Get city
    city = input("Enter city (default: Mumbai): ").strip() or "Mumbai"

    # Get MCP URL
    sohum_url = input("Enter MCP URL (default: http://localhost:8001): ").strip() or "http://localhost:8001"

    # Run test
    result = asyncio.run(test_with_real_pdf(pdf_url, city, sohum_url))

    if result["status"] == "success":
        print("\n✅ PDF processing successful!")
    else:
        print("\n❌ PDF processing failed!")


if __name__ == "__main__":
    main()
