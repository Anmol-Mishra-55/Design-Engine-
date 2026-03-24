#!/bin/bash
# Setup Task 8 repository structure

echo "🚀 Setting up Task 8: BHIV AI Assistant Integration"

# Create new repo structure
mkdir -p bhiv-assistant
cd bhiv-assistant

# Initialize directories
mkdir -p app/{bhiv_layer,mcp,multi_city,geometry,integrations}
mkdir -p workflows
mkdir -p deployment/{staging,production}
mkdir -p tests/{unit,integration}
mkdir -p docs
mkdir -p reports

# Create __init__.py files
find app -type d -exec touch {}/__init__.py \;
find tests -type d -exec touch {}/__init__.py \;

# Initialize git
git init
git remote add origin https://github.com/anmolmishra-eng/bhiv-assistant.git

# Create requirements
cat > requirements.txt << 'EOF'
# Core dependencies
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
sqlalchemy==2.0.23
alembic==1.13.0

# Workflow orchestration (Prefect instead of N8N)
prefect==2.14.3
prefect-docker==0.4.1
prefect-sqlalchemy==0.2.4

# Task 7 integration
httpx==0.25.1
aiohttp==3.9.0

# Multi-agent systems
langchain==0.0.340
anthropic==0.7.0

# Geometry processing
trimesh==4.0.5
pygltflib==1.16.1
numpy==1.24.3

# MCP integration
pydantic-mcp==0.1.0

# Multi-city datasets
geopandas==0.14.0
shapely==2.0.2

# Testing
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0

# Monitoring
sentry-sdk==1.38.0
prometheus-client==0.19.0
EOF
EOF

# Install dependencies
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

echo "✅ Task 8 structure created!"
echo "📂 Directory: $(pwd)"
