"""
Enhanced Prefect Integration Module
Robust workflow orchestration with fallbacks and monitoring
"""
import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Check Prefect availability
try:
    from prefect import get_client
    from workflows.pdf_to_mcp_flow import pdf_to_mcp_flow

    PREFECT_AVAILABLE = True
    logger.info("Prefect integration available")
except ImportError as e:
    PREFECT_AVAILABLE = False
    logger.warning(f"Prefect not available: {e}. Using direct execution mode.")

# Check if we have Prefect configuration
PREFECT_CONFIGURED = bool(os.getenv("PREFECT_API_KEY") or os.getenv("PREFECT_API_URL"))


async def get_workflow_system_status() -> Dict:
    """Comprehensive workflow system status check"""
    status = {
        "prefect_installed": PREFECT_AVAILABLE,
        "prefect_configured": PREFECT_CONFIGURED,
        "mode": "direct",
        "timestamp": datetime.now().isoformat(),
    }

    if PREFECT_AVAILABLE and PREFECT_CONFIGURED:
        try:
            client = get_client()
            status.update({"prefect_client": "connected", "mode": "workflow", "status": "operational"})
            logger.info("Prefect client connected successfully")
        except Exception as e:
            status.update({"prefect_client": "error", "mode": "direct", "status": "degraded", "error": str(e)})
            logger.error(f"Prefect client connection failed: {e}")
    elif PREFECT_AVAILABLE:
        status.update(
            {
                "prefect_client": "not_configured",
                "status": "available_but_not_configured",
                "note": "Prefect is installed but not configured. Set PREFECT_API_KEY to enable.",
            }
        )
    else:
        status.update(
            {
                "prefect_client": "not_installed",
                "status": "unavailable",
                "note": "Prefect is not installed. Install with: pip install prefect",
            }
        )

    return status


async def trigger_pdf_compliance_workflow(pdf_url: str, city: str, sohum_url: str) -> Dict:
    """Trigger PDF to MCP workflow with intelligent routing"""
    workflow_id = f"pdf_workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Try Prefect if available and configured
    if PREFECT_AVAILABLE and PREFECT_CONFIGURED:
        try:
            logger.info(f"[{workflow_id}] Starting Prefect workflow for {city}")
            result = await pdf_to_mcp_flow(pdf_url, city, sohum_url)
            return {
                "workflow_id": workflow_id,
                "status": "success",
                "execution_mode": "prefect",
                "result": result,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"[{workflow_id}] Prefect workflow failed: {e}")
            logger.info(f"[{workflow_id}] Falling back to direct execution")
            return await _direct_pdf_processing(pdf_url, city, sohum_url, workflow_id)
    else:
        logger.info(f"[{workflow_id}] Using direct execution (Prefect not available/configured)")
        return await _direct_pdf_processing(pdf_url, city, sohum_url, workflow_id)


async def _direct_pdf_processing(pdf_url: str, city: str, sohum_url: str, workflow_id: str = None) -> Dict:
    """Direct PDF processing without Prefect with enhanced error handling"""
    if not workflow_id:
        workflow_id = f"direct_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    try:
        logger.info(f"[{workflow_id}] Starting direct PDF processing for {city}")

        # Import workflow functions directly
        from workflows.pdf_to_mcp_flow import (
            cleanup_temp_files,
            download_pdf_from_storage,
            extract_text_from_pdf,
            parse_compliance_rules,
            send_rules_to_mcp,
        )

        # Execute workflow steps directly with progress tracking
        logger.info(f"[{workflow_id}] Step 1: Downloading PDF")
        local_path = f"temp/{city}_compliance.pdf"
        pdf_path = download_pdf_from_storage(pdf_url, local_path)

        logger.info(f"[{workflow_id}] Step 2: Extracting text from PDF")
        text_content = extract_text_from_pdf(pdf_path)

        logger.info(f"[{workflow_id}] Step 3: Parsing compliance rules")
        rules = parse_compliance_rules(text_content, city)

        logger.info(f"[{workflow_id}] Step 4: Sending rules to MCP")
        success = await send_rules_to_mcp(rules, sohum_url)

        logger.info(f"[{workflow_id}] Step 5: Cleaning up temporary files")
        cleanup_temp_files(pdf_path)

        result = {
            "workflow_id": workflow_id,
            "status": "success",
            "execution_mode": "direct",
            "result": {
                "city": city,
                "rules_count": len(rules["rules"]),
                "sections_count": len(rules.get("sections", [])),
                "mcp_success": success,
            },
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(f"[{workflow_id}] Direct PDF processing completed successfully")
        return result

    except Exception as e:
        logger.error(f"[{workflow_id}] Direct PDF processing failed: {e}")
        return {
            "workflow_id": workflow_id,
            "status": "error",
            "execution_mode": "direct",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


async def get_workflow_capabilities() -> Dict:
    """Get available workflow capabilities"""
    capabilities = {
        "pdf_processing": True,
        "direct_execution": True,
        "prefect_workflows": PREFECT_AVAILABLE and PREFECT_CONFIGURED,
        "supported_formats": ["pdf"],
        "supported_cities": ["Mumbai", "Pune", "Ahmedabad", "Nashik"],
    }

    if PREFECT_AVAILABLE:
        capabilities["prefect_version"] = "available"
        if PREFECT_CONFIGURED:
            capabilities["prefect_status"] = "configured"
        else:
            capabilities["prefect_status"] = "not_configured"
    else:
        capabilities["prefect_version"] = "not_installed"
        capabilities["prefect_status"] = "unavailable"

    return capabilities


async def trigger_health_monitoring_workflow() -> Dict:
    """Trigger health monitoring workflow for external services"""
    workflow_id = f"health_monitor_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    try:
        from app.external_services import initialize_external_services

        logger.info(f"[{workflow_id}] Starting health monitoring workflow")
        service_status = await initialize_external_services()

        return {
            "workflow_id": workflow_id,
            "status": "success",
            "execution_mode": "direct",
            "result": service_status,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"[{workflow_id}] Health monitoring workflow failed: {e}")
        return {"workflow_id": workflow_id, "status": "error", "error": str(e), "timestamp": datetime.now().isoformat()}
