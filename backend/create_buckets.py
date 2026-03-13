#!/usr/bin/env python3
"""
Create required Supabase storage buckets for the Design Engine API
"""

import logging

from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_buckets():
    """Create all required Supabase storage buckets"""

    # Use service role key for bucket creation
    service_role_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRudG1oamxieGlydGdzbHp3YnVpIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1ODAwNzU5OSwiZXhwIjoyMDczNTgzNTk5fQ.FqU_-DN-bQgQkIVAR_oHtTpPG9YjXRkuh2gPl92oqF4"

    # Initialize Supabase client with service role key
    supabase = create_client(settings.SUPABASE_URL, service_role_key)

    # List of buckets to create
    buckets_to_create = [
        {
            "id": "files",
            "name": "files",
            "public": False,
            "file_size_limit": 52428800,  # 50MB
            "allowed_mime_types": ["image/*", "application/pdf", "text/*", "application/*"],
        },
        {
            "id": "previews",
            "name": "previews",
            "public": False,
            "file_size_limit": 52428800,  # 50MB
            "allowed_mime_types": ["model/gltf-binary", "application/octet-stream"],
        },
        {
            "id": "geometry",
            "name": "geometry",
            "public": False,
            "file_size_limit": 52428800,  # 50MB
            "allowed_mime_types": ["application/octet-stream", "model/*"],
        },
        {
            "id": "compliance",
            "name": "compliance",
            "public": False,
            "file_size_limit": 52428800,  # 50MB
            "allowed_mime_types": ["application/zip", "application/x-zip-compressed"],
        },
    ]

    for bucket_config in buckets_to_create:
        try:
            # Try to create the bucket
            result = supabase.storage.create_bucket(
                bucket_config["id"],
                options={
                    "public": bucket_config["public"],
                    "file_size_limit": bucket_config["file_size_limit"],
                    "allowed_mime_types": bucket_config["allowed_mime_types"],
                },
            )
            logger.info(f"✅ Created bucket: {bucket_config['id']}")

        except Exception as e:
            if "already exists" in str(e).lower():
                logger.info(f"✅ Bucket already exists: {bucket_config['id']}")
            else:
                logger.error(f"❌ Failed to create bucket {bucket_config['id']}: {e}")

    # List all buckets to verify
    try:
        buckets = supabase.storage.list_buckets()
        logger.info(f"📁 Available buckets: {[b['name'] for b in buckets]}")
    except Exception as e:
        logger.error(f"❌ Failed to list buckets: {e}")


if __name__ == "__main__":
    create_buckets()
