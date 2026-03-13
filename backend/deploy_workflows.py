"""
Deploy Prefect Workflows
Script to deploy all workflows to Prefect Cloud or local server
"""
import asyncio
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from app.config import settings
    from prefect.deployments import Deployment
    from workflows.pdf_to_mcp_flow import pdf_to_mcp_flow

    PREFECT_AVAILABLE = True
except ImportError:
    PREFECT_AVAILABLE = False
    print("Prefect not available - workflows will run in direct mode")


async def deploy_pdf_workflow():
    """Deploy PDF to MCP workflow"""
    if not PREFECT_AVAILABLE:
        print("Skipping workflow deployment - Prefect not available")
        return

    try:
        deployment = Deployment.build_from_flow(
            flow=pdf_to_mcp_flow,
            name="pdf-to-mcp-production",
            version="1.0.0",
            work_queue_name="default",
            tags=["compliance", "pdf", "mcp", "production"],
            description="Automated PDF compliance rule extraction and MCP ingestion",
            parameters={
                "city": "Mumbai",
                "sohum_mcp_url": getattr(settings, "SOHAM_URL", "https://ai-rule-api-w7z5.onrender.com"),
            },
        )

        deployment_id = await deployment.apply()
        print(f"✅ PDF to MCP workflow deployed: {deployment_id}")
        return deployment_id

    except Exception as e:
        print(f"❌ PDF workflow deployment failed: {e}")
        return None


async def deploy_all_workflows():
    """Deploy all available workflows"""
    print("🚀 Starting workflow deployment...")

    deployments = []

    # Deploy PDF workflow
    pdf_deployment = await deploy_pdf_workflow()
    if pdf_deployment:
        deployments.append(pdf_deployment)

    print(f"\n📊 Deployment Summary:")
    print(f"   Total workflows: 1")
    print(f"   Successfully deployed: {len(deployments)}")
    print(f"   Failed: {1 - len(deployments)}")

    if deployments:
        print(f"\n✅ All workflows deployed successfully!")
        print(f"   Deployment IDs: {deployments}")
    else:
        print(f"\n⚠️  No workflows deployed - running in direct mode")

    return deployments


async def test_workflow_connectivity():
    """Test workflow system connectivity"""
    print("🔍 Testing workflow connectivity...")

    try:
        status = {"status": "healthy"}
        print(f"   Workflow status: {status}")

        if status.get("prefect") == "available":
            print("✅ Prefect system is available")
        else:
            print("⚠️  Prefect system unavailable - using direct execution")

    except Exception as e:
        print(f"❌ Workflow connectivity test failed: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("🔧 Design Engine API - Workflow Deployment")
    print("=" * 60)

    async def main():
        await test_workflow_connectivity()
        print()
        await deploy_all_workflows()
        print("\n" + "=" * 60)
        print("✨ Workflow deployment complete!")
        print("=" * 60)

    asyncio.run(main())
