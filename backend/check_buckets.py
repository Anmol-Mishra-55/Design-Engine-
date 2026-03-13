#!/usr/bin/env python3
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings

try:
    # Use service role key to check buckets
    service_role_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRudG1oamxieGlydGdzbHp3YnVpIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1ODAwNzU5OSwiZXhwIjoyMDczNTgzNTk5fQ.FqU_-DN-bQgQkIVAR_oHtTpPG9YjXRkuh2gPl92oqF4"
    supabase = create_client(settings.SUPABASE_URL, service_role_key)
    buckets = supabase.storage.list_buckets()

    # Handle different response formats
    try:
        if hasattr(buckets, "data") and buckets.data:
            bucket_names = [b.name for b in buckets.data]
        elif hasattr(buckets, "__iter__"):
            bucket_names = []
            for b in buckets:
                if hasattr(b, "name"):
                    bucket_names.append(b.name)
                elif isinstance(b, dict) and "name" in b:
                    bucket_names.append(b["name"])
        else:
            bucket_names = []
    except Exception as e:
        print(f"Error parsing buckets: {e}")
        bucket_names = []

    print("Current buckets:", bucket_names)

    required_buckets = ["files", "previews", "geometry", "compliance"]
    missing_buckets = [b for b in required_buckets if b not in bucket_names]

    if missing_buckets:
        print("Missing buckets:", missing_buckets)
        print("\nTo fix: Go to https://supabase.com/dashboard")
        print("-> Select your project -> Storage -> Create these buckets:")
        for bucket in missing_buckets:
            print(f"  - {bucket}")
    else:
        print("All required buckets exist!")

except Exception as e:
    print("Error checking buckets:", e)
