#!/usr/bin/env python3
"""
Smart Startup Script
Validates dependencies and starts the server with appropriate configuration
"""

import importlib
import subprocess
import sys
from pathlib import Path

def check_dependency(module_name: str, package_name: str = None) -> bool:
    """Check if a dependency is available"""
    try:
        importlib.import_module(module_name)
        return True
    except ImportError:
        return False

def install_minimal_deps():
    """Install minimal dependencies"""
    print("📦 Installing minimal dependencies...")
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r",
            "backend/requirements_minimal.txt"
        ])
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False

def check_environment():
    """Check environment and dependencies"""
    print("🔍 Checking environment...")

    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ required")
        return False

    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}")

    # Check core dependencies
    core_deps = [
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("pydantic", "pydantic"),
        ("pymongo", "pymongo"),
        ("motor", "motor"),
    ]

    missing_core = []
    for module, package in core_deps:
        if check_dependency(module):
            print(f"✅ {package}")
        else:
            print(f"❌ {package}")
            missing_core.append(package)

    if missing_core:
        print(f"\n📦 Missing core dependencies: {', '.join(missing_core)}")
        print("Installing minimal requirements...")
        if not install_minimal_deps():
            return False

    # Check optional dependencies
    optional_deps = [
        ("stable_baselines3", "stable-baselines3", "RL training"),
        ("gymnasium", "gymnasium", "RL environments"),
        ("torch", "torch", "ML models"),
        ("openai", "openai", "OpenAI API"),
        ("anthropic", "anthropic", "Claude API"),
    ]

    print("\n🔧 Optional dependencies:")
    for module, package, description in optional_deps:
        if check_dependency(module):
            print(f"✅ {package} - {description}")
        else:
            print(f"⚠️  {package} - {description} (optional)")

    return True

def start_server():
    """Start the FastAPI server"""
    print("\n🚀 Starting FastAPI server...")

    # Change to backend directory
    backend_dir = Path("backend")
    if backend_dir.exists():
        import os
        os.chdir(backend_dir)

    # Start server
    try:
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
        print(f"❌ Server failed to start: {e}")
        return False

    return True

def main():
    """Main function"""
    print("🎯 BHIV Backend Smart Startup")
    print("=" * 40)

    # Check environment
    if not check_environment():
        print("\n❌ Environment check failed")
        print("\n📋 Manual setup instructions:")
        print("1. pip install -r backend/requirements_minimal.txt")
        print("2. cp .env.example .env")
        print("3. Edit .env with your MongoDB credentials")
        print("4. python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
        return

    # Check .env file
    env_file = Path(".env")
    if not env_file.exists():
        print("\n⚠️  .env file not found")
        print("📋 Creating from template...")
        env_example = Path(".env.example")
        if env_example.exists():
            import shutil
            shutil.copy(env_example, env_file)
            print("✅ .env created from .env.example")
            print("🔧 Please edit .env with your actual credentials")
        else:
            print("❌ .env.example not found")
            print("🔧 Please create .env file manually")

    print("\n✅ Environment ready!")

    # Ask user if they want to start the server
    try:
        response = input("\n🚀 Start the server now? (y/n): ").lower().strip()
        if response in ['y', 'yes', '']:
            start_server()
        else:
            print("\n📋 To start manually:")
            print("cd backend && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")

if __name__ == "__main__":
    main()
