#!/usr/bin/env python3
"""
Local MongoDB Setup
Quick setup for local development
"""

import os
import subprocess
import sys
from pathlib import Path

def check_mongodb_installed():
    """Check if MongoDB is installed locally"""
    try:
        result = subprocess.run(['mongod', '--version'],
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("✅ MongoDB is installed locally")
            return True
    except:
        pass

    print("❌ MongoDB not installed locally")
    return False

def check_mongodb_running():
    """Check if MongoDB is running"""
    try:
        import pymongo
        client = pymongo.MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=2000)
        client.admin.command('ping')
        client.close()
        print("✅ MongoDB is running locally")
        return True
    except:
        print("❌ MongoDB not running locally")
        return False

def start_mongodb_docker():
    """Start MongoDB using Docker"""
    try:
        # Check if Docker is available
        subprocess.run(['docker', '--version'], capture_output=True, check=True)
        print("✅ Docker is available")

        # Start MongoDB container
        print("🚀 Starting MongoDB in Docker...")
        subprocess.run([
            'docker', 'run', '-d',
            '--name', 'mongodb-dev',
            '-p', '27017:27017',
            'mongo:latest'
        ], check=True)

        print("✅ MongoDB started in Docker")
        print("📍 MongoDB available at: mongodb://localhost:27017")
        return True

    except subprocess.CalledProcessError:
        print("❌ Docker not available or failed to start MongoDB")
        return False
    except FileNotFoundError:
        print("❌ Docker not installed")
        return False

def update_env_file():
    """Update .env file to use local MongoDB"""
    env_content = """# MongoDB Configuration - Local Development
MONGODB_URL=mongodb://localhost:27017
MONGODB_DATABASE=bhiv_db

# JWT Configuration
JWT_SECRET_KEY=bhiv-jwt-secret-2024-super-secure-key-for-production
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Application Settings
DEBUG=true
ENVIRONMENT=development
HOST=0.0.0.0
PORT=8000

# Optional AI Services (comment out if not needed)
# OPENAI_API_KEY=your_openai_key_here
# GROQ_API_KEY=your_groq_key_here
"""

    env_path = Path('backend/.env')
    with open(env_path, 'w') as f:
        f.write(env_content)

    print(f"✅ Updated {env_path} with local MongoDB")

def main():
    """Main setup function"""
    print("🔧 Local MongoDB Setup")
    print("=" * 40)

    # Check if MongoDB is already running
    if check_mongodb_running():
        print("🎉 MongoDB is already running!")
        update_env_file()
        print("\n✅ Setup complete! Start your server with:")
        print("cd backend && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
        return

    # Try to start MongoDB with Docker
    if start_mongodb_docker():
        # Wait a moment for MongoDB to start
        import time
        print("⏳ Waiting for MongoDB to start...")
        time.sleep(5)

        if check_mongodb_running():
            update_env_file()
            print("\n🎉 Setup complete! MongoDB is running locally")
            print("✅ Start your server with:")
            print("cd backend && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
            return

    # Manual installation instructions
    print("\n📋 Manual MongoDB Installation:")
    print("=" * 40)
    print("Option 1 - Docker (Recommended):")
    print("  1. Install Docker Desktop")
    print("  2. Run: docker run -d --name mongodb-dev -p 27017:27017 mongo")
    print("")
    print("Option 2 - Native Installation:")
    print("  1. Download MongoDB Community Server")
    print("  2. Install and start MongoDB service")
    print("  3. MongoDB will be available at mongodb://localhost:27017")
    print("")
    print("Option 3 - Continue without database:")
    print("  Your server will start but database features will be disabled")

    # Update env file anyway
    update_env_file()

if __name__ == "__main__":
    main()
