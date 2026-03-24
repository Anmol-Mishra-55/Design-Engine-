#!/usr/bin/env python3
"""
Smart Server Startup
Handles MongoDB connection issues gracefully
"""

import asyncio
import subprocess
import sys
from pathlib import Path

async def test_mongodb_connection():
    """Test if MongoDB is available"""
    try:
        import pymongo

        # Test local MongoDB first
        try:
            client = pymongo.MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=2000)
            client.admin.command('ping')
            client.close()
            print("✅ Local MongoDB available")
            return "mongodb://localhost:27017"
        except:
            print("⚠️  Local MongoDB not available")

        # Test Atlas connection (if configured)
        atlas_url = "mongodb+srv://blackholeinfiverse55_db_user:6SKTXNiidEZNTtDc@cluster0.acfgtzl.mongodb.net/?appName=Cluster0&retryWrites=true&w=majority"
        try:
            client = pymongo.MongoClient(atlas_url, serverSelectionTimeoutMS=5000)
            client.admin.command('ping')
            client.close()
            print("✅ MongoDB Atlas available")
            return atlas_url
        except Exception as e:
            print(f"⚠️  MongoDB Atlas not available: {e}")

        print("❌ No MongoDB available - server will start without database")
        return None

    except ImportError:
        print("❌ pymongo not installed")
        return None

def create_env_file(mongodb_url):
    """Create .env file with working MongoDB URL"""
    env_content = f"""# MongoDB Configuration
MONGODB_URL={mongodb_url or 'mongodb://localhost:27017'}
MONGODB_DATABASE=bhiv_db

# JWT Configuration
JWT_SECRET_KEY=bhiv-jwt-secret-2024-super-secure-key-for-production
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Application Settings
DEBUG=false
ENVIRONMENT=development
HOST=0.0.0.0
PORT=8000
"""

    with open('backend/.env', 'w') as f:
        f.write(env_content)

    print(f"✅ Created .env file with MongoDB URL: {mongodb_url or 'localhost'}")

async def main():
    """Main startup function"""
    print("🚀 Smart Server Startup")
    print("=" * 40)

    # Test MongoDB connection
    mongodb_url = await test_mongodb_connection()

    # Create .env file
    create_env_file(mongodb_url)

    # Start server
    print("\n🎯 Starting FastAPI server...")
    print("📍 Server will be available at: http://localhost:8000")
    print("📚 API docs at: http://localhost:8000/docs")

    if not mongodb_url:
        print("\n⚠️  WARNING: No database connection")
        print("   - Server will start but some features may not work")
        print("   - Install local MongoDB or fix Atlas connection")

    print("\n" + "=" * 40)

    # Change to backend directory and start server
    try:
        import os
        os.chdir('backend')

        # Start uvicorn
        subprocess.run([
            sys.executable, "-m", "uvicorn",
            "app.main:app",
            "--reload",
            "--host", "0.0.0.0",
            "--port", "8000"
        ])
    except KeyboardInterrupt:
        print("\n👋 Server stopped")
    except Exception as e:
        print(f"❌ Failed to start server: {e}")

if __name__ == "__main__":
    asyncio.run(main())
