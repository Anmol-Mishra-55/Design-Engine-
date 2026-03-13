#!/usr/bin/env python3
"""
Quick fix for missing Supabase buckets - provides manual setup instructions
"""

print(
    """
🔧 SUPABASE BUCKET SETUP REQUIRED

Your upload is failing because Supabase storage buckets don't exist.

MANUAL SETUP STEPS:

1. Go to your Supabase Dashboard: https://supabase.com/dashboard
2. Select your project: dntmhjlbxirtgslzwbui
3. Go to Storage > Buckets
4. Create these buckets:

   📁 Bucket: "files"
   - Public: No (Private)
   - File size limit: 50MB
   - Allowed MIME types: image/*, application/pdf, text/*, application/*

   📁 Bucket: "previews"
   - Public: No (Private)
   - File size limit: 100MB
   - Allowed MIME types: model/gltf-binary, application/octet-stream

   📁 Bucket: "geometry"
   - Public: No (Private)
   - File size limit: 100MB
   - Allowed MIME types: application/octet-stream, model/*

   📁 Bucket: "compliance"
   - Public: No (Private)
   - File size limit: 50MB
   - Allowed MIME types: application/zip, application/x-zip-compressed

5. After creating buckets, your /api/v1/upload endpoint will work!

ALTERNATIVE: Use service_role key instead of anon key for bucket creation.
"""
)

# Test current bucket access
try:
    from app.config import settings

    supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    buckets = supabase.storage.list_buckets()

    print(f"✅ Current buckets: {[b['name'] for b in buckets]}")

    required_buckets = ["files", "previews", "geometry", "compliance"]
    missing_buckets = [b for b in required_buckets if b not in [bucket["name"] for bucket in buckets]]

    if missing_buckets:
        print(f"❌ Missing buckets: {missing_buckets}")
    else:
        print("✅ All required buckets exist!")

except Exception as e:
    print(f"❌ Error checking buckets: {e}")
