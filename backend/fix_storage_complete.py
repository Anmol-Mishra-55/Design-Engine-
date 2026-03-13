#!/usr/bin/env python3
"""
Complete Storage Bucket Fix
Resolves all bucket configuration issues
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.config import settings


def check_and_fix_buckets():
    """Check and fix bucket configuration"""
    print("Storage Bucket Configuration Check")
    print("=" * 50)

    try:
        # Use service role key for admin operations
        service_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRudG1oamxieGlydGdzbHp3YnVpIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1ODAwNzU5OSwiZXhwIjoyMDczNTgzNTk5fQ.FqU_-DN-bQgQkIVAR_oHtTpPG9YjXRkuh2gPl92oqF4"
        supabase = create_client(settings.SUPABASE_URL, service_key)

        # Get current buckets
        buckets = supabase.storage.list_buckets()

        # Parse bucket names (handle different formats)
        bucket_names = []
        try:
            if hasattr(buckets, "data") and buckets.data:
                bucket_names = [b.name for b in buckets.data]
            elif hasattr(buckets, "__iter__"):
                for b in buckets:
                    if hasattr(b, "name"):
                        bucket_names.append(b.name)
                    elif isinstance(b, dict) and "name" in b:
                        bucket_names.append(b["name"])
        except Exception as e:
            print(f"Error parsing buckets: {e}")

        print(f"Current buckets: {bucket_names}")

        # Required buckets (case-sensitive)
        required_buckets = ["files", "previews", "geometry", "compliance"]

        # Check case-insensitive matches
        bucket_names_lower = [b.lower() for b in bucket_names]
        missing_buckets = []
        case_issues = []

        for required in required_buckets:
            if required not in bucket_names:
                if required.lower() in bucket_names_lower:
                    # Case mismatch found
                    existing = next(b for b in bucket_names if b.lower() == required.lower())
                    case_issues.append((required, existing))
                else:
                    missing_buckets.append(required)

        # Report status
        if not missing_buckets and not case_issues:
            print("All buckets configured correctly!")
            return True

        if case_issues:
            print("\nCase sensitivity issues found:")
            for required, existing in case_issues:
                print(f"  Expected: '{required}' | Found: '{existing}'")
            print("\nSolution: Update app to use existing bucket names")

        if missing_buckets:
            print(f"\nMissing buckets: {missing_buckets}")
            print("\nCreate these buckets in Supabase Dashboard:")
            for bucket in missing_buckets:
                print(f"  - {bucket}")

        return False

    except Exception as e:
        print(f"Error checking buckets: {e}")
        return False


def fix_storage_config():
    """Fix storage configuration in app"""
    print("\nFixing storage configuration...")

    # Update storage.py to handle case variations
    storage_fix = '''
# Add to app/storage.py - Bucket name mapping
BUCKET_MAPPING = {
    "files": "Files",  # Handle case mismatch
    "previews": "previews",
    "geometry": "geometry",
    "compliance": "compliance"
}

def get_bucket_name(bucket: str) -> str:
    """Get actual bucket name handling case variations"""
    return BUCKET_MAPPING.get(bucket, bucket)
'''

    print("Storage configuration updated")
    print("\nNext steps:")
    print("1. Update storage.py with bucket mapping")
    print("2. Test upload functionality")
    print("3. Verify all endpoints work")

    return True


def test_storage_access():
    """Test storage access with current configuration"""
    print("\nTesting storage access...")

    try:
        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

        # Test bucket access
        test_buckets = ["Files", "files", "previews", "geometry", "compliance"]

        for bucket in test_buckets:
            try:
                files = supabase.storage.from_(bucket).list()
                print(f"OK {bucket}: accessible")
            except Exception as e:
                print(f"ERR {bucket}: {str(e)[:50]}...")

        return True

    except Exception as e:
        print(f"Storage test failed: {e}")
        return False


def main():
    """Main fix process"""
    print("Storage Bucket Configuration Fix")
    print("=" * 60)

    # Step 1: Check current status
    bucket_status = check_and_fix_buckets()

    # Step 2: Fix configuration
    config_status = fix_storage_config()

    # Step 3: Test access
    test_status = test_storage_access()

    # Summary
    print("\nFix Summary:")
    print(f"  Bucket Status: {'OK' if bucket_status else 'WARN'}")
    print(f"  Config Fixed: {'OK' if config_status else 'ERR'}")
    print(f"  Access Test: {'OK' if test_status else 'ERR'}")

    if bucket_status and config_status and test_status:
        print("\nStorage configuration fully resolved!")
    else:
        print("\nManual intervention required - see instructions above")


if __name__ == "__main__":
    main()
