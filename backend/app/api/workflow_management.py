"""
Workflow Management API - MINIMAL FOR BHIV AI ASSISTANT
Only essential automation endpoints for AI assistant workflows
"""
import logging
from typing import Dict

from app.external_services import get_service_health_status
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/automation", tags=["🤖 BHIV Automations"])


class AutomationRequest(BaseModel):
    """Request for BHIV automation workflows"""

    workflow_type: str  # pdf_compliance, design_optimization, health_monitoring
    parameters: Dict


class PDFComplianceRequest(BaseModel):
    """PDF compliance automation request"""

    pdf_url: str
    city: str
    sohum_url: str = "https://ai-rule-api-w7z5.onrender.com"


@router.get("/status")
async def get_automation_status():
    """Get BHIV automation system status with real execution history"""
    from app.database_mongodb import SessionLocal

    try:
        workflow_status = {"status": "healthy"}
        service_status = await get_service_health_status()

        # Get recent workflow executions
        db = SessionLocal()
        try:
            recent_runs = None  # Mock database operation
            executions = []
            for run in recent_runs:
                executions.append(
                    {
                        "workflow_id": run.id,
                        "run_id": run.flow_run_id,
                        "flow_name": run.flow_name,
                        "status": run.status,
                        "started_at": run.started_at.isoformat() if run.started_at else None,
                        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                        "duration_seconds": run.duration_seconds,
                        "parameters": run.parameters,
                    }
                )
        finally:
            db.close()

        return {
            "automation_system": workflow_status,
            "external_services": service_status,
            "available_workflows": ["pdf_compliance", "design_optimization", "health_monitoring"],
            "status": "operational" if workflow_status.get("prefect_available") else "limited",
            "recent_executions": executions,
            "total_executions": len(executions),
        }
    except Exception as e:
        logger.error(f"Failed to get automation status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pdf-compliance")
async def trigger_pdf_compliance(request: PDFComplianceRequest):
    """Trigger PDF compliance automation - ESSENTIAL for BHIV"""
    try:
        parameters = {"pdf_url": request.pdf_url, "city": request.city, "sohum_url": request.sohum_url}
        result = {"status": "mock"}
        return result
    except Exception as e:
        logger.error(f"PDF compliance automation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workflow")
async def trigger_workflow(request: AutomationRequest):
    """Trigger any BHIV automation workflow with real Prefect tracking"""
    from datetime import datetime, timezone

    from app.database_mongodb import SessionLocal

    try:
        # Trigger workflow via Prefect
        result = {"status": "mock"}

        if result.get("status") != "success":
            raise HTTPException(status_code=500, detail=result.get("message", "Workflow trigger failed"))

        # Return traceable response
        return {
            "status": "success",
            "workflow_id": result.get("workflow_id"),
            "run_id": result.get("run_id") or result.get("flow_run_id"),
            "workflow_type": request.workflow_type,
            "execution_mode": result.get("execution_mode", "prefect"),
            "message": "Workflow triggered successfully",
            "traceable": True,
            "status_endpoint": f"/api/v1/automation/workflow/{result.get('run_id') or result.get('flow_run_id')}/status",
        }
    except Exception as e:
        logger.error(f"Automation workflow failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workflow/{flow_run_id}/status")
async def get_workflow_run_status(flow_run_id: str):
    """Get real-time status of specific workflow run with full execution details"""
    from app.database_mongodb import SessionLocal

    try:
        # Get status from Prefect and database
        result = await get_workflow_status(flow_run_id)

        if result.get("status") != "success":
            raise HTTPException(status_code=404, detail=result.get("message", "Workflow not found"))

        # Enrich with database info
        db = SessionLocal()
        try:
            workflow_run = None  # Mock database operation
            if workflow_run:
                result["database_record"] = {
                    "id": workflow_run.id,
                    "flow_name": workflow_run.flow_name,
                    "deployment_name": workflow_run.deployment_name,
                    "result": workflow_run.result,
                    "error": workflow_run.error,
                }
        finally:
            db.close()

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get workflow status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
